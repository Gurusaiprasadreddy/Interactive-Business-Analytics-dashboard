"""Reusable Insight Callout Cards."""
from __future__ import annotations

import streamlit as st


def render_insight_card(headline: str, detail: str):
    """Render a styled executive insight callout block."""
    st.markdown(
        f"""
        <div style="border-left: 3.5px solid #2a78d6; padding: 8px 14px; margin-bottom: 12px;
                    background: #f8fafc; border-radius: 0 6px 6px 0; box-shadow: 0 1px 2px rgba(0,0,0,0.03);">
            <div style="font-weight: 600; font-size: 0.94rem; color: #1e293b;">{headline}</div>
            <div style="font-size: 0.85rem; color: #475569; margin-top: 3px; line-height: 1.4;">{detail}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
