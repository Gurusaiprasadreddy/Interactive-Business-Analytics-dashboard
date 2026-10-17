"""Reusable KPI Metric Card Components for Streamlit."""
from __future__ import annotations

import pandas as pd
import streamlit as st


def render_metric_card(
    col,
    label: str,
    value: str,
    series: pd.Series | list[float] | None = None,
    delta: str | None = None,
    inverse: bool = False,
    help_text: str | None = None,
    show_sparkline: bool = True,
):
    """Render a styled metric card with optional delta and sparkline chart."""
    with col:
        with st.container(border=True):
            st.metric(
                label=label,
                value=value,
                delta=delta,
                delta_color="inverse" if inverse else "normal",
                help=help_text,
            )
