# Lumina Market Intelligence Dashboard (Portfolio Demo)

This is a **synthetic demo version** of a market intelligence dashboard originally
built for a real retail-audit client. All brand, brand-owner, and item names, and
all sales figures, have been randomized/replaced — none of this data is real.
The structure (markets, periods, category taxonomy, feature set) matches the
original project; only the confidential business data has been swapped out.

## Run it

1. `cd backend && pip install -r requirements.txt`
2. `python main.py` (serves on http://localhost:8001 by default; override with `PORT=xxxx`)
3. Open `overview.html` (or any of the 6 pages) in your browser.

## What it demonstrates

- Adaptive category segmentation (auto-detects meaningful sub-category splits
  per product category, no hardcoding)
- Global category + period filtering across 6 linked views (Brand Owners,
  Overview, Brand Level, SKUs, Channels, Regions)
- Single-period display collapse with dynamic growth comparisons
- FastAPI backend processing 80,000+ rows with pandas
