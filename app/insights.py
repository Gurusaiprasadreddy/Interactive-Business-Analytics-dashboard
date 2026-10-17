"""Rule-based business insights generated from the current filter selection."""
from __future__ import annotations

import numpy as np
import pandas as pd

from app import kpis
from app.pipeline import Result


def _pct(x: float) -> str:
    return f"{x:+.1%}"


def build_insights(r: Result, channel_df: pd.DataFrame | None = None) -> list[tuple[str, str]]:
    """Return a list of (headline, detail) tuples, most important first."""
    if r.empty:
        return []
    out: list[tuple[str, str]] = []
    h, p = r.head, r.prev_head

    # 1. revenue momentum, split into volume vs. basket size
    if p and p.revenue:
        d_rev = kpis.pct_change(h.revenue, p.revenue)
        d_ord = kpis.pct_change(h.orders, p.orders)
        d_aov = kpis.pct_change(h.aov, p.aov)
        driver = "more orders" if abs(d_ord or 0) >= abs(d_aov or 0) else "a higher average order value"
        if d_rev is not None and d_rev < 0:
            driver = "fewer orders" if abs(d_ord or 0) >= abs(d_aov or 0) else "a lower average order value"
        out.append((
            f"Revenue {'grew' if (d_rev or 0) >= 0 else 'fell'} {_pct(d_rev)} vs. the previous period",
            f"Driven mainly by {driver} (orders {_pct(d_ord)}, AOV {_pct(d_aov)})."))
    else:
        out.append((f"Revenue of ${h.revenue:,.0f} across {h.orders:,} orders",
                    "No earlier period of equal length exists in the data, so no comparison is shown."))

    # 2. concentration by region
    reg = kpis.by_dimension(r.in_period, "region")
    if len(reg):
        top = reg.iloc[0]
        share = top["revenue"] / reg["revenue"].sum()
        out.append((f"{top['region']} contributes {share:.0%} of revenue",
                    "Revenue is concentrated here; protect this market and test growth levers in the next two regions."
                    if share > 0.4 else "Revenue is reasonably spread across regions."))

    # 3. best / worst category on AOV
    cat = kpis.by_dimension(r.in_period, "product_category")
    if len(cat) > 1:
        hi, lo = cat.sort_values("aov").iloc[-1], cat.sort_values("aov").iloc[0]
        out.append((f"{hi['product_category']} has the highest AOV (${hi['aov']:,.0f}); {lo['product_category']} the lowest (${lo['aov']:,.0f})",
                    f"Bundling or cross-sell offers from {lo['product_category']} into {hi['product_category']} could lift basket size."))

    # 4. acquisition efficiency
    if channel_df is not None and len(channel_df[channel_df["new_customers"] > 0]) > 1:
        c = channel_df[channel_df["new_customers"] > 0].sort_values("cac")
        paid = c[c["channel"] != "Organic"]
        if len(paid) > 1:
            best, worst = paid.iloc[0], paid.iloc[-1]
            out.append((f"{worst['channel']} costs ${worst['cac']:,.0f} per new customer vs. ${best['cac']:,.0f} for {best['channel']}",
                        f"Shifting budget from {worst['channel']} to {best['channel']} would lower blended CAC "
                        f"(currently ${h.cac:,.2f}), provided {best['channel']} can scale."))

    # 5. retention
    m = r.monthly.dropna(subset=["churn_rate"])
    if len(m) >= 6:
        first, last = m["churn_rate"].iloc[-6:-3].mean(), m["churn_rate"].iloc[-3:].mean()
        trend = "rising" if last > first * 1.05 else "falling" if last < first * 0.95 else "stable"
        out.append((f"Monthly churn is {trend}: {last:.1%} over the last 3 months vs. {first:.1%} over the 3 before",
                    "Consider win-back emails to customers approaching 60 days since last order."
                    if trend != "falling" else "Retention efforts appear to be working; keep monitoring."))

    # 6. LTV : CAC (simple, from available fields)
    if h.new_customers and h.cac and h.orders:
        rev_per_cust = h.revenue / max(h.active_customers, 1)
        ratio = rev_per_cust / h.cac
        out.append((f"Revenue per active customer (${rev_per_cust:,.0f}) is {ratio:.1f}x the CAC (${h.cac:,.2f})",
                    "A ratio above 3x is a common health benchmark; this is revenue, not margin, so treat it as an upper bound."))
    return out
