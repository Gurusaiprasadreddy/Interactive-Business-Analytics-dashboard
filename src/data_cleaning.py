"""Data cleaning module for Business Analytics Dashboard.

Standardizes raw orders and marketing datasets, handles anomalies,
validates business rules, and outputs cleaned data frames with audit reports.
"""
from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd

from src.data_loader import (
    DataValidationError,
    EXPECTED_MARKETING_COLUMNS,
    EXPECTED_ORDER_COLUMNS,
    load_raw_data,
)

ROOT_DIR = Path(__file__).resolve().parents[1]
PROCESSED_DIR = ROOT_DIR / "data" / "processed"
DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%b %d, %Y"]


def parse_mixed_dates(series: pd.Series) -> pd.Series:
    """Parse mixed date string formats systematically."""
    s = series.astype(str).str.strip()
    out = pd.Series(pd.NaT, index=s.index, dtype="datetime64[ns]")
    for fmt in DATE_FORMATS:
        todo = out.isna()
        if not todo.any():
            break
        out[todo] = pd.to_datetime(s[todo], format=fmt, errors="coerce")
    return out


def clean_orders(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Clean the raw orders dataset according to documented business rules.
    
    Returns:
        tuple[pd.DataFrame, dict]: Cleaned orders DataFrame and an audit report.
    """
    missing = [c for c in EXPECTED_ORDER_COLUMNS if c not in raw.columns]
    if missing:
        raise DataValidationError(f"Orders data is missing required columns: {', '.join(missing)}")

    df = raw[EXPECTED_ORDER_COLUMNS].copy()
    report: dict[str, int] = {"rows_raw": len(df)}

    # 1. Deduplication: Remove exact duplicate rows (preserving legitimate multiple product lines per order)
    before_dup = len(df)
    df = df.drop_duplicates()
    report["duplicate_rows_removed"] = before_dup - len(df)

    # 2. Text standardization: strip whitespace and apply Title Case / Upper Case
    categorical_cols = ["region", "product_category", "acquisition_channel", "country", "product_name"]
    for col in categorical_cols:
        df[col] = df[col].astype("string").str.strip().str.replace(r"\s+", " ", regex=True).str.title()
    df["iso_alpha"] = df["iso_alpha"].astype("string").str.strip().str.upper()
    df["customer_id"] = df["customer_id"].astype("string").str.strip().str.upper()
    df["order_id"] = df["order_id"].astype("string").str.strip()

    # 3. Date standardization
    df["order_date"] = parse_mixed_dates(df["order_date"])
    bad_dates = int(df["order_date"].isna().sum())

    # 4. Numeric cleansing (strip currency symbols and punctuation)
    df["unit_price"] = pd.to_numeric(
        df["unit_price"].astype(str).str.replace(r"[$,€£\s]", "", regex=True),
        errors="coerce"
    )
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    df["discount"] = pd.to_numeric(df["discount"], errors="coerce")

    # 5. Non-revenue-altering imputation
    report["missing_discount_set_to_0"] = int(df["discount"].isna().sum())
    df["discount"] = df["discount"].fillna(0.0)

    # Recover missing country names using known ISO Alpha code mappings
    iso_map = (
        df.dropna(subset=["country", "iso_alpha"])
          .drop_duplicates("iso_alpha")
          .set_index("iso_alpha")["country"]
    )
    missing_country_mask = df["country"].isna()
    df.loc[missing_country_mask, "country"] = df.loc[missing_country_mask, "iso_alpha"].map(iso_map)
    report["country_recovered_from_iso"] = int(missing_country_mask.sum() - df["country"].isna().sum())
    df["country"] = df["country"].fillna("Unknown")

    report["missing_product_name_labelled_unknown"] = int(df["product_name"].isna().sum())
    df["product_name"] = df["product_name"].fillna("Unknown Product")

    # 6. Validate business rules and drop unusable records
    invalid_mask = (
        df["order_date"].isna()
        | df["customer_id"].isna()
        | df["order_id"].isna()
        | df["quantity"].isna()
        | (df["quantity"] <= 0)
        | df["unit_price"].isna()
        | (df["unit_price"] <= 0)
        | (df["discount"] < 0)
        | (df["discount"] > 1)
        | df["region"].isna()
        | df["product_category"].isna()
    )
    report["unparseable_dates"] = bad_dates
    report["invalid_rows_removed"] = int(invalid_mask.sum())
    df = df[~invalid_mask].copy()

    # 7. Derived metrics and temporal dimensions
    df["quantity"] = df["quantity"].astype(int)
    # Revenue = quantity * unit_price * (1 - discount)
    df["revenue"] = (df["quantity"] * df["unit_price"] * (1 - df["discount"])).round(2)
    df["month"] = df["order_date"].dt.to_period("M").dt.to_timestamp()
    df["year"] = df["order_date"].dt.year
    df["quarter"] = df["order_date"].dt.to_period("Q").astype(str)
    df["day_name"] = df["order_date"].dt.day_name()

    df = df.sort_values("order_date").reset_index(drop=True)
    report["rows_clean"] = len(df)

    return df, report


def clean_marketing(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Clean the raw marketing spend dataset.
    
    Returns:
        tuple[pd.DataFrame, dict]: Cleaned marketing DataFrame and an audit report.
    """
    missing = [c for c in EXPECTED_MARKETING_COLUMNS if c not in raw.columns]
    if missing:
        raise DataValidationError(f"Marketing data is missing required columns: {', '.join(missing)}")

    df = raw[EXPECTED_MARKETING_COLUMNS].copy()
    report: dict[str, int] = {"rows_raw": len(df)}

    df["region"] = df["region"].astype("string").str.strip().str.title()
    df["channel"] = df["channel"].astype("string").str.strip().str.title()
    df["month"] = pd.to_datetime(df["month"].astype(str).str.strip(), format="%Y-%m", errors="coerce")
    df["spend"] = pd.to_numeric(df["spend"], errors="coerce")

    # Drop invalid rows (missing fields or negative spend)
    invalid_mask = df.isna().any(axis=1) | (df["spend"] < 0)
    report["invalid_rows_removed"] = int(invalid_mask.sum())
    df = df[~invalid_mask].drop_duplicates().reset_index(drop=True)
    report["rows_clean"] = len(df)

    return df, report


def load_and_clean(
    orders_path: Path | str | None = None,
    marketing_path: Path | str | None = None,
    save: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, dict]]:
    """Load, clean, and optionally save processed datasets to disk."""
    raw_orders, raw_marketing = load_raw_data(orders_path, marketing_path)
    clean_orders_df, orders_report = clean_orders(raw_orders)
    clean_marketing_df, marketing_report = clean_marketing(raw_marketing)

    quality_report = {
        "orders": orders_report,
        "marketing": marketing_report,
    }

    if save:
        PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        clean_orders_df.to_csv(PROCESSED_DIR / "orders_clean.csv", index=False)
        clean_marketing_df.to_csv(PROCESSED_DIR / "marketing_spend_clean.csv", index=False)

    return clean_orders_df, clean_marketing_df, quality_report
