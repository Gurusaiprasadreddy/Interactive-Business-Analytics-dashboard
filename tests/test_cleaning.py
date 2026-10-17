import pandas as pd
import pytest

from app.cleaning import DataValidationError, clean_marketing, clean_orders, load_and_clean, _read_csv
from pathlib import Path


def _raw(**over):
    base = {"order_id": "O1", "order_date": "2024-03-05", "customer_id": "c1", "region": " europe ", "country": "France",
            "iso_alpha": "FRA", "product_category": "FASHION", "product_name": "Backpack", "quantity": 2,
            "unit_price": "$50.00", "discount": 0.1, "acquisition_channel": "email"}
    base.update(over)
    return base


def test_standardises_text_dates_and_price():
    raw = pd.DataFrame([_raw(), _raw(order_id="O2", order_date="05/03/2024"), _raw(order_id="O3", order_date="Mar 05, 2024")])
    df, rep = clean_orders(raw)
    assert set(df["region"]) == {"Europe"} and set(df["product_category"]) == {"Fashion"}
    assert (df["order_date"] == pd.Timestamp("2024-03-05")).all()
    assert (df["unit_price"] == 50.0).all()
    assert df["revenue"].iloc[0] == pytest.approx(90.0)  # 2 * 50 * 0.9


def test_removes_duplicates_and_invalid_rows():
    raw = pd.DataFrame([_raw(), _raw(), _raw(order_id="O2", quantity=-1), _raw(order_id="O3", unit_price=0),
                        _raw(order_id="O4", discount=1.5), _raw(order_id="O5", discount=None)])
    df, rep = clean_orders(raw)
    assert rep["duplicate_rows_removed"] == 1
    assert rep["invalid_rows_removed"] == 3
    assert set(df["order_id"]) == {"O1", "O5"}
    assert df.loc[df["order_id"] == "O5", "discount"].iloc[0] == 0


def test_missing_columns_raise():
    with pytest.raises(DataValidationError):
        clean_orders(pd.DataFrame({"order_id": [1]}))
    with pytest.raises(DataValidationError):
        clean_marketing(pd.DataFrame({"month": ["2024-01"]}))


def test_missing_file_raises_helpful_error(tmp_path):
    with pytest.raises(DataValidationError, match="not found"):
        _read_csv(Path(tmp_path / "nope.csv"), ["a"])


def test_full_pipeline_on_shipped_data():
    orders, mkt, rep = load_and_clean(save=False)
    assert orders["revenue"].min() > 0 and orders["order_date"].notna().all()
    assert not orders.duplicated().any()
    assert rep["orders"]["rows_clean"] == len(orders)
