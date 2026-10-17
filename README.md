# Interactive Business Analytics & KPI Dashboard

[![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.38%2B-FF4B4B.svg)](https://streamlit.io/)
[![Plotly](https://img.shields.io/badge/Plotly-6.0%2B-3F4F75.svg)](https://plotly.com/)
[![Tests](https://img.shields.io/badge/pytest-17%20passed-success.svg)](https://docs.pytest.org/)
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A full-stack, enterprise-grade Business Intelligence (BI) analytics application built for an e-commerce enterprise. Developed as an internship project in **Data Analytics & Business Intelligence**, this application provides dynamic executive performance visibility, cohort retention tracking, geographic sales intelligence, and multi-dimensional drill-downs across dates, regions, product categories, and marketing acquisition channels.

**GitHub Repository:** [https://github.com/Gurusaiprasadreddy/Interactive-Business-Analytics-dashboard](https://github.com/Gurusaiprasadreddy/Interactive-Business-Analytics-dashboard)

---

## 🏗️ Repository Architecture

The project is structured following modular engineering and clean-code best practices:

```
Interactive Dashboard & KPI Visualizations/
├── app/                              # Streamlit application layer
│   ├── components/                   # Reusable UI components
│   │   ├── filters.py                # Global sidebar filters & state manager
│   │   ├── kpi_cards.py              # Metric cards with bordered containers & deltas
│   │   └── insights_card.py          # Executive insight callout blocks
│   ├── main.py                       # Application entry point (4-page navigation)
│   ├── charts.py                     # Plotly visualization builders & theme tokens
│   ├── cleaning.py                   # Data cleaning pipeline bridge
│   ├── kpis.py                       # KPI calculation bridge
│   ├── pipeline.py                   # State filtering & KPI evaluation pipeline
│   ├── insights.py                   # Automated business rule-based insights
│   └── report.py                     # Multi-page PDF report compiler (ReportLab + Kaleido)
├── src/                              # Core analytics & calculation engine
│   ├── __init__.py                   # Source package definition
│   ├── data_loader.py                # File validation & raw data ingestion
│   ├── data_cleaning.py              # Anomaly cleansing & audit trail generation
│   ├── kpi_calculations.py          # Mathematical definitions for revenue, AOV, CAC, churn
│   └── visualizations.py             # Comprehensive Plotly visual suite
├── data/
│   ├── raw/                          # Source datasets (orders_raw.csv, marketing_spend_raw.csv)
│   └── processed/                    # Cleaned & validated datasets (orders_clean.csv, etc.)
├── reports/
│   └── dashboard.pdf                 # Pre-rendered 3-page landscape executive PDF report
├── visualizations/                   # High-resolution PNG exports of primary visual assets
├── scripts/
│   ├── export_pdf.py                 # Standalone script for PDF and PNG report generation
│   └── generate_dataset.py           # Seeded reproducible synthetic dataset generator
├── tests/                            # Automated test suite (17 passed unit tests)
│   ├── test_cleaning.py              # Cleaning & validation unit tests
│   ├── test_kpis.py                  # KPI formulas & edge-case unit tests
│   └── test_src_pipeline.py          # Integration tests for src/ modules
├── Notebook/                         # Jupyter Notebook environment
│   └── Interactive Dashboard & KPI Visualizations.ipynb
├── .streamlit/
│   └── config.toml                   # Streamlit layout & theme configuration
├── packages.txt                      # Cloud OS dependencies (Chromium for Streamlit Cloud)
├── dashboard.pdf                     # Root export copy of executive PDF
├── requirements.txt                  # Production dependencies
└── README.md                         # Project documentation
```

---

## 📊 Dataset Schema & Quality Audit

The application utilizes two primary datasets located in `data/raw/`. The raw data contains realistic e-commerce anomalies (mixed date formats, currency symbols, unparsed text, missing fields, and negative quantities) to ensure a rigorous cleaning pipeline.

### 1. `orders_raw.csv` (~18,294 records)
| Column | Raw Type | Clean Type | Description |
|---|---|---|---|
| `order_id` | String | String | Unique transaction identifier (supports multi-line product orders) |
| `order_date` | Mixed String | Datetime64 | Transaction timestamp (`YYYY-MM-DD`, `DD/MM/YYYY`, `Mon DD, YYYY`) |
| `customer_id` | String | String | Unique customer identifier |
| `region` | Unstandardized String | String | Geographical region (5 regions, Title Case) |
| `country` | String (with NaNs) | String | Customer country name (recovered via ISO code) |
| `iso_alpha` | String | String | ISO 3166-1 alpha-3 country code (e.g., `USA`, `FRA`, `DEU`) |
| `product_category` | Unstandardized String | String | Product group (`Electronics`, `Fashion`, `Home & Kitchen`, etc.) |
| `product_name` | String (with NaNs) | String | Specific item name (missing values imputed as `Unknown Product`) |
| `quantity` | Float / String | Int64 | Units purchased (negative quantities removed) |
| `unit_price` | Currency String (`$50.00`) | Float64 | Base price per unit (stripped of `$`, commas, whitespace) |
| `discount` | Float64 (with NaNs / >1.0) | Float64 | Discount rate between 0.0 and 1.0 (missing imputed as 0.0) |
| `acquisition_channel` | Unstandardized String | String | Channel attributed to customer (`Paid Search`, `Organic`, etc.) |

### 2. `marketing_spend_raw.csv` (806 records)
| Column | Raw Type | Clean Type | Description |
|---|---|---|---|
| `month` | String (`YYYY-MM`) | Datetime64 | Month start timestamp |
| `region` | Unstandardized String | String | Geographical territory of marketing expenditure |
| `channel` | Unstandardized String | String | Marketing channel (`Paid Search`, `Social Ads`, `Email`, etc.) |
| `spend` | Float64 | Float64 | Marketing expenditure in USD |

---

## 📐 KPI Mathematical Definitions & Business Rules

All metrics are derived directly from underlying dataset fields without synthetic fabrication:

| Metric | Mathematical Formula | Attribution & Methodology |
|---|---|---|
| **Total Revenue** | $$\sum \text{quantity} \times \text{unit\_price} \times (1 - \text{discount})$$ | Calculated at transaction line level. Does not assume external tax or shipping charges. |
| **Average Order Value (AOV)** | $$\frac{\text{Total Net Revenue}}{\text{Distinct Order IDs}}$$ | Computed on distinct orders ($N_{\text{distinct}}$) rather than line rows, avoiding multi-line order distortion. |
| **Customer Acquisition Cost (CAC)** | $$\frac{\sum \text{Marketing Spend}}{\text{Newly Acquired Customers}}$$ | Evaluated within matching time, region, and channel scopes. A customer is defined as "New" in the month of their earliest recorded purchase across dataset history. |
| **Customer Churn Rate** | $$\frac{\text{Customers Lost in Month } t}{\text{Active Customers at Start of Month } t}$$ | **90-Day Inactivity Proxy:** Because non-contractual e-commerce lacks formal cancellation notices, churn is modeled as 90 consecutive days without ordering. The first 120 days of data are excluded from headline calculations (warm-up period). |
| **Period-over-Period Deltas** | $$\Delta\% = \frac{\text{Value}_{\text{current}} - \text{Value}_{\text{previous}}}{\text{Value}_{\text{previous}}}$$ | Compared against an immediately preceding period of identical duration. Zero denominators and out-of-boundary prior windows return `N/A`. Churn changes are displayed in **percentage points (pp)**. |

---

## 🖥️ Dashboard Pages & Features

The dashboard provides a 4-page navigation experience via the sidebar selector:

### 📌 Page 1 — Executive Overview
- **Primary KPI Cards**: Net Revenue, Average Order Value, Customer Acquisition Cost, and Customer Churn Rate with previous-period comparison deltas.
- **Secondary Operational Metrics**: Distinct Orders, New Customer Volume, Total Marketing Spend, and Active Customer Base.
- **Revenue Performance Trendline**: Time-series area chart featuring unified tooltips, date drill-down (Month, Quarter, Year), and markers.
- **Key Metric Trendlines**: Individual trend charts for AOV, CAC, and Churn Rate.
- **Revenue Breakdown**: Stacked area view grouping revenue over time by Region, Product Category, or Acquisition Channel.
- **Automated Business Insights**: Dynamic rule-based observations highlighting top performers, CAC efficiency, and revenue trajectories.

### 🌍 Page 2 — Geography & Regions
- **Global Choropleth Map**: Country-level geographic choropleth rendered using ISO-3 codes with metric toggles (Revenue, Orders, AOV, Customers).
- **Regional Revenue Bars**: Ranked horizontal bar breakdown of regional contributions.
- **Regional Drill-Down**: Selectbox filter isolating individual regions to inspect constituent country metrics.
- **Monthly Regional Heatmap**: Matrix chart displaying revenue intensity across all five regions over time.
- **Country Performance Summary**: Formatted tabular view with revenue, distinct orders, AOV, and customer counts.

### 📦 Page 3 — Products & Acquisition
- **Category Performance**: Dual horizontal bar charts comparing Category Revenue and Category AOV.
- **Product Drill-Down**: Interactive category selector revealing top product rankings and unit volumes.
- **Volume vs. Revenue Scatter Plot**: Scatter visualization plotting order frequency against total revenue, sized by units sold.
- **Distribution Histograms**: Order-line revenue distribution with box marginal, and unit price distribution across product categories.
- **Outlier Box Plots**: Statistical box plots highlighting median, IQR, and high-value transaction outliers for revenue and prices.
- **Acquisition Channel Efficiency**: Bar charts for Marketing Spend by Channel and CAC by Channel.
- **Cohort Retention Heatmap**: Longitudinal matrix tracking quarterly customer cohorts and their re-order percentages across subsequent months.
- **Correlation Matrix & Weekday Sales**: Pearson correlation heatmap for transaction fields, and day-of-week sales volume analysis.

### 📋 Page 4 — Data Quality, Audit & PDF Report
- **Cleaning Audit Trail**: Summary table detailing row modifications, invalid data drops, country recoveries, and discount fills.
- **Monthly KPI Export**: Full tabular monthly metrics with CSV download capability.
- **Filtered Orders Export**: CSV download containing all filtered order records currently in scope.
- **PDF Dashboard Export**: Download button for the executive 3-page landscape PDF report.
- **Methodology & Assumptions**: Transparent documentation of formulas, attribution rules, and known limitations.

---

## 🚀 Running the Project Locally

### 1. Prerequisites
- Python 3.10, 3.11, or 3.12
- Google Chrome or Microsoft Edge (for PDF/PNG chart generation)

### 2. Setup Virtual Environment

#### Windows (PowerShell)
```powershell
# Navigate to the project root
cd "D:\RabTech Academy internship\Interactive Dashboard & KPI Visualizations"

# Create virtual environment (if not already created)
python -m venv .venv

# Enable script execution for current PowerShell session (if restricted)
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Install project dependencies
pip install -r requirements.txt
```

#### macOS / Linux (bash/zsh)
```bash
# Navigate to the project root
cd "Interactive Dashboard & KPI Visualizations"

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install project dependencies
pip install -r requirements.txt
```

---

### 3. Launching the Streamlit Application

You can launch the dashboard using either command:

```powershell
# Standard command (when .venv is activated)
streamlit run app/main.py

# Direct Python module command (works universally on all terminals)
python -m streamlit run app/main.py
```

The application will immediately launch and open in your default browser at:
👉 **`http://localhost:8501`**

---

### 4. Running the Test Suite
Execute the automated test suite with `pytest`:

```powershell
python -m pytest
```

Expected result:
```
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.1.1, pluggy-1.6.0
collected 17 items

tests\test_cleaning.py .....                                             [ 29%]
tests\test_kpis.py ........                                              [ 76%]
tests\test_src_pipeline.py ....                                          [100%]

======================== 17 passed, 1 warning in 3.84s ========================
```

---

### 5. Compiling the Executive PDF Report
To regenerate the 3-page landscape PDF report and static visualization PNGs:

```powershell
python scripts/export_pdf.py
```

Generated outputs:
- `reports/dashboard.pdf` (Executive 3-page landscape A4 report)
- `dashboard.pdf` (Root-level copy)
- `visualizations/*.png` (Individual chart exports)

---

## 🌐 Deployment Instructions (Streamlit Community Cloud)

To publish this dashboard live on Streamlit Community Cloud:

1. **Commit and Push Code to GitHub:**
   ```bash
   git init
   git branch -M main
   git remote add origin https://github.com/Gurusaiprasadreddy/Interactive-Business-Analytics-dashboard.git
   git add .
   git commit -m "feat: complete interactive business analytics dashboard and KPI engine"
   git push -u origin main
   ```

2. **Deploy via Streamlit Cloud:**
   - Log into [Streamlit Community Cloud](https://share.streamlit.io/).
   - Click **New app**.
   - Select your repository: `Gurusaiprasadreddy/Interactive-Business-Analytics-dashboard`.
   - Set the Branch to `main`.
   - Set the Main file path to `app/main.py`.
   - In **Advanced settings**, ensure Python 3.10+ is selected.
   - Click **Deploy!**

3. **Chromium Support for Cloud PDF Generation:**
   - The repository includes `packages.txt` with:
     ```
     chromium
     ```
   - This ensures headless Chromium is installed automatically in the Linux container for runtime PDF rendering.

---

## 🔍 Key Business Findings & Recommendations

1. **Category Profitability & Volume Divergence:**
   - **Electronics** generated the highest total revenue (~$507k, 27.0% share), driven by higher unit prices.
   - **Fashion** and **Home & Kitchen** achieved the highest distinct order counts with lower average order values ($115–$130).
   - *Recommendation:* Bundle lower-AOV fashion accessories with high-value electronics to drive cross-category basket expansion.

2. **Regional Concentration:**
   - **North America** and **Europe** represent over 48% of total e-commerce revenue.
   - Growth in **Asia Pacific** shows strong quarter-over-quarter expansion, particularly in mobile electronics.
   - *Recommendation:* Allocate localized marketing budgets toward high-growth emerging metro areas in the Asia Pacific region.

3. **Marketing Channel Efficiency (CAC vs. Volume):**
   - **Email Marketing** demonstrated the lowest Customer Acquisition Cost (~$42/customer), functioning as the most cost-effective conversion channel.
   - **Paid Search** drove the highest absolute customer acquisition volume but at a significantly higher CAC (~$112/customer).
   - *Recommendation:* Scale retargeting and automated email drip campaigns to nurture leads generated by paid search, lowering blended acquisition cost.

4. **Retention & Inactivity Patterns:**
   - The 90-day inactivity proxy indicates customer attrition stabilizes after Month 4.
   - *Recommendation:* Implement automated 60-day re-engagement workflows (discounts, product recommendations) before customers cross the 90-day inactivity threshold.

---

## 📄 License & Attribution
Developed for the **RabTech Academy Data Analytics & Business Intelligence Internship**. Source data is illustrative and designed for reproducible business intelligence benchmarking.
