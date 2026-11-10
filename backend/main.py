"""
Egypt Skin Care Retail Audit Dashboard
FastAPI Backend - Main Application

This backend serves cleaned data via REST APIs for the frontend dashboard.
All data cleaning is done; this only loads, aggregates, and serves JSON.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import json
from pathlib import Path
from typing import List, Dict, Any
import numpy as np

# ============================================================================
# CONFIGURATION
# ============================================================================

# Get the path to cleaned data (one level up from backend folder)
BASE_DIR = Path(__file__).parent.parent
CLEANED_DATA_PATH = BASE_DIR / "cleaned_data.csv"

# Initialize FastAPI app
app = FastAPI(
    title="Egypt Skin Care Retail Audit Dashboard",
    description="Backend API for dashboard data aggregation and serving",
    version="1.0.0"
)

# Add CORS middleware to allow frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# CONSTANTS - derived directly from the data, not guessed
# ============================================================================

MASTER_MARKET = 'TOTAL EGYPT+PERFUMERY'

REGION_MARKETS = [
    'Total Cairo', 'Total Alexandria', 'Total Delta',
    'Total Upper Egypt', 'Total CEED'
]

CHANNEL_MARKETS = [
    'Pharmacies', 'Supermarket/Key account', 'ECOM', 'PERFUMERY',
    'COASTAL MT (NC/RS/SS)', 'Detergent Shops', 'Small groceries',
    'Large groceries', 'Haberdasheries', 'Kiosks/Haberdasheries',
    'SEMI RETAILERS'
]

HERO_BRAND_OWNER = 'LUMINA COSMETICS'  # the ONLY brand owner treated as internal/hero
ALL_PURPOSE_CREAM = 'All Purpose Cream'
PERIODS_ORDER = ['Apr-24', 'Apr-25', 'Apr-26']

# Special pseudo-period meaning "all 3 MAT years combined" -- selectable from
# the period filter alongside the 3 real periods. Wherever a function resolves
# an "anchor" period to pick/rank a single number, ALL_PERIOD resolves to the
# SUM of Apr-24 + Apr-25 + Apr-26 instead of one period's value.
ALL_PERIOD = 'ALL'
PERIODS_WITH_ALL = PERIODS_ORDER + [ALL_PERIOD]

# Product Category 1 values that are unclassified placeholders, not real product
# categories -- never offered in a category picker.
EXCLUDED_CATEGORIES = {'A Needed Malak', 'not found'}

# Values in Product Category 3 that mean "no sub-category info", across ALL
# categories (not just All Purpose Cream's '0').
JUNK_CATEGORY3 = {'0', 'nan', '', 'none'}

# A category's Category 3 field is only treated as a meaningful sub-category
# split if the named (non-junk) segments cover at least this % of the
# category's total sales, AND it isn't a single value covering ~100% of rows
# (which is degenerate -- no real contrast/Unclassified counterpart).
# Verified against the actual data: All Purpose Cream (81.9%) and Others
# (35.2%) clear this bar; Acne/Baby/Facial Care/Sun Care/Antiaging/Body Care
# all sit under 8% and are excluded; Wipes is 100% from a single value and is
# excluded by the degeneracy check below.
MIN_SEGMENT_SHARE_PCT = 15.0


def pct_growth(new_val, old_val):
    """Safe percentage growth. Returns None (not 0) when it can't be computed,
    so the frontend can render 'N/A' instead of a misleading 0%."""
    if old_val is None or new_val is None:
        return None
    if old_val == 0:
        return None
    return round(((new_val - old_val) / old_val) * 100, 2)


def safe_share(part, whole):
    if not whole:
        return 0.0
    return round((part / whole) * 100, 2)


def clean_records(records):
    """Replace NaN/inf with None so json serialization never breaks."""
    out = []
    for r in records:
        clean = {}
        for k, v in r.items():
            if isinstance(v, float) and (pd.isna(v) or np.isinf(v)):
                clean[k] = None
            else:
                clean[k] = v
        out.append(clean)
    return out


# ============================================================================
# GLOBAL DATA - LOADED ONCE AT STARTUP
# ============================================================================

df = None

@app.on_event("startup")
async def load_data():
    """Load cleaned data once when the server starts"""
    global df

    print("\n" + "="*80)
    print("FASTAPI BACKEND STARTUP")
    print("="*80)

    try:
        if not CLEANED_DATA_PATH.exists():
            raise FileNotFoundError(f"Cleaned data not found at {CLEANED_DATA_PATH}")

        print(f"\n[INFO] Loading from: {CLEANED_DATA_PATH}")
        df = pd.read_csv(CLEANED_DATA_PATH)

        # Normalize Markets: the raw data has non-breaking spaces (\xa0) inside
        # 'COASTAL MT (NC/RS/SS)' which silently breaks any exact-match filter.
        df['Markets'] = df['Markets'].astype(str).str.replace('\xa0', ' ', regex=False).str.strip()

        # Normalize Product Category 3 for the All Purpose Cream GPC/Medical split.
        # Sparse/placeholder values ('0', blank, NaN) are kept visible as
        # 'Unclassified' per the build rule, never silently dropped.
        df['Product Category 3'] = df['Product Category 3'].astype(str).str.strip()

        print(f"\n[OK] Loaded cleaned data:")
        print(f"  Rows: {len(df):,}")
        print(f"  Columns: {len(df.columns)}")
        print(f"  File: {CLEANED_DATA_PATH}")

        # Check for required columns
        required_cols = ['Markets', 'Periods', 'Sales Value', 'ITEM CODE', 'Product Category 1', 'Period_Short']
        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            print(f"\n[WARNING] Missing columns: {missing}")

        print(f"\n[OK] Data Summary:")
        print(f"  Markets unique: {df['Markets'].nunique()}")
        print(f"  Markets list: {df['Markets'].unique()[:5]}")
        print(f"  Periods: {df['Periods'].nunique()}")
        print(f"  SKUs: {df['ITEM CODE'].nunique():,}")
        print(f"  Total Sales: EGP {df['Sales Value'].sum():,.0f}")

        # Check if TOTAL EGYPT+PERFUMERY exists (case-sensitive)
        if 'TOTAL EGYPT+PERFUMERY' in df['Markets'].values:
            total_market_rows = len(df[df['Markets'] == 'TOTAL EGYPT+PERFUMERY'])
            print(f"  'TOTAL EGYPT+PERFUMERY' rows: {total_market_rows:,}")
        else:
            print(f"  [WARNING] 'TOTAL EGYPT+PERFUMERY' not found in Markets!")

        print(f"\n✓ Backend ready to serve API requests")
        print("="*80 + "\n")

    except Exception as e:
        print(f"❌ Error loading data: {str(e)}")
        import traceback
        traceback.print_exc()
        raise

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def apply_period_filter(data, period):
    """Apply period filter to data

    Args:
        data: DataFrame to filter
        period: Period string ('Apr-24', 'Apr-25', 'Apr-26') or None for all

    Returns:
        Filtered DataFrame
    """
    if period is None or period == '' or period == ALL_PERIOD:
        return data

    # Validate period
    valid_periods = ['Apr-24', 'Apr-25', 'Apr-26']
    if period not in valid_periods:
        # Return empty result for invalid period
        print(f"[WARNING] Invalid period requested: {period}")
        return data[data['Period_Short'] == period]  # Will return empty

    return data[data['Period_Short'] == period]


def get_total_market_data(period=None):
    """Get aggregated data for TOTAL MARKET (only TOTAL EGYPT+PERFUMERY)

    Args:
        period: Filter by period ('Apr-24', 'Apr-25', 'Apr-26') or None for all
    """
    # Use ONLY "TOTAL EGYPT+PERFUMERY" for total market
    total_market_df = df[df['Markets'] == 'TOTAL EGYPT+PERFUMERY'].copy()

    # Apply period filter if specified
    if period:
        total_market_df = apply_period_filter(total_market_df, period)

    # Fill NULL values in Product Category 1 with "[Unknown]" for display
    total_market_df['Product Category 1'] = total_market_df['Product Category 1'].fillna('[Unknown]')

    # Group by period and category
    agg = total_market_df.groupby(
        ['Period_Short', 'Period_Sort_Order', 'Product Category 1', 'is_unclassified'],
        as_index=False
    )['Sales Value'].sum()

    # Sort by period
    agg = agg.sort_values(['Period_Sort_Order', 'Sales Value'], ascending=[True, False])

    return agg.to_dict('records')


def get_regional_data(period=None):
    """Get data aggregated by geographic regions

    Args:
        period: Filter by period ('Apr-24', 'Apr-25', 'Apr-26') or None for all
    """
    # Define geographic markets (exclude master total)
    geo_markets = [
        'Total Alexandria', 'Total Cairo', 'Total CEED',
        'Total Delta', 'Total Upper Egypt'
    ]

    regional_df = df[df['Markets'].isin(geo_markets)].copy()

    # Apply period filter if specified
    if period:
        regional_df = apply_period_filter(regional_df, period)

    # Group by market and period
    agg = regional_df.groupby(
        ['Markets', 'Period_Short', 'Period_Sort_Order'],
        as_index=False
    )['Sales Value'].sum()

    # Sort by period then market
    agg = agg.sort_values(['Period_Sort_Order', 'Markets'])

    return agg.to_dict('records')


def get_channel_data(period=None):
    """Get data aggregated by sales channels

    Args:
        period: Filter by period ('Apr-24', 'Apr-25', 'Apr-26') or None for all
    """
    # Define channel markets (exclude geographic and master)
    geo_markets = ['Total Alexandria', 'Total Cairo', 'Total CEED', 'Total Delta', 'Total Upper Egypt']
    master = 'TOTAL EGYPT+PERFUMERY'

    channel_markets = df[
        (~df['Markets'].isin(geo_markets)) &
        (df['Markets'] != master)
    ]['Markets'].unique()

    channel_df = df[df['Markets'].isin(channel_markets)].copy()

    # Apply period filter if specified
    if period:
        channel_df = apply_period_filter(channel_df, period)

    # Group by channel and period
    agg = channel_df.groupby(
        ['Markets', 'Period_Short', 'Period_Sort_Order'],
        as_index=False
    )['Sales Value'].sum()

    # Sort by period then channel
    agg = agg.sort_values(['Period_Sort_Order', 'Markets'])

    return agg.to_dict('records')


def get_brand_data(period=None):
    """Get brand owner and brand performance data

    Args:
        period: Filter by period ('Apr-24', 'Apr-25', 'Apr-26') or None for all
    """
    brand_df_work = df.copy()

    # Apply period filter if specified
    if period:
        brand_df_work = apply_period_filter(brand_df_work, period)

    # Group by brand owner, brand, and period
    brand_df = brand_df_work.groupby(
        ['BRAND OWNER', 'BRAND', 'Period_Short', 'Period_Sort_Order'],
        as_index=False
    ).agg({
        'Sales Value': 'sum',
        'ITEM CODE': 'nunique'
    })

    brand_df.columns = ['Brand Owner', 'Brand', 'Period', 'Period_Sort', 'Sales Value', 'SKU Count']

    # Sort by period sales descending
    if period:
        # If specific period requested, sort by that period
        top_brands = brand_df.nlargest(50, 'Sales Value')['Brand'].unique()
    else:
        # If all periods, use Apr-26 for ranking
        current_period = brand_df[brand_df['Period'] == 'Apr-26'].copy()
        top_brands = current_period.nlargest(50, 'Sales Value')['Brand'].unique()

    brand_df = brand_df[brand_df['Brand'].isin(top_brands)]
    brand_df = brand_df.sort_values(['Period_Sort', 'Sales Value'], ascending=[True, False])

    # Drop the sort order column before returning
    brand_df = brand_df.drop('Period_Sort', axis=1)

    return brand_df.to_dict('records')


def get_brand_category_data(period=None):
    """Get sales data grouped by Brand Owner, Category (Product Category 1), and Period

    This powers Tab 4 - Mode 3 "Category Comparison", e.g. comparing
    LUMINA COSMETICS vs a competitor owner within a single category such as "Facial Care".

    Args:
        period: Filter by period ('Apr-24', 'Apr-25', 'Apr-26') or None for all

    Returns:
        List of records: {Brand Owner, Category, Period, Sales Value, SKU Count}
        Includes ALL brand owners/categories (not just top 50) so the frontend
        can freely switch owners/categories without extra API calls, and can
        compute each owner's share of a category's TOTAL sales (all owners).
    """
    work_df = df.copy()

    # Apply period filter if specified
    if period:
        work_df = apply_period_filter(work_df, period)

    # Fill NULL categories for consistency with get_category_analysis()
    work_df['Product Category 1'] = work_df['Product Category 1'].fillna('[Unknown]')

    cat_brand_df = work_df.groupby(
        ['BRAND OWNER', 'Product Category 1', 'Period_Short', 'Period_Sort_Order'],
        as_index=False
    ).agg({
        'Sales Value': 'sum',
        'ITEM CODE': 'nunique'
    })

    cat_brand_df.columns = ['Brand Owner', 'Category', 'Period', 'Period_Sort', 'Sales Value', 'SKU Count']
    cat_brand_df = cat_brand_df.sort_values(['Period_Sort', 'Sales Value'], ascending=[True, False])
    cat_brand_df = cat_brand_df.drop('Period_Sort', axis=1)

    return cat_brand_df.to_dict('records')


def get_sku_data(period=None, category=None):
    """Get SKU-level data for deep dive analysis

    CRITICAL FIX: the original version summed Sales Value across ALL 17
    Markets rows (5 regions + 11 channels + 1 master), which double- and
    triple-counts every SKU since those markets overlap. Total Sales here
    is now taken ONLY from Markets == TOTAL EGYPT+PERFUMERY, exactly like
    every other total-market figure in this backend. Market reach is a
    separate, legitimate count of how many of the 16 non-master markets
    (regions + channels) carry the SKU -- that's a count of distinct
    labels, not a sum, so it has no overlap problem.

    period='ALL' (the "3 years combined" pseudo-period) relies on
    apply_period_filter() treating ALL like "no filter" -- summing Sales
    Value with no Period_Short filter already produces the 3-year combined
    total, since there's nothing here that ranks/displays a single period
    otherwise.

    Args:
        period: Filter by period ('Apr-24', 'Apr-25', 'Apr-26', 'ALL') or None for all
        category: Scope to one Product Category 1 value (global category filter), or None for all
    """
    valid_categories = [c['name'] for c in get_real_categories()]
    scoped_category = category if category in valid_categories else None

    # --- Total Sales: master market only ---
    sales_df = df[df['Markets'] == MASTER_MARKET].copy()
    if scoped_category:
        sales_df = sales_df[sales_df['Product Category 1'] == scoped_category]
    if period:
        sales_df = apply_period_filter(sales_df, period)

    sales_agg = sales_df.groupby(
        ['ITEM CODE', 'ITEM', 'BRAND', 'Product Category 1'],
        as_index=False
    )['Sales Value'].sum()
    sales_agg.columns = ['Item Code', 'Item Name', 'Brand', 'Category', 'Total Sales']

    # --- Market reach: distinct non-master markets carrying the SKU ---
    reach_df = df[df['Markets'] != MASTER_MARKET].copy()
    if scoped_category:
        reach_df = reach_df[reach_df['Product Category 1'] == scoped_category]
    if period:
        reach_df = apply_period_filter(reach_df, period)

    reach_agg = reach_df.groupby('ITEM CODE', as_index=False)['Markets'].nunique()
    reach_agg.columns = ['Item Code', 'Market Count']

    sku_df = sales_agg.merge(reach_agg, on='Item Code', how='left')
    sku_df['Market Count'] = sku_df['Market Count'].fillna(0).astype(int)

    # Sort by sales
    sku_df = sku_df.sort_values('Total Sales', ascending=False)

    return sku_df.head(100).to_dict('records')  # Top 100 SKUs


def get_sku_leaderboard(category=None, segment=None, period=None, top_n=30):
    """Top N SKUs for a given category, optionally scoped to one adaptive
    segment (e.g. GPC or Medical within All Purpose Cream), with the full
    multi-MAT table: Brand, SKU/Item (separate columns), MAT/MAT-1/MAT-2
    sales value, and both growth percentages.

    Scope: Markets == TOTAL EGYPT+PERFUMERY only (never sum across the 17
    overlapping markets -- same rule as everywhere else in this backend).
    """
    anchor = period if period in PERIODS_WITH_ALL else 'Apr-26'

    valid_categories = [c['name'] for c in get_real_categories()]
    if category not in valid_categories:
        category = ALL_PURPOSE_CREAM

    base = df[(df['Markets'] == MASTER_MARKET) & (df['Product Category 1'] == category)].copy()
    has_segments, segment_names = detect_segments(base)

    if has_segments:
        base['SubCategory'] = base['Product Category 3'].apply(
            lambda v: v if v in segment_names else 'Unclassified'
        )
    else:
        base['SubCategory'] = 'Overall'

    names_to_render = segment_names if has_segments else ['Overall']
    if segment in names_to_render:
        scoped = base[base['SubCategory'] == segment]
        resolved_segment = segment
    else:
        scoped = base
        resolved_segment = None

    by_period = scoped.groupby(
        ['ITEM CODE', 'ITEM', 'BRAND', 'Period_Short']
    )['Sales Value'].sum().unstack(fill_value=0)
    for p in PERIODS_ORDER:
        if p not in by_period.columns:
            by_period[p] = 0.0
    by_period = by_period[PERIODS_ORDER]
    by_period = _add_all_col(by_period)
    ranked = by_period.sort_values(anchor, ascending=False)

    records = []
    for (item_code, item, brand), row in ranked.head(top_n).iterrows():
        records.append({
            'item_code': item_code,
            'sku': item,
            'brand': brand,
            'Apr-24': float(row['Apr-24']),
            'Apr-25': float(row['Apr-25']),
            'Apr-26': float(row['Apr-26']),
            'growth_24_25_pct': pct_growth(row['Apr-25'], row['Apr-24']),
            'growth_25_26_pct': pct_growth(row['Apr-26'], row['Apr-25']),
        })

    return {
        'anchor_period': anchor,
        'category': category,
        'has_segments': has_segments,
        'segment_names': names_to_render,
        'segment': resolved_segment,
        'skus': records,
    }


def calculate_yoy_comparison(period=None):
    """Calculate year-over-year comparisons

    Args:
        period: Filter by period ('Apr-24', 'Apr-25', 'Apr-26') or None for all
    """
    # Use only TOTAL EGYPT+PERFUMERY
    total_market_df = df[df['Markets'] == 'TOTAL EGYPT+PERFUMERY'].copy()

    # If specific period, calculate growth vs previous period
    if period:
        total_market_df = apply_period_filter(total_market_df, period)

        period_sales = total_market_df['Sales Value'].sum()
        yoy = {'Current Period Sales': round(period_sales, 2)}

        # Map period to previous period
        period_map = {'Apr-25': 'Apr-24', 'Apr-26': 'Apr-25'}
        if period in period_map:
            prev_period = period_map[period]
            prev_df = df[(df['Markets'] == 'TOTAL EGYPT+PERFUMERY') & (df['Period_Short'] == prev_period)]
            prev_sales = prev_df['Sales Value'].sum()

            if prev_sales > 0:
                growth = ((period_sales - prev_sales) / prev_sales) * 100
                yoy['Growth %'] = round(growth, 2)
            else:
                yoy['Growth %'] = None

        return yoy

    # If no period specified, return all comparisons
    by_period = total_market_df.groupby('Period_Short')['Sales Value'].sum()

    yoy = {}
    if 'Apr-25' in by_period.index and 'Apr-26' in by_period.index:
        growth_25_26 = ((by_period['Apr-26'] - by_period['Apr-25']) / by_period['Apr-25']) * 100
        yoy['Apr-26 vs Apr-25'] = round(growth_25_26, 2)

    if 'Apr-24' in by_period.index and 'Apr-25' in by_period.index:
        growth_24_25 = ((by_period['Apr-25'] - by_period['Apr-24']) / by_period['Apr-24']) * 100
        yoy['Apr-25 vs Apr-24'] = round(growth_24_25, 2)

    return yoy


def get_category_analysis(period=None):
    """Get category performance analysis

    Args:
        period: Filter by period ('Apr-24', 'Apr-25', 'Apr-26') or None for all
    """
    # Use only TOTAL EGYPT+PERFUMERY
    total_market_df = df[df['Markets'] == 'TOTAL EGYPT+PERFUMERY'].copy()

    # Apply period filter if specified
    if period:
        total_market_df = apply_period_filter(total_market_df, period)

    # Group by category and period
    cat_agg = total_market_df.groupby(
        ['Product Category 1', 'Period_Short'],
        as_index=False
    )['Sales Value'].sum()

    # Pivot to get periods as columns
    cat_pivot = cat_agg.pivot(index='Product Category 1', columns='Period_Short', values='Sales Value')
    cat_pivot = cat_pivot.fillna(0)

    # Calculate totals
    cat_pivot['Total'] = cat_pivot.sum(axis=1)
    cat_pivot = cat_pivot.sort_values('Total', ascending=False)

    return cat_pivot.to_dict('index')


# ============================================================================
# NEW ARCHITECTURE HELPER FUNCTIONS
# (Overview / Brand Owners / Brand Level / Channels & Regions analysis)
# ============================================================================

def _period_series(frame, group_col=None):
    """Sum Sales Value by Period_Short (and optionally another column),
    guaranteeing all 3 periods are present even if a group has 0 sales.
    Also adds an 'ALL' key/column = the 3-year combined sum, so any code
    that looks a value up by anchor period transparently gets the combined
    total when anchor == ALL_PERIOD ('ALL')."""
    if group_col:
        pivot = frame.groupby([group_col, 'Period_Short'])['Sales Value'].sum().unstack(fill_value=0)
        for p in PERIODS_ORDER:
            if p not in pivot.columns:
                pivot[p] = 0.0
        pivot = pivot[PERIODS_ORDER]
        pivot[ALL_PERIOD] = pivot[PERIODS_ORDER].sum(axis=1)
        return pivot
    else:
        s = frame.groupby('Period_Short')['Sales Value'].sum()
        out = {p: float(s.get(p, 0.0)) for p in PERIODS_ORDER}
        out[ALL_PERIOD] = sum(out.values())
        return out


def _add_all_col(pivot_df):
    """Add an 'ALL' column (3-year combined sum) to a Period-columned pivot
    DataFrame built directly via groupby/unstack (i.e. not through
    _period_series). Must be called right after the frame is reindexed to
    exactly PERIODS_ORDER, before any ranking/anchor lookup happens."""
    pivot_df[ALL_PERIOD] = pivot_df[PERIODS_ORDER].sum(axis=1)
    return pivot_df


def get_real_categories():
    """List of real product categories (Product Category 1), excluding the
    unclassified placeholders 'A Needed Malak' and 'not found'. Sorted by
    total sales value descending, using TOTAL EGYPT+PERFUMERY across all
    periods so the ordering is stable regardless of which period is selected.
    """
    tm = df[df['Markets'] == MASTER_MARKET]
    tm = tm[~tm['Product Category 1'].isin(EXCLUDED_CATEGORIES)]
    totals = tm.groupby('Product Category 1')['Sales Value'].sum().sort_values(ascending=False)
    return [
        {'name': name, 'total_sales': float(val)}
        for name, val in totals.items()
    ]


def detect_segments(category_df):
    """Decide whether Product Category 3 gives a meaningful sub-category split
    for this slice of data (already filtered to one Product Category 1 value,
    across ALL periods so the decision is period-independent).

    Returns (has_segments: bool, segment_names: list[str] sorted by sales desc).
    A segment set is meaningful only if the named (non-junk) values cover at
    least MIN_SEGMENT_SHARE_PCT of total sales, and it isn't a single value
    covering ~100% of rows (that's degenerate -- no real contrast, just a
    relabeled 'everything', e.g. Wipes' 'Wipes3' value).
    """
    total = category_df['Sales Value'].sum()
    if not total:
        return False, []

    by_cat3 = category_df.groupby('Product Category 3')['Sales Value'].sum()
    real = {k: v for k, v in by_cat3.items() if k.lower() not in JUNK_CATEGORY3}
    if not real:
        return False, []

    real_total = sum(real.values())
    real_share_pct = (real_total / total) * 100

    degenerate = len(real) == 1 and real_share_pct >= 99.0
    meaningful = real_share_pct >= MIN_SEGMENT_SHARE_PCT and not degenerate

    if not meaningful:
        return False, []

    segment_names = [k for k, v in sorted(real.items(), key=lambda kv: kv[1], reverse=True)]
    return True, segment_names


def get_overview_data(period=None, category=None):
    """Total Market -> selected category -> Product Category 3 sub-category split.

    CRITICAL: All figures use ONLY Markets == 'TOTAL EGYPT+PERFUMERY'.
    Adaptive across ALL real categories (same detect_segments() logic as
    Brand Level / Channels / Regions): when Product Category 3 gives a meaningful
    split (e.g. GPC/Medical for All Purpose Cream), 'subcategories' has one
    entry per real segment plus 'Unclassified'; otherwise a single 'Overall'
    entry covering the whole category. Defaults to All Purpose Cream when no
    (valid) category is given, matching this page's original scope.
    """
    anchor = period if period in PERIODS_WITH_ALL else 'Apr-26'

    valid_categories = [c['name'] for c in get_real_categories()]
    if category not in valid_categories:
        category = ALL_PURPOSE_CREAM

    total_market_df = df[df['Markets'] == MASTER_MARKET]
    total_market_by_period = _period_series(total_market_df)

    cat_df = total_market_df[total_market_df['Product Category 1'] == category].copy()
    cat_by_period = _period_series(cat_df)

    has_segments, segment_names = detect_segments(cat_df)
    if has_segments:
        cat_df['SubCategory'] = cat_df['Product Category 3'].apply(
            lambda v: v if v in segment_names else 'Unclassified'
        )
        names_to_render = segment_names + ['Unclassified']
    else:
        cat_df['SubCategory'] = 'Overall'
        names_to_render = ['Overall']

    subcats = []
    for name in names_to_render:
        sub_df = cat_df[cat_df['SubCategory'] == name]
        by_period = _period_series(sub_df)
        subcats.append({
            'name': name,
            'values': by_period,
            'share_of_category_pct': safe_share(by_period[anchor], cat_by_period[anchor]),
            'growth_24_25_pct': pct_growth(by_period['Apr-25'], by_period['Apr-24']),
            'growth_25_26_pct': pct_growth(by_period['Apr-26'], by_period['Apr-25']),
        })

    return {
        'anchor_period': anchor,
        'total_market': {
            'values': total_market_by_period,
            'growth_24_25_pct': pct_growth(total_market_by_period['Apr-25'], total_market_by_period['Apr-24']),
            'growth_25_26_pct': pct_growth(total_market_by_period['Apr-26'], total_market_by_period['Apr-25']),
        },
        'category': {
            'name': category,
            'values': cat_by_period,
            'share_of_total_market_pct': safe_share(cat_by_period[anchor], total_market_by_period[anchor]),
            'growth_24_25_pct': pct_growth(cat_by_period['Apr-25'], cat_by_period['Apr-24']),
            'growth_25_26_pct': pct_growth(cat_by_period['Apr-26'], cat_by_period['Apr-25']),
            'fact_count': int(len(cat_df)),
        },
        'has_segments': has_segments,
        'subcategories': subcats,
    }


def get_brand_owners_data(period=None, top_n=None, category=None):
    """Brand owner ranking + multi-MAT growth table.
    Scope: Markets == TOTAL EGYPT+PERFUMERY. Scoped to a single Product Category 1
    when `category` is given (the global category filter applies here too);
    otherwise covers ALL categories, the original default.

    top_n=None (default) returns EVERY brand owner that has non-zero sales in
    at least one of the 3 MAT periods -- the client's requirement doc doesn't
    specify a cutoff for this section (unlike "Top 30 Brands" elsewhere), so
    we don't invent one. Owners with zero sales across all 3 periods are
    dropped as data noise, not truncated as a ranking cutoff.
    """
    anchor = period if period in PERIODS_WITH_ALL else 'Apr-26'

    valid_categories = [c['name'] for c in get_real_categories()]
    scoped_category = category if category in valid_categories else None

    bo_df = df[df['Markets'] == MASTER_MARKET].copy()
    if scoped_category:
        bo_df = bo_df[bo_df['Product Category 1'] == scoped_category]
    bo_df['BRAND OWNER'] = bo_df['BRAND OWNER'].fillna('[Unknown]')

    by_period = bo_df.groupby(['BRAND OWNER', 'Period_Short'])['Sales Value'].sum().unstack(fill_value=0)
    for p in PERIODS_ORDER:
        if p not in by_period.columns:
            by_period[p] = 0.0
    by_period = by_period[PERIODS_ORDER]
    by_period = _add_all_col(by_period)

    # Drop owners with zero sales in all 3 periods -- noise, not a real ranking cutoff.
    by_period = by_period[(by_period[PERIODS_ORDER] != 0).any(axis=1)]

    total_at_anchor = by_period[anchor].sum()
    ranked = by_period.sort_values(anchor, ascending=False)
    if top_n:
        ranked = ranked.head(top_n)

    records = []
    for rank, (owner, row) in enumerate(ranked.iterrows(), start=1):
        records.append({
            'rank': rank,
            'brand_owner': owner,
            'is_hero': owner == HERO_BRAND_OWNER,
            'Apr-24': float(row['Apr-24']),
            'Apr-25': float(row['Apr-25']),
            'Apr-26': float(row['Apr-26']),
            'growth_24_25_pct': pct_growth(row['Apr-25'], row['Apr-24']),
            'growth_25_26_pct': pct_growth(row['Apr-26'], row['Apr-25']),
            'share_pct': safe_share(row[anchor], total_at_anchor),
        })

    return {
        'anchor_period': anchor,
        'category': scoped_category,
        'total_market_at_anchor': float(total_at_anchor),
        'brand_owners': records,
        'count': len(records),
    }


def get_brand_level_data(category=None, period=None):
    """Brand-level drilldown for ANY real category (adaptive).

    If Product Category 3 gives a meaningful split for this category (verified
    via detect_segments), 'segments' has one entry per real segment
    (e.g. GPC, Medical for All Purpose Cream). If not, 'segments' has a
    single entry named 'Overall' covering the whole category -- so the
    frontend can always just loop over 'segments', no special-casing needed.
    """
    anchor = period if period in PERIODS_WITH_ALL else 'Apr-26'

    valid_categories = [c['name'] for c in get_real_categories()]
    if category not in valid_categories:
        category = ALL_PURPOSE_CREAM

    total_market_df = df[df['Markets'] == MASTER_MARKET]
    total_market_by_period = _period_series(total_market_df)

    cat_df = total_market_df[total_market_df['Product Category 1'] == category].copy()
    has_segments, segment_names = detect_segments(cat_df)

    if has_segments:
        cat_df['SubCategory'] = cat_df['Product Category 3'].apply(
            lambda v: v if v in segment_names else 'Unclassified'
        )
    else:
        cat_df['SubCategory'] = 'Overall'

    universe_by_period = _period_series(cat_df)

    BRAND_TOP_N = 30  # "Brand Performance (Top 30 Brands)" requirement

    def leader_and_topN(sub_name):
        sub_df = cat_df[cat_df['SubCategory'] == sub_name]
        sub_by_period = _period_series(sub_df)
        anchor_total = float(sub_by_period[anchor])
        cat_anchor_total = float(universe_by_period[anchor])

        # Full multi-MAT brand performance table for this segment: Top 30
        # brands by anchor-period sales, each with MAT/MAT-1/MAT-2 values,
        # both growth figures, and BOTH contribution metrics (to the whole
        # category, and to this segment specifically).
        brand_by_period = sub_df.groupby(['BRAND', 'Period_Short'])['Sales Value'].sum().unstack(fill_value=0)
        for p in PERIODS_ORDER:
            if p not in brand_by_period.columns:
                brand_by_period[p] = 0.0
        brand_by_period = brand_by_period[PERIODS_ORDER]
        brand_by_period = _add_all_col(brand_by_period)
        ranked = brand_by_period.sort_values(anchor, ascending=False)

        top30 = []
        for brand, row in ranked.head(BRAND_TOP_N).iterrows():
            anchor_val = float(row[anchor])
            top30.append({
                'brand': brand,
                'Apr-24': float(row['Apr-24']),
                'Apr-25': float(row['Apr-25']),
                'Apr-26': float(row['Apr-26']),
                'growth_24_25_pct': pct_growth(row['Apr-25'], row['Apr-24']),
                'growth_25_26_pct': pct_growth(row['Apr-26'], row['Apr-25']),
                'share_of_category_pct': safe_share(anchor_val, cat_anchor_total),
                'share_of_subcategory_pct': safe_share(anchor_val, anchor_total),
            })
        leader = top30[0] if top30 else None

        return {
            'name': sub_name,
            'values': sub_by_period,
            'share_of_category_pct': safe_share(anchor_total, cat_anchor_total),
            'share_of_total_market_pct': safe_share(anchor_total, float(total_market_by_period[anchor])),
            'growth_24_25_pct': pct_growth(sub_by_period['Apr-25'], sub_by_period['Apr-24']),
            'growth_25_26_pct': pct_growth(sub_by_period['Apr-26'], sub_by_period['Apr-25']),
            'leader': leader,
            'top10': top30[:10],  # compact list, used by the existing bar-chart leader cards
            'top30': top30,       # full "Brand Performance" table (MAT x3 + growth + both contributions)
        }

    names_to_render = segment_names if has_segments else ['Overall']
    segments = [leader_and_topN(name) for name in names_to_render]

    # Top brands trend/table across the WHOLE category (any sub-category) --
    # used for the cross-segment trend chart and the category-wide ranking.
    brand_by_period = cat_df.groupby(['BRAND', 'Period_Short'])['Sales Value'].sum().unstack(fill_value=0)
    for p in PERIODS_ORDER:
        if p not in brand_by_period.columns:
            brand_by_period[p] = 0.0
    brand_by_period = brand_by_period[PERIODS_ORDER]
    brand_by_period = _add_all_col(brand_by_period)
    ranked_brands = brand_by_period.sort_values(anchor, ascending=False)
    cat_anchor_total = float(universe_by_period[anchor])

    def brand_records(n):
        recs = []
        for brand, row in ranked_brands.head(n).iterrows():
            anchor_val = float(row[anchor])
            recs.append({
                'brand': brand,
                'Apr-24': float(row['Apr-24']),
                'Apr-25': float(row['Apr-25']),
                'Apr-26': float(row['Apr-26']),
                'growth_24_25_pct': pct_growth(row['Apr-25'], row['Apr-24']),
                'growth_25_26_pct': pct_growth(row['Apr-26'], row['Apr-25']),
                'share_of_category_pct': safe_share(anchor_val, cat_anchor_total),
            })
        return recs

    top6 = brand_records(6)
    top30 = brand_records(BRAND_TOP_N)
    # NOTE: sum from the pandas frame (which has the 'ALL' column added by
    # _add_all_col), not from the `top30` record dicts -- those only carry
    # explicit 'Apr-24'/'Apr-25'/'Apr-26' keys, not a literal 'ALL' key.
    top30_anchor_sum = float(ranked_brands.head(BRAND_TOP_N)[anchor].sum())
    top30_contribution_pct = safe_share(top30_anchor_sum, cat_anchor_total)

    return {
        'anchor_period': anchor,
        'category': category,
        'has_segments': has_segments,
        'universe': {
            'values': universe_by_period,
            'growth_24_25_pct': pct_growth(universe_by_period['Apr-25'], universe_by_period['Apr-24']),
            'growth_25_26_pct': pct_growth(universe_by_period['Apr-26'], universe_by_period['Apr-25']),
            'brands_tracked': int(cat_df['BRAND'].nunique()),
        },
        'segments': segments,
        'top6_trend': top6,
        'top15': top30,  # kept for backward compatibility with older frontend code
        'top30': top30,
        'top15_contribution_pct': top30_contribution_pct,  # backward-compat alias
        'top30_contribution_pct': top30_contribution_pct,
    }


def _market_contribution_to_total(market_list, dimension_name, period=None):
    """Each market's (channel's/region's) share of the ENTIRE total market,
    across ALL categories -- NOT scoped to any single category. This answers
    "channel/region contribution to Total Market", separate from the
    category-scoped 'contribution_by_channel/region' below.
    """
    anchor = period if period in PERIODS_WITH_ALL else 'Apr-26'

    total_market_by_period = _period_series(df[df['Markets'] == MASTER_MARKET])
    scoped = df[df['Markets'].isin(market_list)]

    by_period = scoped.groupby(['Markets', 'Period_Short'])['Sales Value'].sum().unstack(fill_value=0)
    for p in PERIODS_ORDER:
        if p not in by_period.columns:
            by_period[p] = 0.0
    by_period = by_period[PERIODS_ORDER]
    by_period = _add_all_col(by_period)
    ranked = by_period.sort_values(anchor, ascending=False)

    total_at_anchor = float(total_market_by_period[anchor])
    records = []
    for market, row in ranked.iterrows():
        records.append({
            dimension_name: market,
            'Apr-24': float(row['Apr-24']),
            'Apr-25': float(row['Apr-25']),
            'Apr-26': float(row['Apr-26']),
            'growth_24_25_pct': pct_growth(row['Apr-25'], row['Apr-24']),
            'growth_25_26_pct': pct_growth(row['Apr-26'], row['Apr-25']),
            'share_of_total_market_pct': safe_share(float(row[anchor]), total_at_anchor),
        })
    return records


def _channel_or_region_analysis(period, market_list, dimension_name, category=None):
    """Shared logic for Channels and Regions pages, for ANY real category.

    Adaptive segments same as get_brand_level_data: if Product Category 3 gives
    a meaningful split, 'segments' has one entry per real segment; otherwise
    a single 'Overall' entry covering the whole category. Frontend always
    just loops over 'segments'.
    """
    anchor = period if period in PERIODS_WITH_ALL else 'Apr-26'

    valid_categories = [c['name'] for c in get_real_categories()]
    if category not in valid_categories:
        category = ALL_PURPOSE_CREAM

    scoped = df[
        (df['Markets'].isin(market_list)) &
        (df['Product Category 1'] == category)
    ].copy()

    has_segments, segment_names = detect_segments(scoped)
    if has_segments:
        scoped['SubCategory'] = scoped['Product Category 3'].apply(
            lambda v: v if v in segment_names else 'Unclassified'
        )
    else:
        scoped['SubCategory'] = 'Overall'

    # When anchor == ALL_PERIOD there's no single Period_Short row to filter
    # to -- "anchor_df" becomes the whole (all-periods) scoped frame instead,
    # so every downstream sum below is a 3-year combined total.
    if anchor == ALL_PERIOD:
        anchor_df = scoped
    else:
        anchor_df = scoped[scoped['Period_Short'] == anchor]
    names_to_render = segment_names if has_segments else ['Overall']

    def contribution(sub_name):
        sub_anchor = anchor_df[anchor_df['SubCategory'] == sub_name]
        by_market = sub_anchor.groupby('Markets')['Sales Value'].sum().sort_values(ascending=False)
        total = float(by_market.sum())
        return [
            {dimension_name: m, 'sales': float(v), 'share_pct': safe_share(v, total)}
            for m, v in by_market.items()
        ]

    contribution_by_segment = {name: contribution(name) for name in names_to_render}

    drilldown = {}
    for market in market_list:
        # Use ALL periods (not just anchor_df) so the Top 10 brand list can
        # carry MAT/MAT-1/MAT-2 + growth, not just a single anchor value.
        market_df_all_periods = scoped[scoped['Markets'] == market]
        market_total_anchor = float(anchor_df[anchor_df['Markets'] == market]['Sales Value'].sum())
        entry = {'total_sales': market_total_anchor, 'segments': {}}
        for name in names_to_render:
            sub_df_all = market_df_all_periods[market_df_all_periods['SubCategory'] == name]
            sub_total_anchor = float(
                anchor_df[(anchor_df['Markets'] == market) & (anchor_df['SubCategory'] == name)]['Sales Value'].sum()
            )

            brand_by_period = sub_df_all.groupby(['BRAND', 'Period_Short'])['Sales Value'].sum().unstack(fill_value=0)
            for p in PERIODS_ORDER:
                if p not in brand_by_period.columns:
                    brand_by_period[p] = 0.0
            brand_by_period = brand_by_period[PERIODS_ORDER]
            brand_by_period = _add_all_col(brand_by_period)
            ranked_brands = brand_by_period.sort_values(anchor, ascending=False)

            top10 = []
            for brand, row in ranked_brands.head(10).iterrows():
                anchor_val = float(row[anchor])
                top10.append({
                    'brand': brand,
                    'Apr-24': float(row['Apr-24']),
                    'Apr-25': float(row['Apr-25']),
                    'Apr-26': float(row['Apr-26']),
                    'growth_24_25_pct': pct_growth(row['Apr-25'], row['Apr-24']),
                    'growth_25_26_pct': pct_growth(row['Apr-26'], row['Apr-25']),
                    'sales': anchor_val,  # backward-compat with existing bar-list rendering
                    'share_pct': safe_share(anchor_val, sub_total_anchor),
                })

            entry['segments'][name] = {
                'total_sales': sub_total_anchor,
                'top10': top10,
            }
        drilldown[market] = entry

    total_market_contribution = _market_contribution_to_total(market_list, dimension_name, period)

    return {
        'anchor_period': anchor,
        'category': category,
        'has_segments': has_segments,
        'segment_names': names_to_render,
        f'contribution_by_{dimension_name}': contribution_by_segment,
        'total_market_contribution': total_market_contribution,
        'drilldown': drilldown,
    }


def get_channels_analysis(period=None, category=None):
    return _channel_or_region_analysis(period, CHANNEL_MARKETS, 'channel', category)


def get_regions_analysis(period=None, category=None):
    return _channel_or_region_analysis(period, REGION_MARKETS, 'region', category)


# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint - API documentation"""
    return {
        "message": "Egypt Skin Care Retail Audit Dashboard API",
        "version": "1.0.0",
        "endpoints": {
            "total-market": "/api/total-market",
            "regions": "/api/regions",
            "channels": "/api/channels",
            "brands": "/api/brands",
            "skus": "/api/skus",
            "sku-leaderboard": "/api/sku-leaderboard",
            "yoy-comparison": "/api/yoy-comparison",
            "category-analysis": "/api/category-analysis",
            "brand-category-comparison": "/api/brand-category-comparison",
            "overview": "/api/overview",
            "categories": "/api/categories",
            "brand-owners": "/api/brand-owners",
            "brand-level": "/api/brand-level",
            "channels-analysis": "/api/channels-analysis",
            "regions-analysis": "/api/regions-analysis",
            "health": "/health"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "data_loaded": df is not None,
        "rows": len(df) if df is not None else 0
    }


@app.get("/api/total-market")
async def total_market(period: str = None):
    """
    Get total market data for TOTAL EGYPT+PERFUMERY

    Returns aggregated sales by category and period
    Used for: Tab 0 (Executive Summary), Tab 1 (Total Market)

    Query Parameters:
        period: Period filter ('Apr-24', 'Apr-25', 'Apr-26') or None for all
    """
    try:
        print(f"[API] /api/total-market requested with period={period}")
        data = get_total_market_data(period)
        return {
            "success": True,
            "data": data,
            "count": len(data),
            "requested_period": period
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/regions")
async def regions(period: str = None):
    """
    Get regional (geographic) data

    Returns sales aggregated by 5 geographic regions and period
    Used for: Tab 2 (Regions)

    Query Parameters:
        period: Period filter ('Apr-24', 'Apr-25', 'Apr-26') or None for all
    """
    try:
        print(f"[API] /api/regions requested with period={period}")
        data = get_regional_data(period)
        return {
            "success": True,
            "data": data,
            "count": len(data),
            "requested_period": period
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/channels")
async def channels(period: str = None):
    """
    Get channel (distribution) data

    Returns sales aggregated by sales channels and period
    Used for: Tab 3 (Channels)

    Query Parameters:
        period: Period filter ('Apr-24', 'Apr-25', 'Apr-26') or None for all
    """
    try:
        print(f"[API] /api/channels requested with period={period}")
        data = get_channel_data(period)
        return {
            "success": True,
            "data": data,
            "count": len(data),
            "requested_period": period
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/brands")
async def brands(period: str = None):
    """
    Get brand performance data

    Returns top brands with sales and SKU count by period
    Used for: Tab 4 (Brand Owner & Brand)

    Query Parameters:
        period: Period filter ('Apr-24', 'Apr-25', 'Apr-26') or None for all
    """
    try:
        print(f"[API] /api/brands requested with period={period}")
        data = get_brand_data(period)
        return {
            "success": True,
            "data": data,
            "count": len(data),
            "requested_period": period
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/brand-category-comparison")
async def brand_category_comparison(period: str = None):
    """
    Get sales data grouped by Brand Owner, Category, and Period.

    Returns ALL brand owners and ALL categories (not top-50 limited) so the
    frontend can let the user pick any two owners (e.g. LUMINA COSMETICS vs
    a competitor) and any category (e.g. Facial Care) and compute sales, market
    share (within that category), growth, and category breakdown client-side.

    Used for: Tab 4 (Brands & Compete) - Mode 3 "Category Comparison"

    Query Parameters:
        period: Period filter ('Apr-24', 'Apr-25', 'Apr-26') or None for all
    """
    try:
        print(f"[API] /api/brand-category-comparison requested with period={period}")
        data = get_brand_category_data(period)
        return {
            "success": True,
            "data": data,
            "count": len(data),
            "requested_period": period
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/skus")
async def skus(period: str = None, category: str = None):
    """
    Get SKU-level data

    Returns top 100 SKUs with sales and market reach, scoped to `category`
    when given (the global category filter), else all categories.
    Used for: Tab 5 (SKU Deep Dive)

    Query Parameters:
        period: Period filter ('Apr-24', 'Apr-25', 'Apr-26', 'ALL') or None for all
        category: Scope to one Product Category 1 value, or None for all categories
    """
    try:
        print(f"[API] /api/skus requested with period={period} category={category}")
        data = get_sku_data(period, category)
        return {
            "success": True,
            "data": data,
            "count": len(data),
            "requested_period": period
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sku-leaderboard")
async def sku_leaderboard(period: str = None, category: str = None, segment: str = None):
    """
    Top 30 SKUs for a category, optionally scoped to one adaptive segment
    (e.g. segment=GPC or segment=Medical for All Purpose Cream). Brand and
    SKU/Item are returned as separate fields.
    Used for: SKUs page, GPC/Medical Top 30 SKU tables.
    """
    try:
        print(f"[API] /api/sku-leaderboard requested with period={period} category={category} segment={segment}")
        data = get_sku_leaderboard(category, segment, period)
        return {"success": True, "data": data, "requested_period": period}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/yoy-comparison")
async def yoy_comparison(period: str = None):
    """
    Get year-over-year comparison

    Returns YoY growth percentages for total market
    Used for: Tab 0 (Executive Summary) KPIs

    Query Parameters:
        period: Period filter ('Apr-24', 'Apr-25', 'Apr-26') or None for all
    """
    try:
        print(f"[API] /api/yoy-comparison requested with period={period}")
        data = calculate_yoy_comparison(period)
        return {
            "success": True,
            "data": data,
            "requested_period": period
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/category-analysis")
async def category_analysis(period: str = None):
    """
    Get category analysis

    Returns category performance across periods
    Used for: Tab 1 (Total Market) - category breakdown

    Query Parameters:
        period: Period filter ('Apr-24', 'Apr-25', 'Apr-26') or None for all
    """
    try:
        print(f"[API] /api/category-analysis requested with period={period}")
        data = get_category_analysis(period)
        return {
            "success": True,
            "data": data,
            "requested_period": period
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/overview")
async def overview(period: str = None, category: str = None):
    """
    Total Market -> selected category -> adaptive Category 3 sub-split overview.
    Defaults to All Purpose Cream when no category is given. Used for: Overview page.
    """
    try:
        print(f"[API] /api/overview requested with period={period} category={category}")
        data = get_overview_data(period, category)
        return {"success": True, "data": data, "requested_period": period}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/brand-owners")
async def brand_owners(period: str = None, category: str = None):
    """
    Brand owner ranking + multi-MAT growth table (TOTAL EGYPT+PERFUMERY).
    Scoped to `category` when given (the global category filter), else all categories.
    Used for: Brand Owners page.
    """
    try:
        print(f"[API] /api/brand-owners requested with period={period} category={category}")
        data = get_brand_owners_data(period, category=category)
        return {"success": True, "data": data, "requested_period": period}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/categories")
async def categories():
    """
    List of real product categories (Product Category 1), excluding the
    unclassified placeholders. Used to populate category pickers on
    Brand Level / Channels / Regions.
    """
    try:
        data = get_real_categories()
        return {"success": True, "data": data, "count": len(data)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/brand-level")
async def brand_level(period: str = None, category: str = None):
    """
    Brand-level drilldown for any real category: universe, adaptive
    sub-category leaders + top10 (or a single 'Overall' leader if the
    category has no meaningful Category 3 split), top brand trend.
    Used for: Brand Level page.
    """
    try:
        print(f"[API] /api/brand-level requested with period={period} category={category}")
        data = get_brand_level_data(category, period)
        return {"success": True, "data": data, "requested_period": period}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/channels-analysis")
async def channels_analysis(period: str = None, category: str = None):
    """
    Channel contribution for any real category (adaptive sub-category
    segments, or a single 'Overall' segment) + per-channel drilldown.
    Used for: Channels page.
    """
    try:
        print(f"[API] /api/channels-analysis requested with period={period} category={category}")
        data = get_channels_analysis(period, category)
        return {"success": True, "data": data, "requested_period": period}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/regions-analysis")
async def regions_analysis(period: str = None, category: str = None):
    """
    Region contribution for any real category (adaptive sub-category
    segments, or a single 'Overall' segment) + per-region drilldown.
    Used for: Regions page.
    """
    try:
        print(f"[API] /api/regions-analysis requested with period={period} category={category}")
        data = get_regions_analysis(period, category)
        return {"success": True, "data": data, "requested_period": period}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    return {
        "error": "Internal Server Error",
        "detail": str(exc)
    }


# ============================================================================
# RUN SERVER
# ============================================================================

if __name__ == "__main__":
    import os
    import uvicorn

    # Port is overridable via the PORT env var so this can run alongside other
    # local projects that already use 8000, without editing this file each
    # time -- defaults to 8001 to match script.js's APP.API_BASE.
    PORT = int(os.environ.get("PORT", 8001))

    print("\n" + "="*80)
    print("Starting Egypt Skin Care Retail Audit Dashboard Backend")
    print("="*80)
    print(f"\nServer will run on: http://localhost:{PORT}")
    print(f"API Documentation: http://localhost:{PORT}/docs")
    print("\nPress Ctrl+C to stop the server\n")

    # NOTE: reload=True is intentionally OFF. It spawns a watcher subprocess
    # that re-imports this file, and on some Windows/conda setups that
    # subprocess fails silently -- the process just exits back to the prompt
    # right after the startup warning, with no server ever actually starting.
    # If you're actively editing this file and want auto-restart, run instead:
    #   uvicorn main:app --reload --host 0.0.0.0 --port 8001
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=PORT,
        log_level="info"
    )
