# Lumina Market Intelligence Dashboard (Portfolio Demo)

This is a **synthetic demo version** of a market intelligence dashboard originally
built for a real retail-audit client. All brand, brand-owner, and item names, and
all sales figures, have been randomized/replaced — none of this data is real.
The structure (markets, periods, category taxonomy, feature set) matches the
original project; only the confidential business data has been swapped out.

## Live deploy (Vercel / GitHub Pages / any static host)

This copy runs in **static mode**: `script.js` reads pre-baked JSON snapshots from
the `data/` folder (one per category × period combination, 413 files, ~5MB total)
instead of calling a live Python backend. That means the whole thing is a plain
static site — deploy the repo root to Vercel (or GitHub Pages, Netlify, etc.) with
zero configuration and no server to run or pay for. Open `overview.html` as the
entry point (or set it as the redirect target / homepage in your host's settings).

## Run locally (with the real backend, for development)

1. `cd backend && pip install -r requirements.txt`
2. `python main.py` (serves on http://localhost:8001 by default; override with `PORT=xxxx`)
3. In `script.js`, set `const STATIC_MODE = false;` to call the live backend instead
   of the static `data/` files, and open any of the 6 HTML pages.

To regenerate the static snapshots after a data or backend change, run the live
backend locally and re-request every category/period/segment combination the
frontend calls, saving each response's raw JSON body into `data/<endpoint>/...json`
following the naming scheme `staticPathFor()` builds in `script.js`.

## What it demonstrates

- Adaptive category segmentation (auto-detects meaningful sub-category splits
  per product category, no hardcoding)
- Global category + period filtering across 6 linked views (Brand Owners,
  Overview, Brand Level, SKUs, Channels, Regions)
- Single-period display collapse with dynamic growth comparisons
- FastAPI backend processing 80,000+ rows with pandas (used to generate this
  demo's static data; not required to run the deployed site)
