"""Data loading module for Business Analytics Dashboard.

Provides robust loading of raw orders and marketing spend CSV files
with path resolution, column validation, and clear error messaging.
"""
from __future__ import annotations

from pathlib import Path
import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_RAW_DIR = ROOT_DIR / "data" / "raw"

EXPECTED_ORDER_COLUMNS = [
    "order_id",
    "order_date",
    "customer_id",
    "region",
    "country",
    "iso_alpha",
    "product_category",
    "product_name",
    "quantity",
    "unit_price",
    "discount",
    "acquisition_channel",
]

EXPECTED_MARKETING_COLUMNS = [
    "month",
    "region",
    "channel",
    "spend",
]


class DataValidationError(Exception):
    """Raised when an input file is missing, unreadable, or missing required columns."""
    pass


def load_raw_csv(path: Path | str, required_columns: list[str]) -> pd.DataFrame:
    """Read a CSV file and verify that all required columns are present."""
    file_path = Path(path)
    if not file_path.exists():
        raise DataValidationError(
            f"File not found: {file_path}. Please verify that the dataset exists in data/raw/."
        )
    try:
        df = pd.read_csv(file_path)
    except Exception as exc:
        raise DataValidationError(f"Failed to read CSV at {file_path.name}: {exc}") from exc

    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        raise DataValidationError(
            f"Dataset {file_path.name} is missing required columns: {', '.join(missing)}"
        )
    return df


def load_raw_orders(path: Path | str | None = None) -> pd.DataFrame:
    """Load the raw orders dataset."""
    target_path = Path(path) if path else DEFAULT_RAW_DIR / "orders_raw.csv"
    return load_raw_csv(target_path, EXPECTED_ORDER_COLUMNS)


def load_raw_marketing(path: Path | str | None = None) -> pd.DataFrame:
    """Load the raw marketing spend dataset."""
    target_path = Path(path) if path else DEFAULT_RAW_DIR / "marketing_spend_raw.csv"
    return load_raw_csv(target_path, EXPECTED_MARKETING_COLUMNS)


def load_raw_data(
    orders_path: Path | str | None = None,
    marketing_path: Path | str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load both raw orders and marketing spend datasets."""
    orders = load_raw_orders(orders_path)
    marketing = load_raw_marketing(marketing_path)
    return orders, marketing
