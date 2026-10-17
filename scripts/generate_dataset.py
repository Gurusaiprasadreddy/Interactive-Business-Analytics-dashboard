"""Generate a realistic, deliberately messy e-commerce dataset.

Produces two raw files in data/raw/:
  * orders_raw.csv           - one row per order line (with data-quality issues)
  * marketing_spend_raw.csv  - monthly marketing spend per region and channel

The data is synthetic (no public dataset has both order-level data and
acquisition spend), but it is seeded so results are reproducible.
Run:  python scripts/generate_dataset.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
N_CUSTOMERS = 4000
START, END = "2023-01-01", "2025-12-31"

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"

REGIONS = {
    "North America": [("United States", "USA", 0.7), ("Canada", "CAN", 0.2), ("Mexico", "MEX", 0.1)],
    "Europe": [("United Kingdom", "GBR", 0.3), ("Germany", "DEU", 0.3), ("France", "FRA", 0.25), ("Spain", "ESP", 0.15)],
    "Asia Pacific": [("India", "IND", 0.35), ("Japan", "JPN", 0.25), ("Australia", "AUS", 0.2), ("Singapore", "SGP", 0.2)],
    "Latin America": [("Brazil", "BRA", 0.55), ("Argentina", "ARG", 0.25), ("Chile", "CHL", 0.2)],
    "Middle East & Africa": [("United Arab Emirates", "ARE", 0.4), ("South Africa", "ZAF", 0.35), ("Nigeria", "NGA", 0.25)],
}
REGION_WEIGHT = [0.34, 0.26, 0.24, 0.08, 0.08]

# category -> list of (product, base price)
CATALOG = {
    "Electronics": [("Wireless Earbuds", 79), ("Smart Watch", 199), ("Bluetooth Speaker", 59), ("Laptop Stand", 39)],
    "Home & Kitchen": [("Air Fryer", 119), ("Coffee Maker", 89), ("Knife Set", 64), ("Storage Bins", 29)],
    "Fashion": [("Running Shoes", 95), ("Denim Jacket", 85), ("Backpack", 55), ("Sunglasses", 45)],
    "Beauty & Health": [("Skincare Kit", 49), ("Electric Toothbrush", 69), ("Yoga Mat", 35), ("Vitamin Pack", 25)],
    "Sports & Outdoors": [("Camping Tent", 149), ("Water Bottle", 22), ("Resistance Bands", 19), ("Hiking Boots", 129)],
}
CATEGORY_WEIGHT = [0.28, 0.24, 0.22, 0.14, 0.12]

CHANNELS = {"Paid Search": 0.30, "Social Ads": 0.28, "Email": 0.10, "Affiliate": 0.14, "Organic": 0.18}
# average acquisition cost per new customer by channel (spend is allocated accordingly)
CHANNEL_CAC = {"Paid Search": 38, "Social Ads": 33, "Email": 12, "Affiliate": 27, "Organic": 6}


def build_customers(rng: np.random.Generator) -> pd.DataFrame:
    days = (pd.Timestamp(END) - pd.Timestamp(START)).days
    # acquisition ramps up over time (growth business)
    u = rng.beta(1.3, 1.0, N_CUSTOMERS)
    first_order = pd.Timestamp(START) + pd.to_timedelta((u * (days - 1)).astype(int), unit="D")
    region_names = list(REGIONS)
    region = rng.choice(region_names, N_CUSTOMERS, p=REGION_WEIGHT)
    country, iso = [], []
    for r in region:
        opts = REGIONS[r]
        i = rng.choice(len(opts), p=[o[2] for o in opts])
        country.append(opts[i][0])
        iso.append(opts[i][1])
    channel = rng.choice(list(CHANNELS), N_CUSTOMERS, p=list(CHANNELS.values()))
    # each customer has a monthly purchase propensity and a lifetime (churn)
    lifetime_days = rng.exponential(220, N_CUSTOMERS).astype(int) + 15
    rate = rng.gamma(2.0, 0.22, N_CUSTOMERS)  # expected orders per month while active
    return pd.DataFrame({
        "customer_id": [f"C{100000 + i}" for i in range(N_CUSTOMERS)],
        "first_order": first_order, "region": region, "country": country, "iso_alpha": iso,
        "channel": channel, "lifetime_days": lifetime_days, "rate": rate,
    })


def build_orders(customers: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    end = pd.Timestamp(END)
    rows = []
    cats = list(CATALOG)
    for c in customers.itertuples():
        last_active = min(c.first_order + pd.Timedelta(days=int(c.lifetime_days)), end)
        n_extra = rng.poisson(c.rate * (last_active - c.first_order).days / 30)
        dates = [c.first_order] + [
            c.first_order + pd.Timedelta(days=int(d))
            for d in rng.uniform(1, max((last_active - c.first_order).days, 2), n_extra)
        ]
        for d in dates:
            # mild seasonality: Q4 spike
            n_lines = 1 + int(rng.random() < 0.25)
            for _ in range(n_lines):
                cat = rng.choice(cats, p=CATEGORY_WEIGHT)
                product, price = CATALOG[cat][rng.integers(len(CATALOG[cat]))]
                price = round(price * rng.uniform(0.95, 1.08), 2)
                qty = int(rng.choice([1, 2, 3, 4], p=[0.68, 0.2, 0.08, 0.04]))
                discount = float(rng.choice([0, 0.05, 0.1, 0.2], p=[0.6, 0.15, 0.15, 0.1]))
                if d.month in (11, 12) and rng.random() < 0.4:
                    discount = max(discount, 0.2)
                rows.append((d, c.customer_id, c.region, c.country, c.iso_alpha, cat, product, qty, price, discount, c.channel))
    df = pd.DataFrame(rows, columns=[
        "order_date", "customer_id", "region", "country", "iso_alpha", "product_category",
        "product_name", "quantity", "unit_price", "discount", "acquisition_channel"])
    df = df.sort_values("order_date").reset_index(drop=True)
    # one order_id per (customer, date) so that multi-line orders share an id
    df["order_id"] = "O" + (df.groupby(["customer_id", "order_date"]).ngroup() + 500000).astype(str)
    return df


def build_marketing(customers: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Spend per month x region x channel = new customers acquired * channel CAC * noise."""
    c = customers.copy()
    c["month"] = c["first_order"].dt.to_period("M").dt.to_timestamp()
    g = c.groupby(["month", "region", "channel"]).size().reset_index(name="new")
    g["spend"] = (g["new"] * g["channel"].map(CHANNEL_CAC) * rng.uniform(0.85, 1.2, len(g))).round(2)
    return g.rename(columns={"channel": "channel"})[["month", "region", "channel", "spend"]]


def make_messy(orders: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Inject realistic data-quality problems for the cleaning step to fix."""
    df = orders.copy()
    n = len(df)
    # mixed date formats
    fmt = rng.choice(["%Y-%m-%d", "%d/%m/%Y", "%b %d, %Y"], n, p=[0.8, 0.1, 0.1])
    df["order_date"] = [d.strftime(f) for d, f in zip(df["order_date"], fmt)]
    # inconsistent casing / whitespace in text fields
    for col in ["region", "product_category", "acquisition_channel"]:
        idx = rng.choice(n, int(n * 0.03), replace=False)
        df.loc[idx, col] = df.loc[idx, col].str.upper()
        idx = rng.choice(n, int(n * 0.03), replace=False)
        df.loc[idx, col] = "  " + df.loc[idx, col].str.lower() + " "
    # price stored as text with currency symbol in some rows
    df["unit_price"] = df["unit_price"].astype(object)
    idx = rng.choice(n, int(n * 0.04), replace=False)
    df.loc[idx, "unit_price"] = df.loc[idx, "unit_price"].map(lambda v: f"${v}")
    # missing values
    for col, frac in [("country", 0.01), ("discount", 0.03), ("product_name", 0.02), ("quantity", 0.005), ("customer_id", 0.002)]:
        df.loc[rng.choice(n, int(n * frac), replace=False), col] = np.nan
    # invalid values
    df.loc[rng.choice(n, 15, replace=False), "quantity"] = -1
    df.loc[rng.choice(n, 10, replace=False), "unit_price"] = 0
    df.loc[rng.choice(n, 8, replace=False), "discount"] = 1.5
    # exact duplicate rows
    dup = df.sample(int(n * 0.012), random_state=SEED)
    df = pd.concat([df, dup], ignore_index=True).sample(frac=1, random_state=SEED).reset_index(drop=True)
    return df[["order_id", "order_date", "customer_id", "region", "country", "iso_alpha",
               "product_category", "product_name", "quantity", "unit_price", "discount", "acquisition_channel"]]


def main() -> None:
    rng = np.random.default_rng(SEED)
    RAW.mkdir(parents=True, exist_ok=True)
    customers = build_customers(rng)
    orders = build_orders(customers, rng)
    marketing = build_marketing(customers, rng)
    messy = make_messy(orders, rng)
    messy.to_csv(RAW / "orders_raw.csv", index=False)
    marketing["month"] = marketing["month"].dt.strftime("%Y-%m")
    marketing.to_csv(RAW / "marketing_spend_raw.csv", index=False)
    print(f"orders_raw.csv: {len(messy):,} rows | marketing_spend_raw.csv: {len(marketing):,} rows")


if __name__ == "__main__":
    main()
