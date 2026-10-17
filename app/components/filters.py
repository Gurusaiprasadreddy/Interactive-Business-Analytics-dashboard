"""Reusable Sidebar Filter Component."""
from __future__ import annotations

from dataclasses import dataclass
import pandas as pd
import streamlit as st


@dataclass
class FilterState:
    start_date: pd.Timestamp
    end_date: pd.Timestamp
    regions: list[str]
    countries: list[str]
    categories: list[str]
    products: list[str]
    channels: list[str]
    granularity: str


def render_sidebar_filters(orders_df: pd.DataFrame) -> FilterState:
    """Render interactive sidebar filters with dynamic options and reset capability."""
    st.sidebar.header("Navigation & Filters")

    # Dates
    min_date = orders_df["order_date"].min().date()
    max_date = orders_df["order_date"].max().date()

    all_regions = sorted(orders_df["region"].dropna().unique().tolist())
    all_categories = sorted(orders_df["product_category"].dropna().unique().tolist())
    all_channels = sorted(orders_df["acquisition_channel"].dropna().unique().tolist())

    # Date range selector
    date_val = st.sidebar.date_input(
        "Date Range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
        help="Select start and end dates. The end date includes transactions through 23:59:59.",
    )

    if isinstance(date_val, (list, tuple)) and len(date_val) == 2:
        start_date = pd.Timestamp(date_val[0])
        # Ensure the end date includes the entire day
        end_date = pd.Timestamp(date_val[1]) + pd.Timedelta(hours=23, minutes=59, seconds=59)
    elif isinstance(date_val, (list, tuple)) and len(date_val) == 1:
        start_date = pd.Timestamp(date_val[0])
        end_date = pd.Timestamp(date_val[0]) + pd.Timedelta(hours=23, minutes=59, seconds=59)
    else:
        start_date = pd.Timestamp(min_date)
        end_date = pd.Timestamp(max_date) + pd.Timedelta(hours=23, minutes=59, seconds=59)

    # Region
    selected_regions = st.sidebar.multiselect(
        "Region",
        options=all_regions,
        default=all_regions,
        help="Filter by geographical regions.",
    )

    # Dynamic Country filter based on selected regions
    available_countries = sorted(
        orders_df[orders_df["region"].isin(selected_regions)]["country"].dropna().unique().tolist()
    ) if selected_regions else []

    selected_countries = st.sidebar.multiselect(
        "Country",
        options=available_countries,
        default=available_countries,
        help="Filter by specific countries within selected regions.",
    )

    # Product Category
    selected_categories = st.sidebar.multiselect(
        "Product Category",
        options=all_categories,
        default=all_categories,
        help="Filter by product categories.",
    )

    # Dynamic Product filter based on selected categories
    available_products = sorted(
        orders_df[orders_df["product_category"].isin(selected_categories)]["product_name"].dropna().unique().tolist()
    ) if selected_categories else []

    selected_products = st.sidebar.multiselect(
        "Product",
        options=available_products,
        default=available_products,
        help="Filter by specific products within selected categories.",
    )

    # Acquisition Channel
    selected_channels = st.sidebar.multiselect(
        "Acquisition Channel",
        options=all_channels,
        default=all_channels,
        help="Filter by customer acquisition channels.",
    )

    # Temporal Granularity
    granularity = st.sidebar.radio(
        "Time Aggregation",
        options=["Month", "Quarter", "Year"],
        index=0,
        horizontal=True,
        help="Drill down trendlines by Month, Quarter, or Year.",
    )

    return FilterState(
        start_date=start_date,
        end_date=end_date,
        regions=selected_regions,
        countries=selected_countries,
        categories=selected_categories,
        products=selected_products,
        channels=selected_channels,
        granularity=granularity,
    )
