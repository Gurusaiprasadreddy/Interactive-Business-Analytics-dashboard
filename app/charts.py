"""Plotly figure builders. Used by the Streamlit app and the PDF exporter.

Design rules (see README > Design): one blue for the primary measure, a fixed
categorical order per dimension (colour follows the entity, never the rank),
thin marks, recessive grid, single y-axis per chart, legend whenever there are
two or more series.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# ---- palette (validated categorical order: blue, orange, aqua, yellow, magenta) ----
BLUE, ORANGE, AQUA, YELLOW, MAGENTA = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"
CAT = [BLUE, ORANGE, AQUA, YELLOW, MAGENTA]
INK, INK_2, GRID, SURFACE, MUTED = "#0b0b0b", "#52514e", "#e7e6e2", "#fcfcfb", "#9a998f"

REGIONS = ["North America", "Europe", "Asia Pacific", "Latin America", "Middle East & Africa"]
CATEGORIES = ["Electronics", "Home & Kitchen", "Fashion", "Beauty & Health", "Sports & Outdoors"]
CHANNELS = ["Paid Search", "Social Ads", "Email", "Affiliate", "Organic"]
REGION_COLORS = dict(zip(REGIONS, CAT))
CATEGORY_COLORS = dict(zip(CATEGORIES, CAT))
CHANNEL_COLORS = dict(zip(CHANNELS, CAT))

METRICS = {  # label -> (column, d3 tick format, hover format)
    "Revenue": ("revenue", "$~s", "$,.0f"),
    "Orders": ("orders", "~s", ",.0f"),
    "AOV": ("aov", "$,.0f", "$,.2f"),
    "CAC": ("cac", "$,.0f", "$,.2f"),
    "Churn rate": ("churn_rate", ".0%", ".1%"),
}


def _base(fig: go.Figure, title: str | None, height: int, legend: bool = False) -> go.Figure:
    fig.update_layout(
        title=dict(text=title, x=0, xanchor="left", font=dict(size=15, color=INK)) if title else None,
        height=height, margin=dict(l=8, r=8, t=48 if title else 12, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, Segoe UI, Helvetica, Arial, sans-serif", size=12, color=INK_2),
        showlegend=legend, hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1, title=None),
        hoverlabel=dict(bgcolor="white", font_size=12, font_color=INK),
    )
    fig.update_xaxes(showgrid=False, linecolor=GRID, tickcolor=GRID, zeroline=False)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, showline=False)
    return fig


def _empty(msg: str, height: int) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text=msg, showarrow=False, font=dict(size=14, color=INK_2))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return _base(fig, None, height)


def area_trend(df: pd.DataFrame, metric: str, title: str, height: int = 260,
               color: str = BLUE, granularity: str = "Month") -> go.Figure:
    col, tick, hov = METRICS[metric]
    d = df.dropna(subset=[col])
    if d.empty:
        return _empty("No data for the current selection", height)
    x_fmt = {"Month": "%b %Y", "Quarter": "Q%q %Y", "Year": "%Y"}[granularity]
    fig = go.Figure(go.Scatter(
        x=d["month"], y=d[col], mode="lines+markers" if len(d) <= 12 else "lines", name=metric,
        line=dict(color=color, width=2), marker=dict(size=7, color=color, line=dict(width=2, color=SURFACE)),
        fill="tozeroy", fillcolor=_rgba(color, 0.14),
        hovertemplate=f"<b>{metric}</b>: %{{y:{hov}}}<extra></extra>"))
    if granularity == "Quarter":  # plotly has no %q; show "2025 Q3" labels instead
        labels = d["month"].dt.to_period("Q").astype(str)
        fig.update_traces(customdata=labels, hovertemplate=f"%{{customdata}}<br><b>{metric}</b>: %{{y:{hov}}}<extra></extra>")
        fig.update_xaxes(tickmode="array", tickvals=d["month"], ticktext=labels)
    elif granularity == "Year":
        fig.update_xaxes(tickmode="array", tickvals=d["month"], ticktext=d["month"].dt.year.astype(str))
    else:
        fig.update_xaxes(tickformat="%b %y")
    fig.update_yaxes(tickformat=tick, rangemode="tozero")
    return _base(fig, title, height)


def stacked_area(monthly_by: pd.DataFrame, dim: str, colors: dict, title: str, height: int = 320,
                 granularity: str = "Month") -> go.Figure:
    """monthly_by: columns month, <dim>, revenue."""
    if monthly_by.empty:
        return _empty("No data for the current selection", height)
    order = [k for k in colors if k in set(monthly_by[dim])]
    fig = go.Figure()
    for k in order:
        d = monthly_by[monthly_by[dim] == k]
        fig.add_trace(go.Scatter(
            x=d["month"], y=d["revenue"], name=k, stackgroup="one", mode="lines",
            line=dict(width=1, color=SURFACE), fillcolor=_rgba(colors[k], 0.9),
            hovertemplate="%{y:$,.0f}"))
    fig.update_yaxes(tickformat="$~s")
    fig.update_xaxes(tickformat="%b %y")
    fig = _base(fig, title, height, legend=True)
    return fig


def region_bars(df: pd.DataFrame, title: str, height: int = 300) -> go.Figure:
    return hbar(df, "region", "revenue", REGION_COLORS, title, height)


def hbar(df: pd.DataFrame, dim: str, value: str, colors: dict | None, title: str, height: int = 300,
         fmt: str = "$,.0f", default_color: str = BLUE) -> go.Figure:
    if df.empty:
        return _empty("No data for the current selection", height)
    d = df.sort_values(value, ascending=True)
    marker = [colors.get(k, default_color) for k in d[dim]] if colors else default_color
    fig = go.Figure(go.Bar(
        x=d[value], y=d[dim], orientation="h", marker=dict(color=marker, cornerradius=4),
        text=d[value], texttemplate="%{text:" + fmt + "}", textposition="outside", cliponaxis=False,
        hovertemplate="<b>%{y}</b><br>%{x:" + fmt + "}<extra></extra>"))
    fig.update_xaxes(visible=False, range=[0, d[value].max() * 1.3])
    fig.update_yaxes(gridcolor="rgba(0,0,0,0)", automargin=True)
    fig = _base(fig, title, height)
    fig.update_layout(hovermode="closest", bargap=0.35, margin=dict(l=8, r=36, t=48 if title else 12, b=8))
    return fig


def geo_map(country_df: pd.DataFrame, metric: str, title: str, height: int = 430) -> go.Figure:
    """Choropleth by country. country_df: iso_alpha, country, revenue, orders, aov, customers."""
    col, tick, hov = METRICS[metric if metric in METRICS else "Revenue"]
    if country_df.empty:
        return _empty("No data for the current selection", height)
    fig = px.choropleth(
        country_df, locations="iso_alpha", color=col, hover_name="country",
        hover_data={"iso_alpha": False, col: False, "revenue": ":$,.0f", "orders": ":,", "aov": ":$,.2f"},
        color_continuous_scale=["#e3eefb", BLUE, "#0d3b7a"], projection="natural earth")
    fig.update_geos(showframe=False, showcoastlines=False, showcountries=True, countrycolor="#d8d7d2",
                    landcolor="#f1f0ec", bgcolor="rgba(0,0,0,0)", showlakes=False, showocean=False,
                    lataxis_range=[-45, 75])
    fig.update_coloraxes(colorbar=dict(title=metric, thickness=10, len=0.6, tickformat=tick, outlinewidth=0))
    fig = _base(fig, title, height)
    fig.update_layout(hovermode="closest", margin=dict(l=0, r=0, t=48, b=0))
    return fig


def spend_vs_new(monthly: pd.DataFrame, title: str, height: int = 280) -> go.Figure:
    """New customers (bars) with CAC as a separate small chart elsewhere: single axis, no dual-axis."""
    d = monthly
    fig = go.Figure(go.Bar(x=d["month"], y=d["new_customers"], name="New customers",
                           marker=dict(color=BLUE, cornerradius=3),
                           hovertemplate="%{y:,.0f} new customers<extra></extra>"))
    fig.update_xaxes(tickformat="%b %y")
    return _base(fig, title, height)


def channel_cac(df: pd.DataFrame, title: str, height: int = 280) -> go.Figure:
    d = df[df["new_customers"] > 0].copy()
    return hbar(d, "channel", "cac", CHANNEL_COLORS, title, height, fmt="$,.2f")


def churn_cohort_heatmap(heat: pd.DataFrame, title: str, height: int = 360) -> go.Figure:
    """Retention heatmap: rows = first-order quarter, columns = months since first order."""
    if heat.empty:
        return _empty("Not enough data for a retention view", height)
    fig = go.Figure(go.Heatmap(
        z=heat.values, x=[f"M{c}" for c in heat.columns], y=[str(i) for i in heat.index],
        colorscale=["#e3eefb", BLUE, "#0d3b7a"], zmin=0, zmax=1, xgap=2, ygap=2,
        colorbar=dict(title="Retained", thickness=10, tickformat=".0%", outlinewidth=0),
        hovertemplate="Cohort %{y}<br>%{x}: %{z:.0%} still ordering<extra></extra>"))
    fig.update_yaxes(autorange="reversed", gridcolor="rgba(0,0,0,0)")
    fig.update_xaxes(side="top")
    fig = _base(fig, title, height)
    fig.update_layout(hovermode="closest", margin=dict(l=8, r=8, t=70, b=8))
    return fig


def _rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def cohort_retention(orders: pd.DataFrame, max_months: int = 12) -> pd.DataFrame:
    """Share of each first-order-quarter cohort that placed an order k months after their first order."""
    if orders.empty:
        return pd.DataFrame()
    o = orders[["customer_id", "order_date"]].copy()
    first = o.groupby("customer_id")["order_date"].transform("min")
    o["k"] = ((o["order_date"].dt.year - first.dt.year) * 12 + (o["order_date"].dt.month - first.dt.month))
    o["cohort"] = first.dt.to_period("Q")
    o = o[o["k"] <= max_months]
    size = o.groupby("cohort")["customer_id"].nunique()
    act = o.groupby(["cohort", "k"])["customer_id"].nunique().unstack(fill_value=0)
    heat = act.div(size, axis=0)
    # blank out cells that lie beyond the end of the data (cohort too young)
    last = orders["order_date"].max()
    for coh in heat.index:
        age = (last.year - coh.start_time.year) * 12 + (last.month - coh.start_time.month) - 2
        for k in heat.columns:
            if k > age:
                heat.loc[coh, k] = np.nan
    return heat
