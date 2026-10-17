"""PDF export of the dashboard (reportlab + static Plotly images via kaleido).

Used by the "Prepare PDF" button in the app and by `python scripts/export_pdf.py`.
Static chart rendering needs Chrome/Chromium; set BROWSER_PATH if it is not auto-detected.
"""
from __future__ import annotations

import glob
import io
import os
from datetime import date
from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from app import charts, kpis, pipeline
from app.insights import build_insights
from app.pipeline import Result

PAGE_W, PAGE_H = landscape(A4)
M = 28  # page margin (pt)
BLUE = colors.HexColor(charts.BLUE)
INK, INK2, LINE = colors.HexColor(charts.INK), colors.HexColor(charts.INK_2), colors.HexColor("#dcdbd5")
GOOD, BAD = colors.HexColor("#0b7a3b"), colors.HexColor("#c2342f")


def _ensure_browser() -> None:
    """Point kaleido at a local Chrome/Chromium when one is available and BROWSER_PATH is unset.

    Optional: set PLOTLY_TOPOJSON_DIR to a folder holding plotly's world_110m.json when the machine cannot
    reach cdn.plot.ly (kaleido otherwise downloads the map shapes there when exporting choropleths).
    """
    topo = os.environ.get("PLOTLY_TOPOJSON_DIR")
    if topo:
        import plotly.io as pio
        pio.defaults.topojson = Path(topo).resolve().as_uri()
    if os.environ.get("BROWSER_PATH"):
        return
    for pattern in (
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
        "/opt/pw-browsers/chromium-*/chrome-linux*/chrome",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ):
        if os.path.exists(pattern):
            os.environ["BROWSER_PATH"] = pattern
            return
        found = glob.glob(pattern)
        if found:
            os.environ["BROWSER_PATH"] = found[0]
            return


def _img(fig, w: int, h: int) -> ImageReader:
    fig.update_layout(paper_bgcolor="white", plot_bgcolor="white")
    return ImageReader(io.BytesIO(fig.to_image(format="png", width=w, height=h, scale=2)))


def place(c: canvas.Canvas, fig, px_w: int, px_h: int, x: float, y_top: float, width: float) -> float:
    """Draw a figure with its top-left corner at (x, y_top), scaled to `width` keeping its aspect ratio."""
    height = width * px_h / px_w
    c.drawImage(_img(fig, px_w, px_h), x, y_top - height, width, height)
    return height


def _header(c: canvas.Canvas, title: str, subtitle: str, page: int) -> None:
    c.setFillColor(BLUE)
    c.rect(0, PAGE_H - 46, PAGE_W, 46, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(M, PAGE_H - 30, title)
    c.setFont("Helvetica", 9)
    c.drawRightString(PAGE_W - M, PAGE_H - 28, subtitle)
    c.setFillColor(INK2)
    c.setFont("Helvetica", 8)
    c.drawString(M, 16, f"Generated {date.today():%d %b %Y} · synthetic e-commerce dataset")
    c.drawRightString(PAGE_W - M, 16, f"Page {page}")


def _kpi_card(c: canvas.Canvas, x: float, y: float, w: float, h: float, label: str, value: str,
              delta: str | None, good: bool | None) -> None:
    c.setStrokeColor(LINE)
    c.setFillColor(colors.white)
    c.roundRect(x, y, w, h, 6, stroke=1, fill=1)
    c.setFillColor(INK2)
    c.setFont("Helvetica", 8.5)
    c.drawString(x + 10, y + h - 16, label.upper())
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 19)
    c.drawString(x + 10, y + h - 40, value)
    if delta:
        c.setFillColor(GOOD if good else BAD)
        c.setFont("Helvetica-Bold", 8.5)
        c.drawString(x + 10, y + 9, delta + "  vs prev. period")
    else:
        c.setFillColor(INK2)
        c.setFont("Helvetica", 8)
        c.drawString(x + 10, y + 9, "no prior period")


def _wrap(c: canvas.Canvas, text: str, x: float, y: float, width: float, font: str, size: float, leading: float) -> float:
    c.setFont(font, size)
    words, line = text.split(), ""
    for w in words:
        trial = f"{line} {w}".strip()
        if c.stringWidth(trial, font, size) > width:
            c.drawString(x, y, line)
            y -= leading
            line = w
        else:
            line = trial
    if line:
        c.drawString(x, y, line)
        y -= leading
    return y


def build_pdf(r: Result, path: str | None = None) -> bytes:
    """Render a 3-page landscape A4 PDF for the filtered view. Returns the bytes (and writes `path` if given)."""
    _ensure_browser()
    f, h, p = r.filters, r.head, r.prev_head
    sub = f"{f.start:%b %Y} – {f.end:%b %Y} · {len(f.regions)} regions · {len(f.categories)} categories · {len(f.channels)} channels"
    monthly = r.monthly
    ch = pipeline.channel_table(r)
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=landscape(A4))
    c.setTitle("Business Analytics Dashboard")
    c.setAuthor("Business Analytics Dashboard")
    cw = PAGE_W - 2 * M

    # ---------------- page 1: KPIs, revenue trend, insights
    _header(c, "Business Analytics Dashboard — Overview", sub, 1)
    pd_ = lambda cur, prev: pipeline.pct_delta(cur, prev if p else None)  # noqa: E731
    cards = [
        ("Revenue", f"${h.revenue:,.0f}", pd_(h.revenue, p and p.revenue), True),
        ("Avg. order value", f"${h.aov:,.2f}", pd_(h.aov, p and p.aov), True),
        ("Customer acq. cost", f"${h.cac:,.2f}", pd_(h.cac, p and p.cac), False),
        ("Monthly churn", f"{h.churn_rate:.1%}", (f"{(h.churn_rate - p.churn_rate) * 100:+.1f} pp" if p else None), False),
    ]
    gap, card_h = 12, 62
    card_w = (cw - 3 * gap) / 4
    for i, (lab, val, dlt, higher_good) in enumerate(cards):
        good = None
        if dlt:
            up = dlt.startswith("+")
            good = up if higher_good else not up
        _kpi_card(c, M + i * (card_w + gap), PAGE_H - 62 - card_h, card_w, card_h, lab, val, dlt, good)
    y0 = PAGE_H - 62 - card_h - 12
    # revenue trend (left, 62% width) + insights (right)
    trend_w = cw * 0.62
    place(c, charts.area_trend(monthly, "Revenue", "Monthly revenue", 300), 760, 300, M, y0, trend_w)
    ix = M + trend_w + 20
    iw = PAGE_W - M - ix
    y = y0 - 14
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(ix, y, "Key insights")
    y -= 16
    for head_, detail in build_insights(r, ch)[:5]:
        c.setFillColor(INK)
        top = y
        y = _wrap(c, head_, ix + 9, y, iw - 9, "Helvetica-Bold", 8.5, 10.5)
        c.setFillColor(INK2)
        y = _wrap(c, detail, ix + 9, y, iw - 9, "Helvetica", 8, 10)
        c.setFillColor(BLUE)
        c.rect(ix, y + 2, 2.5, top - y + 6, stroke=0, fill=1)
        y -= 8
    # lower strip: three small area charts
    sw = (cw - 2 * gap) / 3
    for i, (metric, ttl, col) in enumerate([("AOV", "Average order value", charts.BLUE),
                                            ("CAC", "Customer acquisition cost", charts.ORANGE),
                                            ("Churn rate", "Monthly churn rate", charts.MAGENTA)]):
        place(c, charts.area_trend(monthly, metric, ttl, 220, color=col), 400, 220,
              M + i * (sw + gap), M + 20 + sw * 220 / 400, sw)
    c.showPage()

    # ---------------- page 2: geography
    _header(c, "Geography & regions", sub, 2)
    ctab = pipeline.country_table(r)
    map_w = cw * 0.64
    top = PAGE_H - 62
    place(c, charts.geo_map(ctab, "Revenue", "Revenue by country", 400), 800, 400, M, top, map_w)
    reg = r.in_period.groupby("region", as_index=False)["revenue"].sum()
    place(c, charts.region_bars(reg, "Revenue by region", 400), 450, 400, M + map_w + gap, top, cw - map_w - gap)
    place(c, charts.stacked_area(pipeline.revenue_by(r, "region"), "region", charts.REGION_COLORS,
                                 "Revenue by region and month", 260), 1100, 260, M, M + 20 + cw * 260 / 1100, cw)
    c.showPage()

    # ---------------- page 3: products & acquisition
    _header(c, "Products & customer acquisition", sub, 3)
    cat = kpis.by_dimension(r.in_period, "product_category")
    half = (cw - gap) / 2
    hh = half * 280 / 520
    top = PAGE_H - 62
    place(c, charts.hbar(cat, "product_category", "revenue", charts.CATEGORY_COLORS, "Revenue by category", 280),
          520, 280, M, top, half)
    place(c, charts.hbar(cat, "product_category", "aov", charts.CATEGORY_COLORS, "Average order value by category",
                         280, fmt="$,.2f"), 520, 280, M + half + gap, top, half)
    place(c, charts.spend_vs_new(monthly, "New customers per month", 280), 520, 280, M, top - hh - gap, half)
    place(c, charts.channel_cac(ch, "CAC by acquisition channel (lower is better)", 280), 520, 280,
          M + half + gap, top - hh - gap, half)
    c.setFillColor(INK2)
    _wrap(c, "KPI definitions: Revenue = Σ qty × price × (1 − discount); AOV = revenue ÷ orders; CAC = marketing spend ÷ new customers; "
             "churn = customers with no order for 90 days ÷ customers active at the start of the month (average over the period).",
          M, M + 24, cw, "Helvetica", 7.5, 9.5)
    c.showPage()
    c.save()

    data = buf.getvalue()
    if path:
        with open(path, "wb") as fh:
            fh.write(data)
    return data
