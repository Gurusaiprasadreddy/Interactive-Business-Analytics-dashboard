"""KPI calculations. Every metric is derived from fields in the dataset.

Definitions (also in README.md > KPI definitions):
  Revenue   = sum(quantity * unit_price * (1 - discount))
  Orders    = distinct order_id
  AOV       = Revenue / Orders
  New customers = customers whose FIRST order (across all history) falls in the period
  CAC       = marketing spend in the period / new customers in the period
  Churn     = a customer churns 90 days after their last order if they do not
              order again. Monthly churn rate = customers churning in the month
              / customers active at the start of the month. Blank during the first 120 days of data (warm-up).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

CHURN_WINDOW_DAYS = 90


# ---------------------------------------------------------------- customers
def customer_table(orders: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    """One row per customer with first/last order date and churn date.

    `orders` must be the full history for the chosen scope (all dates).
    `churn_date` is NaT while the customer is still active as of `as_of`.
    """
    g = orders.groupby("customer_id").agg(
        first_order=("order_date", "min"), last_order=("order_date", "max"))
    g["churn_date"] = g["last_order"] + pd.Timedelta(days=CHURN_WINDOW_DAYS)
    g.loc[g["churn_date"] > as_of, "churn_date"] = pd.NaT
    g["first_month"] = g["first_order"].dt.to_period("M").dt.to_timestamp()
    return g


def monthly_churn(customers: pd.DataFrame, months: pd.DatetimeIndex) -> pd.DataFrame:
    """Monthly churn. Months in the first CHURN_WINDOW_DAYS + 30 days of history are left blank (NaN):
    nobody can have churned yet, so a rate there would be misleadingly low."""
    rows = []
    warmup_end = customers["first_order"].min() + pd.Timedelta(days=CHURN_WINDOW_DAYS + 30)
    for m in months:
        start, end = m, m + pd.offsets.MonthEnd(0) + pd.Timedelta(hours=23, minutes=59)
        active_at_start = (customers["first_order"] < start) & (
            customers["churn_date"].isna() | (customers["churn_date"] >= start))
        base = int(active_at_start.sum())
        churned = int(((customers["churn_date"] >= start) & (customers["churn_date"] <= end)
                       & active_at_start).sum())
        rows.append({"month": m, "base_customers": base, "churned": churned,
                     "churn_rate": churned / base if base and start >= warmup_end else np.nan})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ monthly
def months_between(start: pd.Timestamp, end: pd.Timestamp) -> pd.DatetimeIndex:
    return pd.date_range(start.to_period("M").to_timestamp(), end.to_period("M").to_timestamp(), freq="MS")


def monthly_kpis(view: pd.DataFrame, scope: pd.DataFrame, spend: pd.DataFrame,
                 start: pd.Timestamp, end: pd.Timestamp, as_of: pd.Timestamp) -> pd.DataFrame:
    """Monthly KPI table for [start, end].

    view  - orders after ALL filters (drives revenue / orders / AOV)
    scope - orders after region + channel filters, all dates, any category
            (drives customer metrics, since a customer is new/churned regardless of what they buy)
    spend - marketing spend after region + channel filters
    """
    months = months_between(start, end)
    base = pd.DataFrame({"month": months})

    v = view[(view["order_date"] >= start) & (view["order_date"] <= end)]
    rev = v.groupby("month").agg(revenue=("revenue", "sum"), orders=("order_id", "nunique"),
                                 units=("quantity", "sum")).reset_index()

    cust = customer_table(scope, as_of) if len(scope) else pd.DataFrame(
        columns=["first_order", "last_order", "churn_date", "first_month"])
    new = (cust.groupby("first_month").size().rename("new_customers").reset_index()
           .rename(columns={"first_month": "month"})) if len(cust) else pd.DataFrame(columns=["month", "new_customers"])
    active = (scope[(scope["order_date"] >= start) & (scope["order_date"] <= end)]
              .groupby("month")["customer_id"].nunique().rename("active_customers").reset_index())
    sp = spend.groupby("month")["spend"].sum().reset_index()
    churn = monthly_churn(cust, months) if len(cust) else pd.DataFrame(
        {"month": months, "base_customers": 0, "churned": 0, "churn_rate": np.nan})

    out = (base.merge(rev, on="month", how="left").merge(new, on="month", how="left")
               .merge(active, on="month", how="left").merge(sp, on="month", how="left")
               .merge(churn, on="month", how="left"))
    for c in ["revenue", "orders", "units", "new_customers", "active_customers", "spend", "churned"]:
        out[c] = out[c].fillna(0)
    out["aov"] = np.where(out["orders"] > 0, out["revenue"] / out["orders"].replace(0, np.nan), np.nan)
    out["cac"] = np.where(out["new_customers"] > 0, out["spend"] / out["new_customers"].replace(0, np.nan), np.nan)
    return out


# ----------------------------------------------------------------- headline
@dataclass
class Headline:
    revenue: float
    orders: int
    aov: float
    new_customers: int
    spend: float
    cac: float
    churn_rate: float  # average monthly churn over the period
    active_customers: int


def headline(monthly: pd.DataFrame, view: pd.DataFrame, scope: pd.DataFrame,
             start: pd.Timestamp, end: pd.Timestamp) -> Headline:
    v = view[(view["order_date"] >= start) & (view["order_date"] <= end)]
    s = scope[(scope["order_date"] >= start) & (scope["order_date"] <= end)]
    revenue = float(v["revenue"].sum())
    orders = int(v["order_id"].nunique())
    new_c = int(monthly["new_customers"].sum())
    spend = float(monthly["spend"].sum())
    valid = monthly["churn_rate"].dropna()
    return Headline(
        revenue=revenue,
        orders=orders,
        aov=revenue / orders if orders else float("nan"),
        new_customers=new_c,
        spend=spend,
        cac=spend / new_c if new_c else float("nan"),
        churn_rate=float(valid.mean()) if len(valid) else float("nan"),
        active_customers=int(s["customer_id"].nunique()),
    )


def pct_change(cur: float, prev: float) -> float | None:
    if prev is None or cur is None or np.isnan(prev) or np.isnan(cur) or prev == 0:
        return None
    return (cur - prev) / prev


# --------------------------------------------------------------- breakdowns
def by_dimension(view: pd.DataFrame, dim: str | list[str]) -> pd.DataFrame:
    g = view.groupby(dim).agg(revenue=("revenue", "sum"), orders=("order_id", "nunique"),
                              units=("quantity", "sum"), customers=("customer_id", "nunique")).reset_index()
    g["aov"] = g["revenue"] / g["orders"].replace(0, np.nan)
    return g.sort_values("revenue", ascending=False)


def channel_efficiency(scope: pd.DataFrame, spend: pd.DataFrame, customers: pd.DataFrame,
                       start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Spend, new customers and CAC by acquisition channel in the period."""
    first = scope.sort_values("order_date").drop_duplicates("customer_id")[["customer_id", "acquisition_channel"]]
    c = customers.join(first.set_index("customer_id"))
    c = c[(c["first_order"] >= start) & (c["first_order"] <= end)]
    new = c.groupby("acquisition_channel").size().rename("new_customers")
    sp = spend.groupby("channel")["spend"].sum().rename("spend")
    out = pd.concat([sp, new], axis=1).fillna(0).reset_index().rename(columns={"index": "channel"})
    out["cac"] = out["spend"] / out["new_customers"].replace(0, np.nan)
    return out.sort_values("cac")
