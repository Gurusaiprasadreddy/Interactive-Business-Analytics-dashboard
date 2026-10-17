"""Tests for src/ modules: data_loader, data_cleaning, kpi_calculations, and visualizations."""
import numpy as np
import pandas as pd
import pytest

from src.data_loader import load_raw_data, load_raw_orders, load_raw_marketing, DataValidationError
from src.data_cleaning import clean_orders, clean_marketing, load_and_clean
from src.kpi_calculations import (
    calculate_headline,
    calculate_monthly_kpis,
    calculate_pct_change,
    calculate_pp_change,
    calculate_dimension_summary,
    calculate_channel_metrics,
)
from src import visualizations as viz


def test_data_loader_shipped_files():
    orders, mkt = load_raw_data()
    assert not orders.empty
    assert not mkt.empty
    assert "order_id" in orders.columns
    assert "spend" in mkt.columns


def test_data_cleaning_and_validation():
    orders_clean, mkt_clean, report = load_and_clean(save=False)
    assert not orders_clean.empty
    assert not mkt_clean.empty
    assert (orders_clean["revenue"] > 0).all()
    assert (orders_clean["quantity"] > 0).all()
    assert (orders_clean["discount"].between(0, 1)).all()
    assert not orders_clean.duplicated().any()
    assert "orders" in report and "marketing" in report


def test_kpi_calculations_and_deltas():
    # Percentage change tests
    assert calculate_pct_change(120, 100) == pytest.approx(0.20)
    assert calculate_pct_change(80, 100) == pytest.approx(-0.20)
    assert calculate_pct_change(100, 0) is None
    assert calculate_pct_change(None, 100) is None

    # Percentage point tests
    assert calculate_pp_change(0.15, 0.10) == pytest.approx(5.0)
    assert calculate_pp_change(0.08, 0.12) == pytest.approx(-4.0)
    assert calculate_pp_change(None, 0.10) is None


def test_visualization_generators():
    orders, mkt, _ = load_and_clean(save=False)
    monthly = orders.groupby("month").agg(revenue=("revenue", "sum"), orders=("order_id", "nunique")).reset_index()

    fig_rev = viz.plot_revenue_area(monthly, title="Revenue Test")
    assert fig_rev is not None

    fig_hist = viz.plot_revenue_histogram(orders.head(100), title="Hist Test")
    assert fig_hist is not None

    fig_box = viz.plot_boxplots(orders.head(100), "revenue", title="Box Test")
    assert fig_box is not None

    fig_corr = viz.plot_correlation_matrix(orders.head(100), title="Corr Test")
    assert fig_corr is not None
