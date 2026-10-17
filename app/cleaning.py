"""Data loading and cleaning.

`clean_orders` and `clean_marketing` return a cleaned DataFrame plus a small
report (dict of step -> rows affected) that the app shows in its Data Quality
panel. Every rule is documented in README.md > Assumptions.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"

ORDER_COLUMNS = [
    "order_id", "order_date", "customer_id", "region", "country", "iso_alpha",
    "product_category", "product_name", "quantity", "unit_price", "discount", "acquisition_channel",
]
DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%b %d, %Y"]


class DataValidationError(Exception):
    """Raised when an input file is missing or does not have the expected shape."""


def _read_csv(path: Path, required: list[str]) -> pd.DataFrame:
    if not path.exists():
        raise DataValidationError(
            f"Data file not found: {path}. Run `python scripts/generate_dataset.py` "
            "or upload a CSV from the sidebar."
        )
    try:
        df = pd.read_csv(path)
    except Exception as exc:  # malformed CSV, encoding problems, ...
        raise DataValidationError(f"Could not read {path.name}: {exc}") from exc
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise DataValidationError(f"{path.name} is missing required columns: {', '.join(missing)}")
    return df


def _parse_dates(series: pd.Series) -> pd.Series:
    """Parse a column that mixes several date formats (each format tried in turn)."""
    s = series.astype(str).str.strip()
    out = pd.Series(pd.NaT, index=s.index, dtype="datetime64[ns]")
    for fmt in DATE_FORMATS:
        todo = out.isna()
        if not todo.any():
            break
        out[todo] = pd.to_datetime(s[todo], format=fmt, errors="coerce")
    return out


def clean_orders(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Clean the raw orders table. Returns (clean_df, report)."""
    missing = [c for c in ORDER_COLUMNS if c not in raw.columns]
    if missing:
        raise DataValidationError(f"Orders data is missing required columns: {', '.join(missing)}")

    df = raw[ORDER_COLUMNS].copy()
    rep: dict[str, int] = {"rows_raw": len(df)}

    # 1. exact duplicates
    before = len(df)
    df = df.drop_duplicates()
    rep["duplicate_rows_removed"] = before - len(df)

    # 2. text standardisation (strip + Title Case) for categorical fields
    for col in ["region", "product_category", "acquisition_channel", "country", "product_name"]:
        df[col] = df[col].astype("string").str.strip().str.replace(r"\s+", " ", regex=True).str.title()
    df["iso_alpha"] = df["iso_alpha"].astype("string").str.strip().str.upper()
    df["customer_id"] = df["customer_id"].astype("string").str.strip().str.upper()
    df["order_id"] = df["order_id"].astype("string").str.strip()

    # 3. dates (mixed formats)
    df["order_date"] = _parse_dates(df["order_date"])
    bad_dates = int(df["order_date"].isna().sum())

    # 4. numeric fields (strip currency symbols / commas, then coerce)
    df["unit_price"] = pd.to_numeric(
        df["unit_price"].astype(str).str.replace(r"[$,€£\s]", "", regex=True), errors="coerce")
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    df["discount"] = pd.to_numeric(df["discount"], errors="coerce")

    # 5. fill-ins that do not change revenue
    rep["missing_discount_set_to_0"] = int(df["discount"].isna().sum())
    df["discount"] = df["discount"].fillna(0.0)
    # country can be recovered from its ISO code via other rows
    iso_to_country = (df.dropna(subset=["country", "iso_alpha"])
                        .drop_duplicates("iso_alpha").set_index("iso_alpha")["country"])
    miss_country = df["country"].isna()
    df.loc[miss_country, "country"] = df.loc[miss_country, "iso_alpha"].map(iso_to_country)
    rep["country_recovered_from_iso"] = int(miss_country.sum() - df["country"].isna().sum())
    df["country"] = df["country"].fillna("Unknown")
    rep["missing_product_name_labelled_unknown"] = int(df["product_name"].isna().sum())
    df["product_name"] = df["product_name"].fillna("Unknown")

    # 6. drop rows that cannot be used for KPIs
    invalid = (
        df["order_date"].isna() | df["customer_id"].isna() | df["order_id"].isna()
        | df["quantity"].isna() | (df["quantity"] <= 0)
        | df["unit_price"].isna() | (df["unit_price"] <= 0)
        | (df["discount"] < 0) | (df["discount"] > 1)
        | df["region"].isna() | df["product_category"].isna()
    )
    rep["unparseable_dates"] = bad_dates
    rep["invalid_rows_removed"] = int(invalid.sum())
    df = df[~invalid].copy()

    # 7. derived fields
    df["quantity"] = df["quantity"].astype(int)
    df["revenue"] = (df["quantity"] * df["unit_price"] * (1 - df["discount"])).round(2)
    df["month"] = df["order_date"].dt.to_period("M").dt.to_timestamp()
    df = df.sort_values("order_date").reset_index(drop=True)

    rep["rows_clean"] = len(df)
    return df, rep


def clean_marketing(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    required = ["month", "region", "channel", "spend"]
    missing = [c for c in required if c not in raw.columns]
    if missing:
        raise DataValidationError(f"Marketing data is missing required columns: {', '.join(missing)}")
    df = raw[required].copy()
    rep = {"rows_raw": len(df)}
    df["region"] = df["region"].astype("string").str.strip().str.title()
    df["channel"] = df["channel"].astype("string").str.strip().str.title()
    df["month"] = pd.to_datetime(df["month"].astype(str).str.strip(), format="%Y-%m", errors="coerce")
    df["spend"] = pd.to_numeric(df["spend"], errors="coerce")
    bad = df.isna().any(axis=1) | (df["spend"] < 0)
    rep["invalid_rows_removed"] = int(bad.sum())
    df = df[~bad].drop_duplicates().reset_index(drop=True)
    rep["rows_clean"] = len(df)
    return df, rep


def load_and_clean(
    orders_path: Path | str | None = None,
    marketing_path: Path | str | None = None,
    save: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Read raw CSVs, clean them, optionally save to data/processed/."""
    orders_path = Path(orders_path) if orders_path else RAW_DIR / "orders_raw.csv"
    marketing_path = Path(marketing_path) if marketing_path else RAW_DIR / "marketing_spend_raw.csv"

    orders_raw = _read_csv(orders_path, ORDER_COLUMNS)
    mkt_raw = _read_csv(marketing_path, ["month", "region", "channel", "spend"])
    orders, o_rep = clean_orders(orders_raw)
    mkt, m_rep = clean_marketing(mkt_raw)
    if orders.empty:
        raise DataValidationError("No valid order rows remain after cleaning.")

    if save:
        try:
            PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
            orders.to_csv(PROCESSED_DIR / "orders_clean.csv", index=False)
            mkt.to_csv(PROCESSED_DIR / "marketing_spend_clean.csv", index=False)
        except OSError:
            pass  # read-only deployments: the app still works from memory
    return orders, mkt, {"orders": o_rep, "marketing": m_rep}


if __name__ == "__main__":
    o, m, r = load_and_clean()
    print(r)
    print(o.head())
