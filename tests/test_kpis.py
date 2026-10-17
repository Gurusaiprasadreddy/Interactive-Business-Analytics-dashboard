import numpy as np
import pandas as pd
import pytest

from app import kpis, pipeline
from app.pipeline import Filters


def _orders():
    rows = [  # order_id, date, customer, revenue, qty
        ("O1", "2024-01-10", "A", 100.0, 1), ("O2", "2024-01-20", "B", 50.0, 1), ("O2", "2024-01-20", "B", 50.0, 2),
        ("O3", "2024-02-05", "A", 200.0, 1), ("O4", "2024-05-01", "C", 120.0, 1),
    ]
    df = pd.DataFrame(rows, columns=["order_id", "order_date", "customer_id", "revenue", "quantity"])
    df["order_date"] = pd.to_datetime(df["order_date"])
    df["month"] = df["order_date"].dt.to_period("M").dt.to_timestamp()
    df["region"], df["product_category"], df["acquisition_channel"] = "Europe", "Fashion", "Email"
    df["country"], df["iso_alpha"], df["product_name"] = "France", "FRA", "X"
    return df


def _spend():
    return pd.DataFrame({"month": pd.to_datetime(["2024-01-01", "2024-02-01", "2024-05-01"]), "region": "Europe",
                         "channel": "Email", "spend": [90.0, 30.0, 60.0]})


F = Filters(pd.Timestamp("2024-01-01"), pd.Timestamp("2024-06-30"), ["Europe"], ["Fashion"], ["Email"])


def test_revenue_orders_aov():
    r = pipeline.compute(_orders(), _spend(), F)
    assert r.head.revenue == 520.0
    assert r.head.orders == 4            # O2 has two lines but is one order
    assert r.head.aov == pytest.approx(130.0)


def test_new_customers_and_cac():
    r = pipeline.compute(_orders(), _spend(), F)
    assert r.head.new_customers == 3     # A, B, C
    assert r.head.spend == 180.0
    assert r.head.cac == pytest.approx(60.0)
    jan = r.monthly.set_index("month").loc["2024-01-01"]
    assert jan["new_customers"] == 2 and jan["cac"] == pytest.approx(45.0)


def test_churn_definition():
    cust = kpis.customer_table(_orders(), as_of=pd.Timestamp("2024-06-30"))
    # A last ordered 2024-02-05 -> churns 90 days later; B 2024-01-20 -> churns; C ordered 2024-05-01 -> still active
    assert cust.loc["A", "churn_date"] == pd.Timestamp("2024-02-05") + pd.Timedelta(days=90)
    assert pd.isna(cust.loc["C", "churn_date"])


def test_churn_blank_during_warmup():
    cust = kpis.customer_table(_orders(), as_of=pd.Timestamp("2024-06-30"))
    m = kpis.monthly_churn(cust, pd.date_range("2024-01-01", "2024-06-01", freq="MS"))
    assert m["churn_rate"].iloc[:4].isna().all()        # Jan-Apr are inside the 120-day warm-up


def test_previous_period_unavailable_when_before_data():
    r = pipeline.compute(_orders(), _spend(), F)
    assert r.prev_head is None


def test_regroup_quarter_recomputes_ratios():
    r = pipeline.compute(_orders(), _spend(), F)
    q = pipeline.regroup(r.monthly, "Quarter")
    q1 = q.iloc[0]
    assert q1["revenue"] == 400.0 and q1["orders"] == 3
    assert q1["aov"] == pytest.approx(400 / 3)
    assert q1["cac"] == pytest.approx(120 / 2)   # Q1 new customers: A and B (C first orders in May)


def test_empty_selection_is_handled():
    f = Filters(F.start, F.end, ["Asia Pacific"], ["Fashion"], ["Email"])
    r = pipeline.compute(_orders(), _spend(), f)
    assert r.empty and r.head.revenue == 0 and np.isnan(r.head.aov)


def test_pct_change_guards():
    assert kpis.pct_change(110, 100) == pytest.approx(0.1)
    assert kpis.pct_change(1, 0) is None and kpis.pct_change(1, None) is None
