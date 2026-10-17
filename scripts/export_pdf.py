"""Export the last-12-months dashboard (all regions / categories / channels) to reports/dashboard.pdf
and the individual charts to visualizations/*.png.

Run:  python scripts/export_pdf.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd

from app import charts, pipeline
from app.cleaning import load_and_clean
from app.pipeline import Filters
from app.report import _ensure_browser, build_pdf


def main() -> None:
    orders, mkt, _ = load_and_clean(save=True)
    last12 = orders["order_date"].max().to_period("M").to_timestamp() - pd.DateOffset(months=11)
    f = Filters(start=max(last12, orders["order_date"].min().to_period("M").to_timestamp()),
                end=pipeline.month_end(orders["order_date"].max()),
                regions=sorted(orders["region"].unique()), categories=sorted(orders["product_category"].unique()),
                channels=sorted(orders["acquisition_channel"].unique()))
    res = pipeline.compute(orders, mkt, f)
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "visualizations").mkdir(exist_ok=True)
    out = ROOT / "reports" / "dashboard.pdf"
    build_pdf(res, str(out))
    print(f"wrote {out}")

    _ensure_browser()
    figs = {
        "revenue_trend": charts.area_trend(res.monthly, "Revenue", "Monthly revenue", 420),
        "aov_trend": charts.area_trend(res.monthly, "AOV", "Average order value", 420),
        "cac_trend": charts.area_trend(res.monthly, "CAC", "Customer acquisition cost", 420, color=charts.ORANGE),
        "churn_trend": charts.area_trend(res.monthly, "Churn rate", "Monthly churn rate", 420, color=charts.MAGENTA),
        "revenue_by_region": charts.stacked_area(pipeline.revenue_by(res, "region"), "region", charts.REGION_COLORS,
                                                 "Revenue by region", 480),
        "geo_revenue": charts.geo_map(pipeline.country_table(res), "Revenue", "Revenue by country", 520),
    }
    for name, fig in figs.items():
        fig.update_layout(paper_bgcolor="white", plot_bgcolor="white")
        fig.write_image(ROOT / "visualizations" / f"{name}.png", width=1100, height=fig.layout.height, scale=2)
    print(f"wrote {len(figs)} PNGs to visualizations/")


if __name__ == "__main__":
    main()
