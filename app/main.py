"""Business Analytics & KPI Dashboard - Streamlit Application.

Interactive executive dashboard for e-commerce performance:
- Executive Overview (KPIs, Deltas, Trends, Automated Insights)
- Geography and Regions (Global Choropleth, Regional Bars, Heatmaps, Country Drill-Downs)
- Products and Acquisition (Category Comparisons, Scatter, Histograms, Boxplots, Channels, CAC, Cohort Retention)
- Data Quality & Export (Cleaning Audit, CSV & PDF Reporting)

Run with:
    streamlit run app/main.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
import streamlit as st

from app import charts, pipeline
from app.cleaning import DataValidationError, load_and_clean
from app.insights import build_insights
from app.pipeline import Filters
from src import visualizations as src_viz

# ------------------------------------------------------------------ Page Config & Styling
st.set_page_config(
    page_title="Executive Business Analytics Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      .block-container {padding-top: 1.4rem; padding-bottom: 2rem; max-width: 1440px;}
      h1 {font-size: 1.85rem !important; margin-bottom: 0.15rem !important; font-weight: 700 !important; color: #0f172a;}
      h2 {font-size: 1.35rem !important; font-weight: 600 !important; margin-top: 1rem !important; color: #1e293b;}
      h3 {font-size: 1.1rem !important; font-weight: 600 !important; color: #334155;}
      [data-testid="stMetric"] {
          background: #ffffff;
          border-radius: 8px;
          padding: 10px 14px;
          box-shadow: 0 1px 3px rgba(0,0,0,0.04);
      }
      .insight-box {
          border-left: 3.5px solid #2a78d6;
          padding: 8px 12px;
          margin-bottom: 10px;
          background: #f8fafc;
          border-radius: 0 6px 6px 0;
          box-shadow: 0 1px 2px rgba(0,0,0,0.02);
      }
      .insight-box b {color: #0f172a; font-size: 0.92rem; display: block;}
      .insight-box span {color: #475569; font-size: 0.84rem; display: block; margin-top: 2px; line-height: 1.35;}
      .stTabs [data-baseweb="tab-list"] {gap: 8px;}
      .stTabs [data-baseweb="tab"] {padding-top: 8px; padding-bottom: 8px; font-weight: 500;}
    </style>
    """,
    unsafe_allow_html=True,
)


# ------------------------------------------------------------------ Data Loading
@st.cache_data(show_spinner="Loading and verifying data…")
def get_dashboard_data():
    return load_and_clean(save=False)


try:
    orders, marketing, quality_report = get_dashboard_data()
except DataValidationError as exc:
    st.error(f"**Data Validation Error:** {exc}")
    st.stop()
except Exception as exc:
    st.error(f"Unexpected data loading error: {exc}")
    st.stop()

# Available options for filters
months_range = list(
    pd.date_range(
        orders["order_date"].min().to_period("M").to_timestamp(),
        orders["order_date"].max().to_period("M").to_timestamp(),
        freq="MS",
    )
)
month_labels = {m: m.strftime("%b %Y") for m in months_range}

all_regions = [r for r in charts.REGIONS if r in set(orders["region"])] + sorted(
    set(orders["region"]) - set(charts.REGIONS)
)
all_categories = [c for c in charts.CATEGORIES if c in set(orders["product_category"])] + sorted(
    set(orders["product_category"]) - set(charts.CATEGORIES)
)
all_channels = [c for c in charts.CHANNELS if c in set(orders["acquisition_channel"])] + sorted(
    set(orders["acquisition_channel"]) - set(charts.CHANNELS)
)

DEFAULTS = {
    "f_months": (months_range[max(len(months_range) - 12, 0)], months_range[-1]),
    "f_regions": all_regions,
    "f_cats": all_categories,
    "f_chans": all_channels,
    "f_gran": "Month",
}


def reset_all_filters():
    for key, val in DEFAULTS.items():
        st.session_state[key] = val


# ------------------------------------------------------------------ Sidebar: Navigation & Filters
with st.sidebar:
    st.markdown("### 🧭 Dashboard Navigation")
    current_page = st.radio(
        "Select Page",
        options=[
            "Page 1 — Executive Overview",
            "Page 2 — Geography and Regions",
            "Page 3 — Products and Acquisition",
            "Page 4 — Data Quality & Exports",
        ],
        index=0,
        label_visibility="collapsed",
    )

    st.markdown("---")
    st.markdown("### 🔍 Global Filters")

    st.select_slider(
        "Reporting Period",
        options=months_range,
        value=st.session_state.get("f_months", DEFAULTS["f_months"]),
        key="f_months",
        format_func=month_labels.get,
        help="Filter transactions by date range. All dates in the selected ending month are included.",
    )

    selected_regions = st.multiselect(
        "Region",
        options=all_regions,
        default=st.session_state.get("f_regions", DEFAULTS["f_regions"]),
        key="f_regions",
    )

    selected_categories = st.multiselect(
        "Product Category",
        options=all_categories,
        default=st.session_state.get("f_cats", DEFAULTS["f_cats"]),
        key="f_cats",
    )

    selected_channels = st.multiselect(
        "Acquisition Channel",
        options=all_channels,
        default=st.session_state.get("f_chans", DEFAULTS["f_chans"]),
        key="f_chans",
    )

    granularity = st.radio(
        "Time Aggregation",
        options=["Month", "Quarter", "Year"],
        index=["Month", "Quarter", "Year"].index(st.session_state.get("f_gran", "Month")),
        key="f_gran",
        horizontal=True,
        help="Date drill-down: Aggregate trendlines by Month, Quarter, or Year.",
    )

    st.button("↺ Reset Filters", on_click=reset_all_filters, use_container_width=True)

# Validate filter selections
f_start, f_end = st.session_state["f_months"]
if not (selected_regions and selected_categories and selected_channels):
    st.warning("⚠️ Please select at least one region, category, and acquisition channel to display analytics.")
    st.stop()

# Build filter object and run computation pipeline
# End date includes the entire month through 23:59:59
full_month_end = pipeline.month_end(f_end) + pd.Timedelta(hours=23, minutes=59, seconds=59)
filters = Filters(
    start=f_start,
    end=full_month_end,
    regions=selected_regions,
    categories=selected_categories,
    channels=selected_channels,
)

try:
    res = pipeline.compute(orders, marketing, filters)
except Exception as exc:
    st.error(f"Calculation error for current filter selection: {exc}")
    st.stop()

# Header caption
st.title("Interactive Business Analytics & KPI Dashboard")
st.caption(
    f"Reporting Period: **{f_start:%b %Y} – {f_end:%b %Y}** · "
    f"Scope: **{len(filters.regions)}** region(s) · **{len(filters.categories)}** category(ies) · **{len(filters.channels)}** channel(s)"
)

if res.empty:
    st.info("ℹ️ No transactions match the current filter combination. Try expanding the date range or enabling more regions/categories.")
    st.stop()

h, p = res.head, res.prev_head
trend = pipeline.regroup(res.monthly, granularity)
mon = res.monthly


# Helper for rendering KPI cards
def render_kpi(col, label, value, series, cur, prev, inverse=False, pp=False, help_text=None, show_spark=True):
    if prev is None:
        delta = None
    elif pp:
        delta = f"{(cur - prev) * 100:+.1f} pp"
    else:
        delta = pipeline.pct_delta(cur, prev)
    with col:
        with st.container(border=True):
            st.metric(
                label=label,
                value=value,
                delta=delta,
                delta_color="inverse" if inverse else "normal",
                help=help_text,
            )


# ==============================================================================
# PAGE 1 — EXECUTIVE OVERVIEW
# ==============================================================================
if current_page == "Page 1 — Executive Overview":
    st.markdown("## Executive Performance Overview")

    # Primary Executive KPI Cards
    k1, k2, k3, k4 = st.columns(4)
    render_kpi(
        k1,
        "Total Revenue",
        f"${h.revenue:,.0f}",
        mon["revenue"],
        h.revenue,
        p and p.revenue,
        help_text="Sum of line revenue: quantity × unit price × (1 − discount)",
    )
    render_kpi(
        k2,
        "Average Order Value (AOV)",
        f"${h.aov:,.2f}",
        mon["aov"],
        h.aov,
        p and p.aov,
        help_text="Net revenue divided by distinct order IDs",
    )
    render_kpi(
        k3,
        "Customer Acquisition Cost (CAC)",
        f"${h.cac:,.2f}" if h.new_customers else "N/A",
        mon["cac"],
        h.cac,
        p and p.cac,
        inverse=True,
        help_text="Marketing spend divided by newly acquired customers. Lower is better.",
    )
    churn_str = f"{h.churn_rate:.1%}" if (h.churn_rate == h.churn_rate and not np.isnan(h.churn_rate)) else "N/A"
    render_kpi(
        k4,
        "Customer Churn Rate",
        churn_str,
        mon["churn_rate"],
        h.churn_rate,
        p and p.churn_rate,
        inverse=True,
        pp=True,
        help_text="90-day inactivity proxy: Monthly share of customers with no order for >= 90 days. First 120 days excluded for warm-up.",
    )

    # Secondary Operational Metrics
    s1, s2, s3, s4 = st.columns(4)
    render_kpi(s1, "Distinct Orders", f"{h.orders:,}", mon["orders"], h.orders, p and p.orders, show_spark=False)
    render_kpi(s2, "New Customers", f"{h.new_customers:,}", mon["new_customers"], h.new_customers, p and p.new_customers, show_spark=False)
    render_kpi(s3, "Marketing Spend", f"${h.spend:,.0f}", mon["spend"], h.spend, p and p.spend, show_spark=False)
    render_kpi(s4, "Active Customers", f"{h.active_customers:,}", mon["active_customers"], h.active_customers, p and p.active_customers, show_spark=False)

    if p is None:
        st.caption("ℹ️ Deltas compare against the immediately preceding period of equal length (unavailable if preceding period begins prior to dataset start).")
    else:
        st.caption("ℹ️ Deltas indicate change compared to the preceding period of identical duration.")

    # Main Revenue Trend Area Chart + Automated Insights
    row1_left, row1_right = st.columns([2, 1], gap="medium")
    with row1_left:
        st.plotly_chart(
            charts.area_trend(trend, "Revenue", f"Revenue Performance ({granularity} Aggregation)", 440, granularity=granularity),
            use_container_width=True,
        )

    with row1_right:
        st.markdown("### 💡 Executive Insights")
        ch_table = pipeline.channel_table(res)
        insights = build_insights(res, ch_table)
        for headline, detail in insights[:5]:
            st.markdown(
                f'<div class="insight-box"><b>{headline}</b><span>{detail}</span></div>',
                unsafe_allow_html=True,
            )

    # Secondary Trendlines: AOV, CAC, Churn
    st.markdown("### 📈 Key Metric Trends")
    t1, t2, t3 = st.columns(3)
    with t1:
        st.plotly_chart(
            charts.area_trend(trend, "AOV", f"AOV Trend ({granularity})", 260, granularity=granularity),
            use_container_width=True,
        )
    with t2:
        st.plotly_chart(
            charts.area_trend(trend, "CAC", f"CAC Trend ({granularity})", 260, color=charts.ORANGE, granularity=granularity),
            use_container_width=True,
        )
    with t3:
        st.plotly_chart(
            charts.area_trend(trend, "Churn rate", f"Churn / Inactivity Rate ({granularity})", 260, color=charts.MAGENTA, granularity=granularity),
            use_container_width=True,
        )

    # Stacked Revenue Breakdown
    st.markdown("### 🥞 Revenue Composition Over Time")
    split_choice = st.radio("Group Revenue By:", ["Region", "Product category", "Acquisition channel"], horizontal=True)
    dim_name, color_map = {
        "Region": ("region", charts.REGION_COLORS),
        "Product category": ("product_category", charts.CATEGORY_COLORS),
        "Acquisition channel": ("acquisition_channel", charts.CHANNEL_COLORS),
    }[split_choice]

    st.plotly_chart(
        charts.stacked_area(
            pipeline.revenue_by(res, dim_name, granularity),
            dim_name,
            color_map,
            f"Revenue by {split_choice} ({granularity})",
            340,
        ),
        use_container_width=True,
    )


# ==============================================================================
# PAGE 2 — GEOGRAPHY AND REGIONS
# ==============================================================================
elif current_page == "Page 2 — Geography and Regions":
    st.markdown("## Geographic & Regional Distribution")

    g_ctrl1, g_ctrl2 = st.columns([1, 1])
    with g_ctrl1:
        map_metric = st.radio("Map Metric:", ["Revenue", "Orders", "AOV"], horizontal=True)
    with g_ctrl2:
        available_regions = ["All regions"] + sorted(res.in_period["region"].unique())
        selected_drill_region = st.selectbox("Drill Down Region:", available_regions)

    ctab = pipeline.country_table(res, selected_drill_region)

    m1, m2 = st.columns([3, 2], gap="medium")
    with m1:
        map_title = f"{map_metric} by Country" + ("" if selected_drill_region == "All regions" else f" · {selected_drill_region}")
        fig_map = charts.geo_map(ctab, map_metric, map_title, height=440)
        if selected_drill_region != "All regions":
            fig_map.update_geos(fitbounds="locations")
        st.plotly_chart(fig_map, use_container_width=True)

    with m2:
        if selected_drill_region == "All regions":
            reg_totals = res.in_period.groupby("region", as_index=False)["revenue"].sum()
            st.plotly_chart(
                charts.region_bars(reg_totals, "Revenue by Region", height=440),
                use_container_width=True,
            )
        else:
            st.plotly_chart(
                charts.hbar(ctab, "country", "revenue", None, f"Revenue by Country · {selected_drill_region}", height=440),
                use_container_width=True,
            )

    # Monthly Regional Revenue Heatmap
    st.markdown("### 🗺️ Monthly Regional Revenue Heatmap")
    regional_monthly = (
        res.in_period.groupby(["region", "month"], as_index=False)["revenue"]
        .sum()
    )
    st.plotly_chart(
        src_viz.plot_regional_monthly_heatmap(regional_monthly, height=320),
        use_container_width=True,
    )

    # Country Data Table
    st.markdown("### 📋 Country Performance Summary")
    if not ctab.empty:
        table_view = ctab[["country", "revenue", "orders", "aov", "customers"]].rename(
            columns={"country": "Country", "revenue": "Revenue", "orders": "Orders", "aov": "AOV", "customers": "Customers"}
        )
        st.dataframe(
            table_view,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Revenue": st.column_config.NumberColumn(format="$%,.0f"),
                "AOV": st.column_config.NumberColumn(format="$%,.2f"),
                "Orders": st.column_config.NumberColumn(format="%,d"),
                "Customers": st.column_config.NumberColumn(format="%,d"),
            },
        )


# ==============================================================================
# PAGE 3 — PRODUCTS AND ACQUISITION
# ==============================================================================
elif current_page == "Page 3 — Products and Acquisition":
    st.markdown("## Products & Customer Acquisition Analysis")

    from app import kpis
    cat_summary = kpis.by_dimension(res.in_period, "product_category")

    # Category Bar Charts
    c1, c2 = st.columns(2, gap="medium")
    with c1:
        st.plotly_chart(
            charts.hbar(cat_summary, "product_category", "revenue", charts.CATEGORY_COLORS, "Revenue by Product Category", 300),
            use_container_width=True,
        )
    with c2:
        st.plotly_chart(
            charts.hbar(cat_summary, "product_category", "aov", charts.CATEGORY_COLORS, "Average Order Value by Category", 300, fmt="$,.2f"),
            use_container_width=True,
        )

    # Product Drill-Down
    st.markdown("### 🔎 Product Drill-Down")
    selected_drill_cat = st.selectbox("Filter Products by Category:", ["All categories"] + list(cat_summary["product_category"]))
    prod_data = res.in_period if selected_drill_cat == "All categories" else res.in_period[res.in_period["product_category"] == selected_drill_cat]
    prod_table = kpis.by_dimension(prod_data, ["product_category", "product_name"])
    prod_table["label"] = prod_table["product_name"]

    p_col1, p_col2 = st.columns([1, 1], gap="medium")
    with p_col1:
        top_prods = prod_table.head(10)
        st.plotly_chart(
            charts.hbar(top_prods, "label", "revenue", None, f"Top Products by Revenue ({selected_drill_cat})", max(300, 28 * len(top_prods) + 80)),
            use_container_width=True,
        )
    with p_col2:
        st.dataframe(
            prod_table[["product_category", "product_name", "revenue", "units", "aov"]].rename(
                columns={"product_category": "Category", "product_name": "Product", "revenue": "Revenue", "units": "Units Sold", "aov": "AOV"}
            ),
            hide_index=True,
            use_container_width=True,
            height=max(300, 28 * len(top_prods) + 80),
            column_config={
                "Revenue": st.column_config.NumberColumn(format="$%,.0f"),
                "AOV": st.column_config.NumberColumn(format="$%,.2f"),
                "Units Sold": st.column_config.NumberColumn(format="%,d"),
            },
        )

    # Category Volume vs Revenue Scatter
    st.markdown("### ⚖️ Category Performance: Order Volume vs. Revenue")
    st.plotly_chart(
        src_viz.plot_category_scatter(cat_summary, height=360),
        use_container_width=True,
    )

    # Histograms & Box Plots
    st.markdown("### 📊 Distribution & Outlier Analysis")
    h1, h2 = st.columns(2, gap="medium")
    with h1:
        st.plotly_chart(
            src_viz.plot_revenue_histogram(res.in_period, height=360),
            use_container_width=True,
        )
    with h2:
        st.plotly_chart(
            src_viz.plot_unit_price_histogram(res.in_period, height=360),
            use_container_width=True,
        )

    b1, b2 = st.columns(2, gap="medium")
    with b1:
        st.plotly_chart(
            src_viz.plot_boxplots(res.in_period, "revenue", "Order-Line Revenue Box Plots (Outliers)", height=360),
            use_container_width=True,
        )
    with b2:
        st.plotly_chart(
            src_viz.plot_boxplots(res.in_period, "unit_price", "Unit Price Box Plots by Category", height=360),
            use_container_width=True,
        )

    # Acquisition & Retention
    st.markdown("### 🎯 Acquisition Channels & Cohort Retention")
    ch_tab = pipeline.channel_table(res)

    a1, a2 = st.columns(2, gap="medium")
    with a1:
        st.plotly_chart(
            charts.spend_vs_new(mon, "New Customers Acquired Monthly", 300),
            use_container_width=True,
        )
    with a2:
        st.plotly_chart(
            charts.channel_cac(ch_tab, "CAC by Acquisition Channel (Lower is Better)", 300),
            use_container_width=True,
        )

    # Channel Summary Table
    st.dataframe(
        ch_tab.rename(columns={"channel": "Channel", "spend": "Marketing Spend", "new_customers": "New Customers", "cac": "CAC"}),
        hide_index=True,
        use_container_width=True,
        column_config={
            "Marketing Spend": st.column_config.NumberColumn(format="$%,.0f"),
            "CAC": st.column_config.NumberColumn(format="$%,.2f"),
            "New Customers": st.column_config.NumberColumn(format="%,d"),
        },
    )

    # Retention Heatmap
    st.plotly_chart(
        charts.churn_cohort_heatmap(
            charts.cohort_retention(res.scope),
            "Quarterly Cohort Retention Heatmap (% of Cohort Re-ordering in Month k)",
        ),
        use_container_width=True,
    )
    st.caption("ℹ️ Cohort retention evaluates full customer ordering history independently of the date filter to maintain comparable longitudinal cohorts.")

    # Correlation Matrix & Weekday Analysis
    c_m1, c_m2 = st.columns(2, gap="medium")
    with c_m1:
        st.plotly_chart(
            src_viz.plot_correlation_matrix(res.in_period, height=340),
            use_container_width=True,
        )
    with c_m2:
        st.plotly_chart(
            src_viz.plot_weekday_performance(res.in_period, height=340),
            use_container_width=True,
        )


# ==============================================================================
# PAGE 4 — DATA QUALITY & EXPORTS
# ==============================================================================
elif current_page == "Page 4 — Data Quality & Exports":
    st.markdown("## Data Quality, Methodology & Report Exports")

    st.markdown("### 📄 Monthly KPI Table")
    kpi_export_df = mon[[
        "month", "revenue", "orders", "aov", "new_customers", "spend", "cac", "base_customers", "churned", "churn_rate"
    ]].copy()
    kpi_export_df["month"] = kpi_export_df["month"].dt.strftime("%Y-%m")

    st.dataframe(
        kpi_export_df,
        hide_index=True,
        use_container_width=True,
        column_config={
            "revenue": st.column_config.NumberColumn("Revenue", format="$%,.0f"),
            "orders": st.column_config.NumberColumn("Orders", format="%,d"),
            "aov": st.column_config.NumberColumn("AOV", format="$%,.2f"),
            "new_customers": st.column_config.NumberColumn("New Customers", format="%,d"),
            "spend": st.column_config.NumberColumn("Marketing Spend", format="$%,.0f"),
            "cac": st.column_config.NumberColumn("CAC", format="$%,.2f"),
            "base_customers": st.column_config.NumberColumn("Active at Start", format="%,d"),
            "churned": st.column_config.NumberColumn("Churned", format="%,d"),
            "churn_rate": st.column_config.NumberColumn("Churn Rate", format="percent"),
        },
    )

    down1, down2 = st.columns(2)
    down1.download_button(
        "⬇ Download Monthly KPIs (CSV)",
        kpi_export_df.to_csv(index=False).encode("utf-8"),
        "monthly_kpis.csv",
        "text/csv",
        use_container_width=True,
    )
    down2.download_button(
        "⬇ Download Filtered Orders (CSV)",
        res.in_period.to_csv(index=False).encode("utf-8"),
        "filtered_orders.csv",
        "text/csv",
        use_container_width=True,
    )

    st.markdown("---")
    st.markdown("### 📑 PDF Executive Report Export")
    pdf_path = ROOT / "reports" / "dashboard.pdf"
    if pdf_path.exists():
        with open(pdf_path, "rb") as f_pdf:
            pdf_bytes = f_pdf.read()
        st.download_button(
            "⬇ Download Pre-Generated Executive PDF Report (3-Page A4)",
            pdf_bytes,
            "executive_dashboard_report.pdf",
            "application/pdf",
            use_container_width=True,
        )
    else:
        st.info("Run `python scripts/export_pdf.py` to compile the executive PDF report.")

    with st.expander("📐 KPI Definitions, Formulas & Assumptions", expanded=True):
        st.markdown(
            """
            - **Total Revenue**: Sum of line revenue calculated as $\\sum \\text{quantity} \\times \\text{unit\\_price} \\times (1 - \\text{discount})$. Taxes, shipping fees, and customer returns are not present in raw datasets.
            - **Orders & Average Order Value (AOV)**: Distinct count of `order_id` values. $\\text{AOV} = \\frac{\\text{Total Revenue}}{\\text{Distinct Orders}}$.
            - **New Customers**: Count of unique `customer_id` values whose earliest observed order across all dataset history falls within the reporting window.
            - **Customer Acquisition Cost (CAC)**: Total marketing spend within reporting window divided by newly acquired customers. Marketing spend is allocated at region and channel levels; it cannot be attributed to individual product categories.
            - **Customer Churn Rate (90-Day Inactivity Proxy)**: Because contractual subscription cancellation data is absent in retail e-commerce, churn is modeled as 90 consecutive days without placing an order following a customer's latest purchase. Monthly rate is $\\frac{\\text{Customers Lost in Month}}{\\text{Active Customers at Month Start}}$. The initial 120-day warm-up window is excluded from headline averages to prevent misleadingly low churn figures.
            - **Period-over-Period Deltas**: Compare selected window metrics against an immediately preceding period of identical duration.
            """
        )

    with st.expander("🧹 Data Cleaning Audit Report", expanded=False):
        c_ord, c_mkt = st.columns(2)
        with c_ord:
            st.markdown("**Orders Dataset Cleaning Audit**")
            st.dataframe(
                pd.DataFrame({"Cleaning Step": list(quality_report["orders"].keys()), "Rows Affected": list(quality_report["orders"].values())}),
                hide_index=True,
                use_container_width=True,
            )
        with c_mkt:
            st.markdown("**Marketing Spend Cleaning Audit**")
            st.dataframe(
                pd.DataFrame({"Cleaning Step": list(quality_report["marketing"].keys()), "Rows Affected": list(quality_report["marketing"].values())}),
                hide_index=True,
                use_container_width=True,
            )
