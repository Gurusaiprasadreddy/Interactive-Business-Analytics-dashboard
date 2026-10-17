"""Plotly visualization suite for Business Analytics Dashboard.

Provides executive charts adhering to professional visual design standards:
- Cohesive color palettes (Blue for primary revenue, Orange for CAC, Magenta for Churn)
- Recessive grids, readable typography, and unified tooltips
- Interactive geographic choropleths with country code validation
- Histograms, boxplots, correlation matrices, and heatmaps
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Executive Theme Palette
COLOR_PRIMARY_BLUE = "#2a78d6"
COLOR_CAC_ORANGE = "#eb6834"
COLOR_CHURN_MAGENTA = "#e87ba4"
COLOR_SUCCESS_GREEN = "#1baf7a"
COLOR_YELLOW = "#eda100"

CATEGORICAL_COLORS = [COLOR_PRIMARY_BLUE, COLOR_CAC_ORANGE, COLOR_SUCCESS_GREEN, COLOR_YELLOW, COLOR_CHURN_MAGENTA]

COLOR_INK = "#0b0b0b"
COLOR_INK_MUTED = "#52514e"
COLOR_GRID = "#e7e6e2"
COLOR_SURFACE = "#ffffff"

REGIONS = ["North America", "Europe", "Asia Pacific", "Latin America", "Middle East & Africa"]
CATEGORIES = ["Electronics", "Home & Kitchen", "Fashion", "Beauty & Health", "Sports & Outdoors"]
CHANNELS = ["Paid Search", "Social Ads", "Email", "Affiliate", "Organic"]

REGION_COLOR_MAP = dict(zip(REGIONS, CATEGORICAL_COLORS))
CATEGORY_COLOR_MAP = dict(zip(CATEGORIES, CATEGORICAL_COLORS))
CHANNEL_COLOR_MAP = dict(zip(CHANNELS, CATEGORICAL_COLORS))


def _apply_base_layout(fig: go.Figure, title: str | None = None, height: int = 350, show_legend: bool = False) -> go.Figure:
    """Apply consistent styling, margins, fonts, and gridlines to a Plotly figure."""
    fig.update_layout(
        title=dict(text=title, x=0, xanchor="left", font=dict(size=14, color=COLOR_INK, family="Segoe UI, Inter, sans-serif")) if title else None,
        height=height,
        margin=dict(l=10, r=10, t=46 if title else 12, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Segoe UI, Inter, Arial, sans-serif", size=12, color=COLOR_INK_MUTED),
        showlegend=show_legend,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, title=None),
        hoverlabel=dict(bgcolor="white", font_size=12, font_color=COLOR_INK),
    )
    fig.update_xaxes(showgrid=False, linecolor=COLOR_GRID, tickcolor=COLOR_GRID, zeroline=False)
    fig.update_yaxes(gridcolor=COLOR_GRID, zeroline=False, showline=False)
    return fig


def _create_empty_figure(message: str, height: int = 300) -> go.Figure:
    """Return a clean placeholder figure when no records match filter criteria."""
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        showarrow=False,
        font=dict(size=13, color=COLOR_INK_MUTED),
    )
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return _apply_base_layout(fig, None, height)


# -------------------------------------------------------------------------
# Executive Overview Visualizations
# -------------------------------------------------------------------------

def plot_revenue_area(
    df: pd.DataFrame,
    title: str = "Revenue Trend",
    height: int = 350,
    granularity: str = "Month",
) -> go.Figure:
    """Plot an executive time-series area chart of revenue."""
    if df.empty or "revenue" not in df.columns:
        return _create_empty_figure("No revenue data available for current selection", height)

    valid_df = df.dropna(subset=["revenue"])
    if valid_df.empty:
        return _create_empty_figure("No revenue data available for current selection", height)

    fig = go.Figure(
        go.Scatter(
            x=valid_df["month"],
            y=valid_df["revenue"],
            mode="lines+markers" if len(valid_df) <= 18 else "lines",
            name="Revenue",
            line=dict(color=COLOR_PRIMARY_BLUE, width=2.5),
            marker=dict(size=6, color=COLOR_PRIMARY_BLUE, line=dict(width=1.5, color=COLOR_SURFACE)),
            fill="tozeroy",
            fillcolor="rgba(42, 120, 214, 0.15)",
            hovertemplate="<b>Revenue</b>: $%{y:,.0f}<extra></extra>",
        )
    )

    if granularity == "Quarter":
        labels = valid_df["month"].dt.to_period("Q").astype(str)
        fig.update_traces(customdata=labels, hovertemplate="%{customdata}<br><b>Revenue</b>: $%{y:,.0f}<extra></extra>")
        fig.update_xaxes(tickmode="array", tickvals=valid_df["month"], ticktext=labels)
    elif granularity == "Year":
        years = valid_df["month"].dt.year.astype(str)
        fig.update_xaxes(tickmode="array", tickvals=valid_df["month"], ticktext=years)
    else:
        fig.update_xaxes(tickformat="%b %y")

    fig.update_yaxes(tickformat="$~s", rangemode="tozero")
    return _apply_base_layout(fig, title, height)


def plot_metric_trend(
    df: pd.DataFrame,
    metric_col: str,
    title: str,
    color: str = COLOR_PRIMARY_BLUE,
    height: int = 240,
    is_currency: bool = True,
    is_percent: bool = False,
    granularity: str = "Month",
) -> go.Figure:
    """Plot metric trendline with unified hover and zero baseline."""
    if df.empty or metric_col not in df.columns:
        return _create_empty_figure(f"No {title} data available", height)

    valid_df = df.dropna(subset=[metric_col])
    if valid_df.empty:
        return _create_empty_figure(f"No {title} data available", height)

    if is_currency:
        hover_fmt = "$%{y:,.2f}"
        tick_fmt = "$~s"
    elif is_percent:
        hover_fmt = "%{y:.1%}"
        tick_fmt = ".0%"
    else:
        hover_fmt = "%{y:,.0f}"
        tick_fmt = "~s"

    fig = go.Figure(
        go.Scatter(
            x=valid_df["month"],
            y=valid_df[metric_col],
            mode="lines+markers" if len(valid_df) <= 18 else "lines",
            name=title,
            line=dict(color=color, width=2),
            marker=dict(size=5, color=color, line=dict(width=1.5, color=COLOR_SURFACE)),
            fill="tozeroy",
            fillcolor=f"rgba({int(color[1:3], 16)}, {int(color[3:5], 16)}, {int(color[5:7], 16)}, 0.12)",
            hovertemplate=f"<b>{title}</b>: {hover_fmt}<extra></extra>",
        )
    )

    if granularity == "Quarter":
        labels = valid_df["month"].dt.to_period("Q").astype(str)
        fig.update_traces(customdata=labels, hovertemplate=f"%{{customdata}}<br><b>{title}</b>: {hover_fmt}<extra></extra>")
        fig.update_xaxes(tickmode="array", tickvals=valid_df["month"], ticktext=labels)
    elif granularity == "Year":
        years = valid_df["month"].dt.year.astype(str)
        fig.update_xaxes(tickmode="array", tickvals=valid_df["month"], ticktext=years)
    else:
        fig.update_xaxes(tickformat="%b %y")

    fig.update_yaxes(tickformat=tick_fmt, rangemode="tozero")
    return _apply_base_layout(fig, title, height)


def plot_stacked_area(
    df: pd.DataFrame,
    dimension_col: str,
    color_map: dict[str, str],
    title: str,
    height: int = 340,
) -> go.Figure:
    """Stacked revenue area chart grouped by region, category, or channel."""
    if df.empty or dimension_col not in df.columns:
        return _create_empty_figure("No breakdown data available", height)

    fig = go.Figure()
    unique_keys = [k for k in color_map if k in set(df[dimension_col])]
    if not unique_keys:
        unique_keys = sorted(df[dimension_col].unique())

    for key in unique_keys:
        subset = df[df[dimension_col] == key]
        c = color_map.get(key, COLOR_PRIMARY_BLUE)
        fig.add_trace(
            go.Scatter(
                x=subset["month"],
                y=subset["revenue"],
                name=key,
                stackgroup="revenue_stack",
                mode="lines",
                line=dict(width=1, color=COLOR_SURFACE),
                fillcolor=f"rgba({int(c[1:3], 16)}, {int(c[3:5], 16)}, {int(c[5:7], 16)}, 0.88)",
                hovertemplate=f"<b>{key}</b>: $%{{y:,.0f}}<extra></extra>",
            )
        )

    fig.update_xaxes(tickformat="%b %y")
    fig.update_yaxes(tickformat="$~s")
    return _apply_base_layout(fig, title, height, show_legend=True)


# -------------------------------------------------------------------------
# Geographic & Regional Visualizations
# -------------------------------------------------------------------------

def plot_geo_choropleth(
    country_df: pd.DataFrame,
    metric: str = "Revenue",
    title: str = "Global Revenue by Country",
    height: int = 440,
) -> go.Figure:
    """Interactive choropleth map using ISO-3 codes with country-level statistics."""
    if country_df.empty or "iso_alpha" not in country_df.columns:
        return _create_empty_figure("No geographic country data available", height)

    metric_mapping = {
        "Revenue": ("revenue", "$~s", ":$,.0f"),
        "Orders": ("orders", "~s", ":,d"),
        "AOV": ("aov", "$~s", ":$,.2f"),
        "Customers": ("customers", "~s", ":,d"),
    }
    col, tick_fmt, hov_format = metric_mapping.get(metric, ("revenue", "$~s", ":$,.0f"))

    fig = px.choropleth(
        country_df,
        locations="iso_alpha",
        color=col,
        hover_name="country",
        hover_data={
            "iso_alpha": False,
            col: False,
            "revenue": ":$,.0f",
            "orders": ":,d",
            "aov": ":$,.2f",
            "customers": ":,d",
        },
        color_continuous_scale=["#e3eefb", COLOR_PRIMARY_BLUE, "#0d3b7a"],
        projection="natural earth",
    )
    fig.update_geos(
        showframe=False,
        showcoastlines=False,
        showcountries=True,
        countrycolor="#d8d7d2",
        landcolor="#f6f5f1",
        bgcolor="rgba(0,0,0,0)",
        showlakes=False,
        showocean=False,
    )
    fig.update_coloraxes(
        colorbar=dict(title=metric, thickness=12, len=0.6, tickformat=tick_fmt, outlinewidth=0)
    )
    fig = _apply_base_layout(fig, title, height)
    fig.update_layout(hovermode="closest", margin=dict(l=0, r=0, t=46, b=0))
    return fig


def plot_horizontal_bars(
    df: pd.DataFrame,
    category_col: str,
    value_col: str,
    color_map: dict[str, str] | None = None,
    title: str = "",
    height: int = 320,
    fmt: str = "$,.0f",
    default_color: str = COLOR_PRIMARY_BLUE,
) -> go.Figure:
    """Styled horizontal bar chart."""
    if df.empty or category_col not in df.columns or value_col not in df.columns:
        return _create_empty_figure(f"No data available for {title}", height)

    sorted_df = df.sort_values(value_col, ascending=True)
    colors = (
        [color_map.get(k, default_color) for k in sorted_df[category_col]]
        if color_map
        else default_color
    )

    fig = go.Figure(
        go.Bar(
            x=sorted_df[value_col],
            y=sorted_df[category_col],
            orientation="h",
            marker=dict(color=colors, cornerradius=4),
            text=sorted_df[value_col],
            texttemplate="%{text:" + fmt + "}",
            textposition="outside",
            cliponaxis=False,
            hovertemplate="<b>%{y}</b><br>%{x:" + fmt + "}<extra></extra>",
        )
    )
    fig.update_xaxes(visible=False, range=[0, sorted_df[value_col].max() * 1.25 if not sorted_df.empty else 1])
    fig.update_yaxes(gridcolor="rgba(0,0,0,0)", automargin=True)
    fig = _apply_base_layout(fig, title, height)
    fig.update_layout(hovermode="closest", bargap=0.32, margin=dict(l=10, r=40, t=46 if title else 12, b=10))
    return fig


def plot_regional_monthly_heatmap(
    df: pd.DataFrame,
    title: str = "Monthly Regional Revenue Heatmap",
    height: int = 340,
) -> go.Figure:
    """Heatmap matrix of Revenue by Region and Month."""
    if df.empty:
        return _create_empty_figure("No regional trend data available", height)

    pivot = df.pivot(index="region", columns="month", values="revenue").fillna(0)
    month_labels = [m.strftime("%b %y") for m in pivot.columns]

    fig = go.Figure(
        go.Heatmap(
            z=pivot.values,
            x=month_labels,
            y=pivot.index,
            colorscale=["#f7fbff", "#9ecae1", COLOR_PRIMARY_BLUE, "#08306b"],
            colorbar=dict(title="Revenue", tickformat="$~s", thickness=12, outlinewidth=0),
            hovertemplate="<b>%{y}</b> (%{x})<br>Revenue: $%{z:,.0f}<extra></extra>",
        )
    )
    fig.update_xaxes(side="bottom")
    fig.update_yaxes(gridcolor="rgba(0,0,0,0)")
    return _apply_base_layout(fig, title, height)


# -------------------------------------------------------------------------
# Products & Acquisition Visualizations
# -------------------------------------------------------------------------

def plot_revenue_histogram(
    df: pd.DataFrame,
    title: str = "Order-Line Revenue Distribution",
    height: int = 350,
) -> go.Figure:
    """Distribution of order-line revenue with box marginal and calibrated bins."""
    if df.empty or "revenue" not in df.columns:
        return _create_empty_figure("No revenue data available", height)

    fig = px.histogram(
        df,
        x="revenue",
        nbins=40,
        marginal="box",
        title=title,
        color_discrete_sequence=[COLOR_PRIMARY_BLUE],
        labels={"revenue": "Order-Line Revenue ($)"},
    )
    fig.update_layout(bargap=0.08)
    fig.update_xaxes(tickformat="$~s")
    fig.update_yaxes(title="Count", gridcolor=COLOR_GRID)
    return _apply_base_layout(fig, title, height)


def plot_unit_price_histogram(
    df: pd.DataFrame,
    title: str = "Unit Price Distribution by Category",
    height: int = 380,
) -> go.Figure:
    """Unit price distribution across product categories."""
    if df.empty or "unit_price" not in df.columns or "product_category" not in df.columns:
        return _create_empty_figure("No unit price data available", height)

    fig = px.histogram(
        df,
        x="unit_price",
        color="product_category",
        color_discrete_map=CATEGORY_COLOR_MAP,
        nbins=35,
        barmode="overlay",
        opacity=0.65,
        title=title,
        labels={"unit_price": "Unit Price ($)", "product_category": "Category"},
    )
    fig.update_xaxes(tickformat="$~s")
    fig.update_yaxes(title="Count", gridcolor=COLOR_GRID)
    return _apply_base_layout(fig, title, height, show_legend=True)


def plot_boxplots(
    df: pd.DataFrame,
    y_col: str,
    title: str,
    height: int = 380,
    is_currency: bool = True,
) -> go.Figure:
    """Box plots showing median, IQR, and statistical outliers by product category."""
    if df.empty or y_col not in df.columns or "product_category" not in df.columns:
        return _create_empty_figure(f"No {y_col} data available", height)

    fig = px.box(
        df,
        x="product_category",
        y=y_col,
        color="product_category",
        color_discrete_map=CATEGORY_COLOR_MAP,
        points="outliers",
        title=title,
        labels={"product_category": "Category", y_col: y_col.replace("_", " ").title()},
    )
    if is_currency:
        fig.update_yaxes(tickformat="$~s")
    return _apply_base_layout(fig, title, height, show_legend=False)


def plot_category_scatter(
    category_df: pd.DataFrame,
    title: str = "Category Volume vs. Revenue Performance",
    height: int = 360,
) -> go.Figure:
    """Scatter plot: Distinct Orders vs Revenue with bubble size reflecting Units Sold."""
    if category_df.empty:
        return _create_empty_figure("No category performance data", height)

    fig = px.scatter(
        category_df,
        x="orders",
        y="revenue",
        size="units",
        color="product_category",
        color_discrete_map=CATEGORY_COLOR_MAP,
        hover_name="product_category",
        title=title,
        labels={
            "orders": "Distinct Orders",
            "revenue": "Total Revenue ($)",
            "units": "Units Sold",
            "product_category": "Category",
        },
    )
    fig.update_xaxes(tickformat="~s")
    fig.update_yaxes(tickformat="$~s")
    return _apply_base_layout(fig, title, height, show_legend=True)


def plot_spend_and_new_customers(
    monthly_df: pd.DataFrame,
    title: str = "New Customers Acquired Monthly",
    height: int = 280,
) -> go.Figure:
    """Monthly new customer bar chart."""
    if monthly_df.empty or "new_customers" not in monthly_df.columns:
        return _create_empty_figure("No acquisition data available", height)

    fig = go.Figure(
        go.Bar(
            x=monthly_df["month"],
            y=monthly_df["new_customers"],
            name="New Customers",
            marker=dict(color=COLOR_PRIMARY_BLUE, cornerradius=4),
            hovertemplate="%{x|%b %Y}<br><b>New Customers</b>: %{y:,d}<extra></extra>",
        )
    )
    fig.update_xaxes(tickformat="%b %y")
    fig.update_yaxes(tickformat="~s")
    return _apply_base_layout(fig, title, height)


def plot_cohort_retention_heatmap(
    retention_matrix: pd.DataFrame,
    title: str = "Customer Retention Heatmap by Cohort",
    height: int = 350,
) -> go.Figure:
    """Cohort retention heatmap: Rows = First-order quarter, Columns = Month k re-order rate."""
    if retention_matrix.empty:
        return _create_empty_figure("Insufficient data for customer cohort analysis", height)

    fig = go.Figure(
        go.Heatmap(
            z=retention_matrix.values,
            x=[f"Month {c}" for c in retention_matrix.columns],
            y=[str(idx) for idx in retention_matrix.index],
            colorscale=["#e3eefb", COLOR_PRIMARY_BLUE, "#0d3b7a"],
            zmin=0,
            zmax=1,
            xgap=2,
            ygap=2,
            colorbar=dict(title="Retention", thickness=12, tickformat=".0%", outlinewidth=0),
            hovertemplate="Cohort %{y}<br>%{x}: %{z:.1%} re-ordered<extra></extra>",
        )
    )
    fig.update_yaxes(autorange="reversed", gridcolor="rgba(0,0,0,0)")
    fig.update_xaxes(side="top")
    fig = _apply_base_layout(fig, title, height)
    fig.update_layout(hovermode="closest", margin=dict(l=10, r=10, t=70, b=10))
    return fig


def plot_correlation_matrix(
    df: pd.DataFrame,
    title: str = "Correlation Heatmap (Sales Metrics)",
    height: int = 340,
) -> go.Figure:
    """Correlation matrix between numerical transaction attributes."""
    numeric_cols = [c for c in ["quantity", "unit_price", "discount", "revenue"] if c in df.columns]
    if len(numeric_cols) < 2 or df.empty:
        return _create_empty_figure("Insufficient numeric fields for correlation", height)

    corr = df[numeric_cols].corr()
    fig = px.imshow(
        corr,
        text_auto=".2f",
        zmin=-1,
        zmax=1,
        color_continuous_scale="RdBu_r",
        title=title,
    )
    return _apply_base_layout(fig, title, height)


def plot_weekday_performance(
    df: pd.DataFrame,
    title: str = "Revenue Performance by Day of Week",
    height: int = 320,
) -> go.Figure:
    """Weekly sales distribution by day of week."""
    if df.empty or "order_date" not in df.columns:
        return _create_empty_figure("No date data available", height)

    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    temp = df.copy()
    temp["day_name"] = temp["order_date"].dt.day_name()
    grouped = temp.groupby("day_name", as_index=False)["revenue"].sum()
    grouped["day_name"] = pd.Categorical(grouped["day_name"], categories=days, ordered=True)
    grouped = grouped.sort_values("day_name")

    fig = go.Figure(
        go.Bar(
            x=grouped["day_name"],
            y=grouped["revenue"],
            marker=dict(color=COLOR_PRIMARY_BLUE, cornerradius=4),
            hovertemplate="<b>%{x}</b><br>Revenue: $%{y:,.0f}<extra></extra>",
        )
    )
    fig.update_yaxes(tickformat="$~s")
    return _apply_base_layout(fig, title, height)
