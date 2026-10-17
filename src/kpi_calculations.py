"""KPI calculation engine for Business Analytics Dashboard.

Defines executive business metrics, period-over-period comparative analytics,
dimensional rollups, and customer retention/churn analytics.

Formulas:
- Revenue = sum(quantity * unit_price * (1 - discount))
- Orders  = distinct order_id
- AOV     = Revenue / Orders
- New Customers = Customers whose first-ever recorded order is within the period
- CAC     = Marketing Spend / New Customers
- Churn Rate (90-day Inactivity Proxy) =
    Customers whose last order was >= 90 days ago without reordering / active base at period start.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd

CHURN_WINDOW_DAYS = 90
WARMUP_DAYS = 120


@dataclass
class HeadlineKPIs:
    revenue: float
    orders: int
    aov: float
    new_customers: int
    spend: float
    cac: float
    churn_rate: float
    active_customers: int


def calculate_customer_lifecycles(orders: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    """Determine customer first and last order timestamps, and projected churn date."""
    if orders.empty:
        return pd.DataFrame(columns=["first_order", "last_order", "churn_date", "first_month"])

    lifecycle = orders.groupby("customer_id").agg(
        first_order=("order_date", "min"),
        last_order=("order_date", "max"),
    )
    # 90-day inactivity threshold
    lifecycle["churn_date"] = lifecycle["last_order"] + pd.Timedelta(days=CHURN_WINDOW_DAYS)
    lifecycle.loc[lifecycle["churn_date"] > as_of, "churn_date"] = pd.NaT
    lifecycle["first_month"] = lifecycle["first_order"].dt.to_period("M").dt.to_timestamp()
    return lifecycle


def calculate_monthly_churn(customers: pd.DataFrame, months: pd.DatetimeIndex) -> pd.DataFrame:
    """Calculate monthly customer churn (inactivity proxy) across a date range."""
    rows = []
    if customers.empty:
        return pd.DataFrame({"month": months, "base_customers": 0, "churned": 0, "churn_rate": np.nan})

    warmup_cutoff = customers["first_order"].min() + pd.Timedelta(days=WARMUP_DAYS)
    for m in months:
        start_date = m
        end_date = m + pd.offsets.MonthEnd(0) + pd.Timedelta(hours=23, minutes=59, seconds=59)

        # Customers active at the beginning of the month
        active_mask = (customers["first_order"] < start_date) & (
            customers["churn_date"].isna() | (customers["churn_date"] >= start_date)
        )
        base_count = int(active_mask.sum())

        # Customers whose 90-day inactivity window elapsed during this month
        churned_mask = (
            (customers["churn_date"] >= start_date)
            & (customers["churn_date"] <= end_date)
            & active_mask
        )
        churned_count = int(churned_mask.sum())

        rate = (churned_count / base_count) if (base_count > 0 and start_date >= warmup_cutoff) else np.nan
        rows.append({
            "month": m,
            "base_customers": base_count,
            "churned": churned_count,
            "churn_rate": rate,
        })
    return pd.DataFrame(rows)


def calculate_monthly_kpis(
    filtered_orders: pd.DataFrame,
    scope_orders: pd.DataFrame,
    filtered_marketing: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
    as_of: pd.Timestamp,
) -> pd.DataFrame:
    """Generate monthly KPI trends for the selected period."""
    start_month = start.to_period("M").to_timestamp()
    end_month = end.to_period("M").to_timestamp()
    months = pd.date_range(start_month, end_month, freq="MS")
    base_df = pd.DataFrame({"month": months})

    # Orders within period
    in_period_orders = filtered_orders[
        (filtered_orders["order_date"] >= start) & (filtered_orders["order_date"] <= end)
    ]
    revenue_summary = (
        in_period_orders.groupby("month")
        .agg(
            revenue=("revenue", "sum"),
            orders=("order_id", "nunique"),
            units=("quantity", "sum"),
        )
        .reset_index()
    )

    # Customer metrics derived from scope
    customers = calculate_customer_lifecycles(scope_orders, as_of)
    if not customers.empty:
        new_cust = (
            customers.groupby("first_month")
            .size()
            .rename("new_customers")
            .reset_index()
            .rename(columns={"first_month": "month"})
        )
    else:
        new_cust = pd.DataFrame(columns=["month", "new_customers"])

    in_scope_period = scope_orders[
        (scope_orders["order_date"] >= start) & (scope_orders["order_date"] <= end)
    ]
    active_cust = (
        in_scope_period.groupby("month")["customer_id"]
        .nunique()
        .rename("active_customers")
        .reset_index()
    )

    # Marketing spend
    marketing_summary = (
        filtered_marketing.groupby("month")["spend"]
        .sum()
        .reset_index()
    )

    # Churn metrics
    churn_df = calculate_monthly_churn(customers, months)

    # Merge everything
    merged = (
        base_df.merge(revenue_summary, on="month", how="left")
        .merge(new_cust, on="month", how="left")
        .merge(active_cust, on="month", how="left")
        .merge(marketing_summary, on="month", how="left")
        .merge(churn_df, on="month", how="left")
    )

    numeric_fill_zero = [
        "revenue", "orders", "units", "new_customers",
        "active_customers", "spend", "churned", "base_customers"
    ]
    for col in numeric_fill_zero:
        merged[col] = merged[col].fillna(0)

    merged["aov"] = np.where(merged["orders"] > 0, merged["revenue"] / merged["orders"], np.nan)
    merged["cac"] = np.where(merged["new_customers"] > 0, merged["spend"] / merged["new_customers"], np.nan)

    return merged


def calculate_headline(
    monthly: pd.DataFrame,
    filtered_orders: pd.DataFrame,
    scope_orders: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> HeadlineKPIs:
    """Calculate executive headline KPIs for the filtered dataset."""
    v = filtered_orders[(filtered_orders["order_date"] >= start) & (filtered_orders["order_date"] <= end)]
    s = scope_orders[(scope_orders["order_date"] >= start) & (scope_orders["order_date"] <= end)]

    revenue = float(v["revenue"].sum()) if not v.empty else 0.0
    orders = int(v["order_id"].nunique()) if not v.empty else 0
    new_customers = int(monthly["new_customers"].sum()) if not monthly.empty else 0
    spend = float(monthly["spend"].sum()) if not monthly.empty else 0.0
    valid_churn = monthly["churn_rate"].dropna() if not monthly.empty else pd.Series(dtype=float)

    return HeadlineKPIs(
        revenue=revenue,
        orders=orders,
        aov=revenue / orders if orders > 0 else float("nan"),
        new_customers=new_customers,
        spend=spend,
        cac=spend / new_customers if new_customers > 0 else float("nan"),
        churn_rate=float(valid_churn.mean()) if len(valid_churn) > 0 else float("nan"),
        active_customers=int(s["customer_id"].nunique()) if not s.empty else 0,
    )


def calculate_pct_change(current: float | None, previous: float | None) -> float | None:
    """Safe percentage change calculation (returns None if invalid or zero denominator)."""
    if previous is None or current is None or np.isnan(previous) or np.isnan(current) or previous == 0:
        return None
    return (current - previous) / previous


def calculate_pp_change(current: float | None, previous: float | None) -> float | None:
    """Safe percentage-point difference (current - previous in decimal form)."""
    if previous is None or current is None or np.isnan(previous) or np.isnan(current):
        return None
    return (current - previous) * 100.0


def calculate_dimension_summary(df: pd.DataFrame, dimension: str | list[str]) -> pd.DataFrame:
    """Aggregate revenue, order volume, unit sales, and AOV by categorical dimensions."""
    if df.empty:
        cols = [dimension] if isinstance(dimension, str) else list(dimension)
        return pd.DataFrame(columns=cols + ["revenue", "orders", "units", "customers", "aov"])

    grouped = (
        df.groupby(dimension)
        .agg(
            revenue=("revenue", "sum"),
            orders=("order_id", "nunique"),
            units=("quantity", "sum"),
            customers=("customer_id", "nunique"),
        )
        .reset_index()
    )
    grouped["aov"] = grouped["revenue"] / grouped["orders"].replace(0, np.nan)
    return grouped.sort_values("revenue", ascending=False)


def calculate_channel_metrics(
    scope_orders: pd.DataFrame,
    marketing_df: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.DataFrame:
    """Calculate marketing spend, new customer acquisition, and CAC per channel."""
    first_orders = (
        scope_orders.sort_values("order_date")
        .drop_duplicates("customer_id")[["customer_id", "order_date", "acquisition_channel"]]
    )
    first_in_period = first_orders[
        (first_orders["order_date"] >= start) & (first_orders["order_date"] <= end)
    ]
    new_by_channel = (
        first_in_period.groupby("acquisition_channel")
        .size()
        .rename("new_customers")
        .reset_index()
        .rename(columns={"acquisition_channel": "channel"})
    )

    mkt_in_period = marketing_df[
        (marketing_df["month"] >= start.to_period("M").to_timestamp())
        & (marketing_df["month"] <= end.to_period("M").to_timestamp())
    ]
    spend_by_channel = (
        mkt_in_period.groupby("channel")["spend"]
        .sum()
        .reset_index()
    )

    all_channels = pd.DataFrame({"channel": sorted(set(scope_orders["acquisition_channel"].unique()) | set(marketing_df["channel"].unique()))})
    merged = all_channels.merge(spend_by_channel, on="channel", how="left").merge(new_by_channel, on="channel", how="left")
    merged["spend"] = merged["spend"].fillna(0.0)
    merged["new_customers"] = merged["new_customers"].fillna(0).astype(int)
    merged["cac"] = np.where(merged["new_customers"] > 0, merged["spend"] / merged["new_customers"], np.nan)

    return merged.sort_values("spend", ascending=False)
