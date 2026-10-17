"""Filtering + KPI computation shared by the Streamlit app and the PDF exporter."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from app import kpis


@dataclass
class Filters:
    start: pd.Timestamp          # first day of the first selected month
    end: pd.Timestamp            # last day of the last selected month
    regions: list[str]
    categories: list[str]
    channels: list[str]


@dataclass
class Result:
    filters: Filters
    view: pd.DataFrame           # orders after ALL filters (all dates)
    scope: pd.DataFrame          # orders after region + channel filters (all dates)
    spend: pd.DataFrame          # marketing spend after region + channel filters
    monthly: pd.DataFrame        # monthly KPI table for the selected period
    head: kpis.Headline
    prev_head: kpis.Headline | None   # same-length period immediately before; None if out of data range
    prev_monthly: pd.DataFrame | None
    customers: pd.DataFrame
    in_period: pd.DataFrame = field(default_factory=pd.DataFrame)  # `view` restricted to [start, end]

    @property
    def empty(self) -> bool:
        return self.in_period.empty


def month_end(m: pd.Timestamp) -> pd.Timestamp:
    return (m + pd.offsets.MonthEnd(0)).normalize()


def compute(orders: pd.DataFrame, marketing: pd.DataFrame, f: Filters) -> Result:
    data_min, as_of = orders["order_date"].min(), orders["order_date"].max()

    scope = orders[orders["region"].isin(f.regions) & orders["acquisition_channel"].isin(f.channels)]
    view = scope[scope["product_category"].isin(f.categories)]
    spend = marketing[marketing["region"].isin(f.regions) & marketing["channel"].isin(f.channels)]

    monthly = kpis.monthly_kpis(view, scope, spend, f.start, f.end, as_of)
    head = kpis.headline(monthly, view, scope, f.start, f.end)
    customers = kpis.customer_table(scope, as_of) if len(scope) else pd.DataFrame()

    # previous period of identical length (for the delta on each KPI card)
    n_days = (f.end - f.start).days + 1
    p_end = f.start - pd.Timedelta(days=1)
    p_start = (p_end - pd.Timedelta(days=n_days - 1)).replace(day=1)
    prev_head = prev_monthly = None
    if p_start >= data_min.to_period("M").to_timestamp():
        prev_monthly = kpis.monthly_kpis(view, scope, spend, p_start, p_end, as_of)
        prev_head = kpis.headline(prev_monthly, view, scope, p_start, p_end)

    in_period = view[(view["order_date"] >= f.start) & (view["order_date"] <= f.end)]
    return Result(f, view, scope, spend, monthly, head, prev_head, prev_monthly, customers, in_period)


def regroup(monthly: pd.DataFrame, granularity: str) -> pd.DataFrame:
    """Aggregate the monthly KPI table to Month / Quarter / Year (date drill-down)."""
    if granularity == "Month":
        return monthly.copy()
    freq = {"Quarter": "Q", "Year": "Y"}[granularity]
    m = monthly.copy()
    m["period"] = m["month"].dt.to_period(freq).dt.start_time
    g = m.groupby("period").agg(
        revenue=("revenue", "sum"), orders=("orders", "sum"), new_customers=("new_customers", "sum"),
        spend=("spend", "sum"), churn_rate=("churn_rate", "mean"), months=("month", "count")).reset_index()
    g = g.rename(columns={"period": "month"})
    g["aov"] = np.where(g["orders"] > 0, g["revenue"] / g["orders"].replace(0, np.nan), np.nan)
    g["cac"] = np.where(g["new_customers"] > 0, g["spend"] / g["new_customers"].replace(0, np.nan), np.nan)
    return g


# ------------------------------------------------------------------ helpers used by the UI / PDF
def revenue_by(r: Result, dim: str, granularity: str = "Month") -> pd.DataFrame:
    """Revenue per period x dimension (zero-filled so stacked areas have no gaps)."""
    d = r.in_period
    if d.empty:
        return pd.DataFrame(columns=["month", dim, "revenue"])
    freq = {"Month": "M", "Quarter": "Q", "Year": "Y"}[granularity]
    key = d["order_date"].dt.to_period(freq).dt.start_time.rename("month")
    piv = d.groupby([key, d[dim]])["revenue"].sum().unstack(fill_value=0)
    full = pd.date_range(piv.index.min(), piv.index.max(),
                         freq={"M": "MS", "Q": "QS", "Y": "YS"}[freq])
    piv = piv.reindex(full, fill_value=0)
    return piv.rename_axis("month").reset_index().melt("month", var_name=dim, value_name="revenue")


def channel_table(r: Result) -> pd.DataFrame:
    """Spend, new customers and CAC per acquisition channel in the selected period."""
    f = r.filters
    sp = r.spend[(r.spend["month"] >= f.start.to_period("M").to_timestamp()) & (r.spend["month"] <= f.end)]
    if r.customers.empty:
        return pd.DataFrame(columns=["channel", "spend", "new_customers", "cac"])
    return kpis.channel_efficiency(r.scope, sp, r.customers, f.start, f.end)


def country_table(r: Result, region: str | None = None) -> pd.DataFrame:
    d = r.in_period if region in (None, "All regions") else r.in_period[r.in_period["region"] == region]
    if d.empty:
        return pd.DataFrame()
    iso = d.drop_duplicates("country").set_index("country")["iso_alpha"]
    t = kpis.by_dimension(d, "country")
    t["iso_alpha"] = t["country"].map(iso)
    return t


def pct_delta(cur: float, prev: float | None) -> str | None:
    if prev is None:
        return None
    ch = kpis.pct_change(cur, prev)
    return None if ch is None else f"{ch:+.1%}"
