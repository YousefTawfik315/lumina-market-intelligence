/* ============================================================================
   Lumina Market Intelligence Dashboard
   Shared JS — one file for every page. Each page sets <body data-page="...">
   and this file dispatches to the matching render*Page() function.

   BUILD RULES ENFORCED HERE (do not silently violate these):
   - Total-market figures always come from the backend, which already scopes
     to Markets == 'TOTAL EGYPT+PERFUMERY'. Never sum across markets client-side.
   - Growth % renders as "N/A" (not 0%) when the backend returns null.
   - LUMINA COSMETICS (and its brand family) are highlighted, never hidden.
   - Brand Level / Channels / Regions pages are adaptive across ALL real
     categories (via /api/categories + a category selector). Each category's
     backend response says has_segments + segments[]/segment_names[] -- when
     Product Category 3 gives a meaningful split (e.g. GPC / Medical for All
     Purpose Cream) those segments are shown; otherwise a single 'Overall'
     segment is shown. The frontend never hardcodes GPC/Medical -- it always
     loops over whatever segments the backend returns.
   ============================================================================ */

const ALL_PURPOSE_CREAM_LABEL = 'All Purpose Cream';

// Special pseudo-period meaning "all 3 MAT years combined" -- mirrors the
// backend's ALL_PERIOD sentinel. Selectable from the nav's period pills
// alongside the 3 real periods; KPI cards then show the 3-year combined sum.
const ALL_PERIOD = 'ALL';

const APP = {
  API_BASE: 'http://localhost:8001',
  PERIODS: ['Apr-24', 'Apr-25', 'Apr-26'],
  PERIODS_SELECTABLE: ['Apr-24', 'Apr-25', 'Apr-26', 'ALL'],
  state: {
    period: 'Apr-26',
    compare: false,
    category: null,
  },
  colors: {
    green: ['#1B2559', '#2A3B7A', '#3B4F9E', '#5568B8', '#8091D1', '#ABB7E3', '#D2D8F1', '#EBEEFA'],
    positive: '#1E8E5A',
    negative: '#D14545',
    neutral: '#8A93A6',
    dark: '#12172B',
    beige: '#E7ECFA',
  },
};

/* ---------------------------------------------------------------------- */
/* Formatting helpers                                                      */
/* ---------------------------------------------------------------------- */

function fmtEGP(value) {
  if (value === null || value === undefined || isNaN(value)) return 'N/A';
  const abs = Math.abs(value);
  let out;
  if (abs >= 1e9) out = (value / 1e9).toFixed(2) + 'B';
  else if (abs >= 1e6) out = (value / 1e6).toFixed(2) + 'M';
  else if (abs >= 1e3) out = (value / 1e3).toFixed(1) + 'K';
  else out = value.toFixed(0);
  return 'EGP ' + out;
}

function fmtNum(value) {
  if (value === null || value === undefined || isNaN(value)) return 'N/A';
  return Number(value).toLocaleString('en-US', { maximumFractionDigits: 0 });
}

function fmtPct(value, decimals) {
  if (value === null || value === undefined || isNaN(value)) return 'N/A';
  const d = decimals === undefined ? 1 : decimals;
  return value.toFixed(d) + '%';
}

function growthBadgeHTML(value) {
  if (value === null || value === undefined || isNaN(value)) {
    return `<span class="badge badge-neutral">N/A</span>`;
  }
  const cls = value >= 0 ? 'badge-positive' : 'badge-negative';
  const arrow = value >= 0 ? '▲' : '▼';
  return `<span class="badge ${cls}">${arrow} ${Math.abs(value).toFixed(1)}%</span>`;
}

function anchorVal(record, anchorPeriod, key) {
  // Records from list endpoints (brand owners, brand-level top10/top30, etc.)
  // only ever carry explicit 'Apr-24'/'Apr-25'/'Apr-26' fields -- never a
  // literal 'ALL' key. When the "3-Year Total" period is selected, the value
  // for that record is the sum of the 3 real periods instead of a lookup.
  const k = key || anchorPeriod;
  if (k === ALL_PERIOD) {
    return (record['Apr-24'] || 0) + (record['Apr-25'] || 0) + (record['Apr-26'] || 0);
  }
  return record[k];
}

/* ---------------------------------------------------------------------- */
/* Single-period display helpers                                          */
/* Client requirement: picking one year (Apr-24/25/26) shows ONLY that     */
/* year's numbers everywhere -- no other year's raw values on the page.    */
/* Picking "3-Year Total" (ALL_PERIOD) shows all 3 years together, as      */
/* today. The backend's `anchor_period` on every response is the single    */
/* source of truth for which mode is active -- these helpers just render   */
/* according to it, they never re-derive the period filter themselves.     */
/* ---------------------------------------------------------------------- */

function displayPeriodsFor(anchorPeriod) {
  return anchorPeriod === ALL_PERIOD ? APP.PERIODS : [anchorPeriod];
}

function growthMetaFor(anchorPeriod) {
  // Which single growth field is a valid "vs previous year" comparison when
  // exactly one year is selected. Apr-24 has no prior year in the dataset,
  // so there is nothing valid to show there.
  if (anchorPeriod === 'Apr-25') return { key: 'growth_24_25_pct', label: 'vs Apr-24' };
  if (anchorPeriod === 'Apr-26') return { key: 'growth_25_26_pct', label: 'vs Apr-25' };
  return null;
}

function periodHeadersHTML(displayPeriods) {
  if (displayPeriods.length === 1) {
    const growth = growthMetaFor(displayPeriods[0]);
    return `<th class="num">${displayPeriods[0]}</th>` + (growth ? `<th class="num">Growth</th>` : '');
  }
  return `<th class="num">Apr-24</th><th class="num">Apr-25</th><th class="num">Apr-26</th><th class="num">Δ 24→25</th><th class="num">Δ 25→26</th>`;
}

function periodCellsHTML(record, displayPeriods) {
  if (displayPeriods.length === 1) {
    const p = displayPeriods[0];
    const growth = growthMetaFor(p);
    let out = `<td class="num">${fmtEGP(record[p])}</td>`;
    if (growth) out += `<td class="num">${growthBadgeHTML(record[growth.key])}</td>`;
    return out;
  }
  return `<td class="num">${fmtEGP(record['Apr-24'])}</td><td class="num">${fmtEGP(record['Apr-25'])}</td><td class="num">${fmtEGP(record['Apr-26'])}</td><td class="num">${growthBadgeHTML(record.growth_24_25_pct)}</td><td class="num">${growthBadgeHTML(record.growth_25_26_pct)}</td>`;
}

function kpiGrowthHTML(record, anchorPeriod) {
  // For KPI cards showing ONE headline growth figure (not a full table).
  // Returns '' when there's nothing valid to compare (Apr-24 selected).
  if (anchorPeriod === ALL_PERIOD) {
    return `${growthBadgeHTML(record.growth_25_26_pct)} vs Apr-25`;
  }
  const meta = growthMetaFor(anchorPeriod);
  if (!meta) return '';
  return `${growthBadgeHTML(record[meta.key])} ${meta.label}`;
}

function escapeHTML(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

/* ---------------------------------------------------------------------- */
/* Fetch helper                                                            */
/* ---------------------------------------------------------------------- */

// Portfolio demo: no live backend. Every /api/... call the app makes is
// mapped to a pre-baked static JSON file instead (generated once from the
// real backend, see data/ folder), so this entire site is static-hostable
// (Vercel, GitHub Pages, etc.) with zero server to run or pay for.
const STATIC_MODE = true;

function staticPathFor(path) {
  const [endpoint, qs] = path.split('?');
  const endpointSlug = endpoint.replace(/^\/api\//, '').replace(/\//g, '-');
  const params = new URLSearchParams(qs || '');
  const parts = [];
  if (params.has('period')) parts.push(params.get('period'));
  if (params.has('category')) parts.push(slugify(params.get('category')));
  if (params.has('segment')) parts.push(slugify(params.get('segment')));
  const fileName = parts.length ? parts.join('__') : 'index';
  return `data/${endpointSlug}/${fileName}.json`;
}

async function fetchJSON(path) {
  const url = STATIC_MODE ? staticPathFor(path) : `${APP.API_BASE}${path}`;
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Request failed (${res.status}) for ${path}`);
  }
  const body = await res.json();
  if (body && body.success === false) {
    throw new Error(body.detail || 'Unknown API error');
  }
  return body.data !== undefined ? body.data : body;
}

function setState(el, html) {
  if (el) el.innerHTML = html;
}

function showLoading(el, label) {
  setState(el, `<div class="loading-state">${label || 'Loading…'}</div>`);
}

function showError(el, err) {
  console.error(err);
  setState(el, `<div class="error-state">Couldn't load this section. Is the backend running on ${APP.API_BASE}? (${escapeHTML(err.message || err)})</div>`);
}

/* ---------------------------------------------------------------------- */
/* Navigation: period pills + compare toggle (shared across all pages)     */
/* ---------------------------------------------------------------------- */

function initNav(onPeriodChange) {
  const pageName = document.body.getAttribute('data-page');
  document.querySelectorAll('.nav-links a').forEach((a) => {
    if (a.getAttribute('data-nav') === pageName) a.classList.add('active');
  });

  const savedPeriod = sessionStorage.getItem('lmi_period');
  if (savedPeriod && APP.PERIODS_SELECTABLE.includes(savedPeriod)) APP.state.period = savedPeriod;

  const pillsWrap = document.querySelector('.period-pills');
  if (pillsWrap) {
    pillsWrap.querySelectorAll('.period-pill').forEach((btn) => {
      const p = btn.getAttribute('data-period');
      btn.classList.toggle('active', p === APP.state.period);
      btn.addEventListener('click', () => {
        APP.state.period = p;
        sessionStorage.setItem('lmi_period', p);
        pillsWrap.querySelectorAll('.period-pill').forEach((b) => b.classList.toggle('active', b === btn));
        if (typeof onPeriodChange === 'function') onPeriodChange(APP.state.period);
      });
    });
  }
}

function slugify(str) {
  return String(str).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
}

/* ---------------------------------------------------------------------- */
/* Category selector (Brand Level / Channels / Regions pages)              */
/* ---------------------------------------------------------------------- */

async function initCategorySelector(onCategoryChange) {
  const select = document.getElementById('category-select');
  if (!select) return null;

  let categories = [];
  try {
    categories = await fetchJSON('/api/categories');
  } catch (err) {
    console.error(err);
  }

  const names = categories.map((c) => c.name);
  // All Purpose Cream is Lumina's flagship line (and the only category with a
  // GPC/Medical split most pages were originally built around) -- bubble it
  // to the front so it's the default selection, not just whatever sorts
  // first by total sales.
  if (names.includes(ALL_PURPOSE_CREAM_LABEL)) {
    names.splice(names.indexOf(ALL_PURPOSE_CREAM_LABEL), 1);
    names.unshift(ALL_PURPOSE_CREAM_LABEL);
  }
  select.innerHTML = names.map((name) => `<option value="${escapeHTML(name)}">${escapeHTML(name)}</option>`).join('');

  const saved = sessionStorage.getItem('lmi_category');
  APP.state.category = (saved && names.includes(saved)) ? saved : (names[0] || null);
  if (APP.state.category) select.value = APP.state.category;

  select.addEventListener('change', () => {
    APP.state.category = select.value;
    sessionStorage.setItem('lmi_category', APP.state.category);
    if (typeof onCategoryChange === 'function') onCategoryChange(APP.state.category);
  });

  return APP.state.category;
}

/* ---------------------------------------------------------------------- */
/* Reusable render fragments                                               */
/* ---------------------------------------------------------------------- */

function kpiPeriodsHTML(values) {
  return `
    <div class="kpi-periods">
      ${APP.PERIODS.map((p) => `
        <div class="kpi-period-item">
          <span class="lbl">${p}</span>
          <span class="val">${fmtEGP(values[p])}</span>
        </div>
      `).join('')}
    </div>`;
}

function barListHTML(items, opts) {
  opts = opts || {};
  const valueKey = opts.valueKey || 'sales';
  const labelKey = opts.labelKey || 'brand';
  const shareKey = opts.shareKey || 'share_of_subcategory_pct';
  const isHeroFn = opts.isHeroFn || (() => false);
  const val = (it) => anchorVal(it, valueKey);
  const max = Math.max(...items.map(val), 1);

  return `<div class="bar-list">${items.map((it) => {
    const pct = Math.max((val(it) / max) * 100, 2);
    const isHero = isHeroFn(it);
    return `
      <div class="bar-row">
        <div class="bar-label ${isHero ? 'is-hero' : ''}">${escapeHTML(it[labelKey])}${isHero ? '<span class="hero-tag">LUMINA</span>' : ''}</div>
        <div class="bar-track">
          <div class="bar-fill ${isHero ? 'is-hero' : ''}" style="width:${pct}%">
            <span class="bar-fill-label">${fmtPct(it[shareKey])}</span>
          </div>
        </div>
        <div class="bar-pct">${fmtEGP(val(it))}</div>
      </div>`;
  }).join('')}</div>`;
}

function isHeroOwner(name) {
  return (name || '').trim().toUpperCase() === 'LUMINA COSMETICS';
}

function isHeroBrandGuess(brand) {
  // Used only for lightweight visual highlighting on brand-level pages where
  // the backend already scoped to All Purpose Cream; the brand "GPC" and its
  // sibling Lumina lines are the ones worth calling out visually.
  const heroBrands = ['LUMORA', 'VELARA', 'PURELINE', 'DERMORA'];
  return heroBrands.includes((brand || '').trim().toUpperCase());
}

/* ---------------------------------------------------------------------- */
/* Chart.js helpers (loaded via CDN in each page)                          */
/* ---------------------------------------------------------------------- */

function makeDonut(ctx, labels, values, colors) {
  return new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels,
      datasets: [{
        data: values,
        backgroundColor: colors,
        borderWidth: 2,
        borderColor: '#FFFFFF',
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '62%',
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (item) => `${item.label}: ${fmtEGP(item.raw)}`,
          },
        },
      },
    },
  });
}

function makeLine(ctx, labels, datasets) {
  return new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: datasets.map((d, i) => ({
        label: d.label,
        data: d.data,
        borderColor: APP.colors.green[i % APP.colors.green.length],
        backgroundColor: APP.colors.green[i % APP.colors.green.length],
        tension: 0.3,
        pointRadius: 4,
        borderWidth: 2,
      })),
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'bottom', labels: { boxWidth: 8, font: { size: 11 } } },
        tooltip: { callbacks: { label: (item) => `${item.dataset.label}: ${fmtEGP(item.raw)}` } },
      },
      scales: {
        y: { ticks: { callback: (v) => fmtEGP(v) } },
      },
    },
  });
}

function makeRankedBar(ctx, labels, values) {
  // Single-period ranking view: one bar per label (e.g. brand), ordered as
  // given. Used instead of a line chart when there's only one period selected
  // -- a line with a single point per series renders as disconnected dots,
  // which isn't a useful chart.
  return new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        data: values,
        backgroundColor: labels.map((_, i) => APP.colors.green[i % APP.colors.green.length]),
        borderRadius: 4,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: (item) => fmtEGP(item.raw) } },
      },
      scales: {
        y: { ticks: { callback: (v) => fmtEGP(v) } },
      },
    },
  });
}

function makeGroupedBar(ctx, labels, datasets) {
  return new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: datasets.map((d, i) => ({
        label: d.label,
        data: d.data,
        backgroundColor: APP.colors.green[(APP.colors.green.length - 1 - i) % APP.colors.green.length],
        borderRadius: 4,
      })),
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'bottom', labels: { boxWidth: 8, font: { size: 11 } } },
        tooltip: { callbacks: { label: (item) => `${item.dataset.label}: ${fmtEGP(item.raw)}` } },
      },
      scales: {
        y: { ticks: { callback: (v) => fmtEGP(v) } },
      },
    },
  });
}

/* ---------------------------------------------------------------------- */
/* PAGE: Overview                                                          */
/* ---------------------------------------------------------------------- */

let overviewChart = null;
const OV_KPI_COLORS = ['kpi-card--dark', '', 'kpi-card--green', 'kpi-card--beige'];

async function renderOverviewPage() {
  const root = document.getElementById('overview-root');
  if (!root) return;
  showLoading(root, 'Loading overview…');
  try {
    const catParam = APP.state.category ? `&category=${encodeURIComponent(APP.state.category)}` : '';
    const data = await fetchJSON(`/api/overview?period=${APP.state.period}${catParam}`);
    const subcats = data.subcategories;
    const splitLabel = data.has_segments ? subcats.map((s) => s.name).join(' vs ') : 'Overall';
    const displayPeriods = displayPeriodsFor(data.anchor_period);
    const periodLabel = displayPeriods.length === 3 ? '3 MAT years combined' : `MAT ${data.anchor_period} only`;

    const titleEl = document.getElementById('page-title');
    const subtitleEl = document.getElementById('page-subtitle');
    if (titleEl) titleEl.textContent = 'Overview';
    if (subtitleEl) {
      subtitleEl.textContent = `${data.category.name} · ${periodLabel} · TOTAL EGYPT+PERFUMERY`;
    }

    root.innerHTML = `
      <div class="grid grid-4" id="overview-kpis"></div>
      <div class="card">
        <p class="card-eyebrow"><span class="section-index">2.3</span>Sub-Category Split — ${escapeHTML(data.category.name)}</p>
        <h3 class="card-title">${escapeHTML(splitLabel)}</h3>
        <p class="card-note">Sales value (EGP) within ${escapeHTML(data.category.name)}, by Product Category 3, at ${data.anchor_period}.</p>
        <div class="chart-box"><canvas id="subcat-chart"></canvas></div>
      </div>
      <div class="card">
        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>Sub-Category</th>
                ${periodHeadersHTML(displayPeriods)}
                <th class="num">% of ${escapeHTML(data.category.name)} (${data.anchor_period})</th>
              </tr>
            </thead>
            <tbody id="subcat-table-body"></tbody>
          </table>
        </div>
        ${data.has_segments ? `
        <p class="card-note" style="margin-top:14px;margin-bottom:0;">
          <strong>"Unclassified"</strong> = ${escapeHTML(data.category.name)} rows whose Product Category 3 value is not
          ${escapeHTML(subcats.filter((s) => s.name !== 'Unclassified').map((s) => s.name).join(' or '))}
          (blank, "0", or another non-standard label in the raw data). These sales are real and are counted in the
          ${escapeHTML(data.category.name)} total above — they're broken out here instead of being hidden, since they
          can't be assigned to a named sub-category.
        </p>` : `
        <p class="card-note" style="margin-top:14px;margin-bottom:0;">No meaningful Product Category 3 sub-category split was detected for ${escapeHTML(data.category.name)}, so this shows the overall category total instead.</p>`}
      </div>
      <p class="footer-note">Total-market figures use Markets = TOTAL EGYPT+PERFUMERY only. ${data.has_segments ? 'Sub-category names are Product Category 3 values; rows outside the named segments are grouped as Unclassified, not hidden.' : ''}</p>
    `;

    const kpiWrap = document.getElementById('overview-kpis');
    const tmGrowth = kpiGrowthHTML(data.total_market, data.anchor_period);
    const totalMarketCard = `
      <div class="kpi-card kpi-card--beige">
        <span class="kpi-label">Total Market</span>
        <span class="kpi-value">${fmtEGP(data.total_market.values[data.anchor_period])}</span>
        ${tmGrowth ? `<div class="kpi-sub">${tmGrowth}</div>` : ''}
        ${displayPeriods.length === 3 ? kpiPeriodsHTML(data.total_market.values) : ''}
      </div>`;
    const catGrowth = kpiGrowthHTML(data.category, data.anchor_period);
    const categoryCard = `
      <div class="kpi-card kpi-card--green">
        <span class="kpi-label">${escapeHTML(data.category.name)}</span>
        <span class="kpi-value">${fmtEGP(data.category.values[data.anchor_period])}</span>
        <div class="kpi-sub">${catGrowth ? catGrowth + ' · ' : ''}${fmtPct(data.category.share_of_total_market_pct)} of Total Market</div>
        <div class="kpi-note">${fmtNum(data.category.fact_count)} row-facts across all periods</div>
      </div>`;
    const subcatCards = subcats.map((s, i) => {
      const subGrowth = kpiGrowthHTML(s, data.anchor_period);
      return `
      <div class="kpi-card ${OV_KPI_COLORS[i % OV_KPI_COLORS.length]}">
        <span class="kpi-label">${escapeHTML(s.name)}${data.has_segments ? ' (Category 3)' : ''}</span>
        <span class="kpi-value">${fmtEGP(s.values[data.anchor_period])}</span>
        <div class="kpi-sub">${subGrowth ? subGrowth + ' · ' : ''}${fmtPct(s.share_of_category_pct)} of ${escapeHTML(data.category.name)}</div>
      </div>`;
    }).join('');

    kpiWrap.innerHTML = totalMarketCard + categoryCard + subcatCards;
    kpiWrap.style.gridTemplateColumns = `repeat(auto-fit, minmax(220px, 1fr))`;

    const tbody = document.getElementById('subcat-table-body');
    tbody.innerHTML = subcats.map((s) => `
      <tr>
        <td>${escapeHTML(s.name)}</td>
        ${periodCellsHTML({ ...s.values, growth_24_25_pct: s.growth_24_25_pct, growth_25_26_pct: s.growth_25_26_pct }, displayPeriods)}
        <td class="num">${fmtPct(s.share_of_category_pct)}</td>
      </tr>
    `).join('');

    const ctx = document.getElementById('subcat-chart').getContext('2d');
    if (overviewChart) overviewChart.destroy();
    overviewChart = makeGroupedBar(
      ctx,
      displayPeriods,
      subcats.map((s) => ({ label: s.name, data: displayPeriods.map((p) => s.values[p]) }))
    );
  } catch (err) {
    showError(root, err);
  }
}

/* ---------------------------------------------------------------------- */
/* PAGE: Brand Owners                                                      */
/* ---------------------------------------------------------------------- */

async function renderBrandOwnersPage() {
  const root = document.getElementById('brand-owners-root');
  if (!root) return;
  showLoading(root, 'Loading brand owners…');
  try {
    const catParam = APP.state.category ? `&category=${encodeURIComponent(APP.state.category)}` : '';
    const data = await fetchJSON(`/api/brand-owners?period=${APP.state.period}${catParam}`);
    const top15 = data.brand_owners.slice(0, 15);
    const scopeLabel = data.category ? escapeHTML(data.category) : 'all categories';
    const displayPeriods = displayPeriodsFor(data.anchor_period);
    const boColspan = 2 + (displayPeriods.length === 3 ? 5 : (growthMetaFor(data.anchor_period) ? 2 : 1)) + 1;

    const titleEl = document.getElementById('page-title');
    const subtitleEl = document.getElementById('page-subtitle');
    if (titleEl) titleEl.textContent = 'Brand Owners';
    if (subtitleEl) {
      subtitleEl.textContent = `TOTAL EGYPT+PERFUMERY · ${data.category || 'all categories'} · ${displayPeriods.length === 3 ? '3 MAT years combined' : `MAT ${data.anchor_period} only`}`;
    }

    root.innerHTML = `
      <div class="card">
        <p class="card-eyebrow"><span class="section-index">1</span>Brand Owner Overview</p>
        <h3 class="card-title">Top brand owners — TOTAL EGYPT+PERFUMERY</h3>
        <p class="card-note">Scope: ${scopeLabel}. ${data.anchor_period} sales value (EGP) and contribution % to TOTAL EGYPT+PERFUMERY. Total at anchor: ${fmtEGP(data.total_market_at_anchor)}.</p>
        <div id="bo-bar-list"></div>
      </div>
      <div class="card">
        <div class="flex-between" style="margin-bottom:14px;flex-wrap:wrap;gap:12px;">
          <div>
            <p class="card-eyebrow mb-0"><span class="section-index">1</span>Multi-MAT Detail</p>
            <h3 class="card-title mb-0">Brand owners — multi-MAT</h3>
            <p class="card-note mb-0">All ${data.count} brand owners with non-zero sales in at least one MAT period (scope: ${scopeLabel}). Sales value (EGP), growth between consecutive MATs, and contribution to TOTAL EGYPT+PERFUMERY at ${data.anchor_period}.</p>
          </div>
          <input type="text" class="search-input" id="bo-search" placeholder="Search brand owner…" />
        </div>
        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>#</th><th>Brand Owner</th>
                ${periodHeadersHTML(displayPeriods)}
                <th class="num">% of TOTAL EGYPT+PERFUMERY (${data.anchor_period})</th>
              </tr>
            </thead>
            <tbody id="bo-table-body"></tbody>
          </table>
        </div>
      </div>
      <p class="footer-note">Only BRAND OWNER = "LUMINA COSMETICS" is treated as internal. All other owners are shown as independent competitors.</p>
    `;

    document.getElementById('bo-bar-list').innerHTML = renderOwnerBarList(top15, data.anchor_period);

    function renderOwnerTable(search) {
      const q = (search || '').toLowerCase();
      const rows = q
        ? data.brand_owners.filter((o) => (o.brand_owner || '').toLowerCase().includes(q))
        : data.brand_owners;
      const tbody = document.getElementById('bo-table-body');
      if (!rows.length) {
        tbody.innerHTML = `<tr><td colspan="${boColspan}" class="empty-state">No brand owners match "${escapeHTML(search)}".</td></tr>`;
        return;
      }
      tbody.innerHTML = rows.map((o) => `
        <tr class="${o.is_hero ? 'is-hero' : ''}">
          <td class="rank">${o.rank}</td>
          <td>${escapeHTML(o.brand_owner)}${o.is_hero ? '<span class="hero-tag">LUMINA</span>' : ''}</td>
          ${periodCellsHTML(o, displayPeriods)}
          <td class="num">${fmtPct(o.share_pct)}</td>
        </tr>
      `).join('');
    }

    renderOwnerTable('');
    document.getElementById('bo-search').addEventListener('input', (e) => renderOwnerTable(e.target.value));
  } catch (err) {
    showError(root, err);
  }
}

function renderOwnerBarList(items, anchor) {
  const val = (it) => anchorVal(it, anchor);
  const max = Math.max(...items.map(val), 1);
  return `<div class="bar-list">${items.map((it) => {
    const pct = Math.max((val(it) / max) * 100, 2);
    return `
      <div class="bar-row">
        <div class="bar-label ${it.is_hero ? 'is-hero' : ''}">${escapeHTML(it.brand_owner)}${it.is_hero ? '<span class="hero-tag">LUMINA</span>' : ''}</div>
        <div class="bar-track">
          <div class="bar-fill ${it.is_hero ? 'is-hero' : ''}" style="width:${pct}%">
            <span class="bar-fill-label">${fmtPct(it.share_pct)}</span>
          </div>
        </div>
        <div class="bar-pct">${fmtEGP(val(it))}</div>
      </div>`;
  }).join('')}</div>`;
}

/* ---------------------------------------------------------------------- */
/* PAGE: Brand Level (adaptive across all real categories)                 */
/* ---------------------------------------------------------------------- */

let trendChart = null;
let top15Chart = null;
const BL_KPI_COLORS = ['kpi-card--green', 'kpi-card--dark', '', 'kpi-card--beige'];

async function renderBrandLevelPage() {
  const root = document.getElementById('brand-level-root');
  if (!root) return;
  showLoading(root, 'Loading brand level…');
  try {
    const catParam = APP.state.category ? `&category=${encodeURIComponent(APP.state.category)}` : '';
    const data = await fetchJSON(`/api/brand-level?period=${APP.state.period}${catParam}`);
    const displayPeriods = displayPeriodsFor(data.anchor_period);

    const titleEl = document.getElementById('page-title');
    const subtitleEl = document.getElementById('page-subtitle');
    if (titleEl) titleEl.textContent = `Brand Level — ${data.category}`;
    if (subtitleEl) {
      subtitleEl.textContent = data.has_segments
        ? `${data.segments.map((s) => s.name).join(' / ')} sub-categories (Product Category 3) · sorted by latest MAT sales value`
        : `Brand ranking · sorted by latest MAT sales value`;
    }

    const leaderCardsHTML = data.segments.map((seg) => `
      <div class="card">
        <h3 class="card-title">${escapeHTML(seg.name)} leaders</h3>
        <p class="card-note">Top 10 by ${data.anchor_period} sales value; labels show each brand's share of ${escapeHTML(seg.name)}.</p>
        <div id="bl-leaders-${slugify(seg.name)}"></div>
      </div>
    `).join('');

    // Brand Performance: Top 30 brands PER SEGMENT, with both contribution
    // metrics (to the whole category, and to this segment specifically).
    const perfTableCardsHTML = data.segments.map((seg) => `
      <div class="card">
        <p class="card-eyebrow">Brand Performance</p>
        <h3 class="card-title">Top 30 ${escapeHTML(seg.name)} brands ${displayPeriods.length === 3 ? 'across 3 MAT periods' : `— MAT ${data.anchor_period}`}</h3>
        <p class="card-note">Ranked by MAT (${data.anchor_period}). "% of Category" is each brand's share of the whole ${escapeHTML(data.category)} category; "% of ${escapeHTML(seg.name)}" is its share within this segment only.</p>
        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>Brand</th>
                ${periodHeadersHTML(displayPeriods)}
                <th class="num">% of Category</th><th class="num">% of ${escapeHTML(seg.name)}</th>
              </tr>
            </thead>
            <tbody id="bl-perf-${slugify(seg.name)}"></tbody>
          </table>
        </div>
      </div>
    `).join('');

    root.innerHTML = `
      <div class="grid" id="bl-kpis" style="grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));"></div>

      <div class="grid" style="grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));">
        ${leaderCardsHTML}
      </div>

      <div class="card">
        <p class="card-eyebrow">${displayPeriods.length === 3 ? 'Top 6 brands · trend' : 'Top 6 brands · ranked'}</p>
        <h3 class="card-title">Top 6 ${escapeHTML(data.category)} brands ${displayPeriods.length === 3 ? 'across 3 MAT periods' : `— MAT ${data.anchor_period}`}</h3>
        <p class="card-note">${displayPeriods.length === 3
          ? 'Each line is a brand\'s sales value (EGP) across consecutive periods.'
          : `Each bar is a brand's sales value (EGP) at MAT ${data.anchor_period} only, ranked highest to lowest.`} The period selector controls which 6 brands qualify: <strong>ranked by MAT (${data.anchor_period})</strong>.</p>
        <div class="chart-box chart-box--lg"><canvas id="bl-trend-chart"></canvas></div>
      </div>

      ${perfTableCardsHTML}

      <div class="card">
        <div class="flex-between">
          <div>
            <p class="card-eyebrow">Top 30 brands</p>
            <h3 class="card-title">Top 30 ${escapeHTML(data.category)} brands ${displayPeriods.length === 3 ? 'across 3 MAT periods' : `— MAT ${data.anchor_period}`}</h3>
            <p class="card-note">${displayPeriods.length === 3 ? 'Grouped bars per period (top 15 shown on chart for readability; table below has all 30).' : 'Top 15 shown on chart for readability; table below has all 30.'} Ranked by MAT (${data.anchor_period}). Side panel shows top-30 contribution to ${escapeHTML(data.category)} at ${data.anchor_period}.</p>
          </div>
        </div>
        <div class="grid" style="grid-template-columns: 2.4fr 1fr;">
          <div class="chart-box chart-box--lg"><canvas id="bl-top15-chart"></canvas></div>
          <div class="callout">
            <span class="callout-label">Top 30 contribute</span>
            <span class="callout-value">${fmtPct(data.top30_contribution_pct)}</span>
            <span class="callout-note">from ${escapeHTML(data.category)}</span>
            <span class="callout-value" style="font-size:16px;margin-top:8px;">${fmtEGP(data.top30.reduce((s, r) => s + anchorVal(r, data.anchor_period), 0))}</span>
          </div>
        </div>
        <div class="table-wrap" style="margin-top:16px;">
          <table class="data-table">
            <thead>
              <tr><th>Brand</th>${periodHeadersHTML(displayPeriods)}<th class="num">% of Category</th></tr>
            </thead>
            <tbody id="bl-top15-table-body"></tbody>
          </table>
        </div>
      </div>
      <p class="footer-note">${data.has_segments
        ? `Scope: ${escapeHTML(data.category)}. ${data.segments.map((s) => s.name).join(' / ')} are Product Category 3 values, not Category 2.`
        : `Scope: ${escapeHTML(data.category)}. No meaningful Product Category 3 segmentation was detected for this category, so this view shows the overall brand ranking instead.`}</p>
    `;

    const universeCard = `
      <div class="kpi-card kpi-card--beige">
        <span class="kpi-label">${escapeHTML(data.category)} universe — MAT (${data.anchor_period})</span>
        <span class="kpi-value">${fmtEGP(data.universe.values[data.anchor_period])}</span>
        <div class="kpi-note">Brands tracked: ${fmtNum(data.universe.brands_tracked)}</div>
      </div>`;

    const segmentCards = data.segments.map((seg, i) => `
      <div class="kpi-card ${BL_KPI_COLORS[i % BL_KPI_COLORS.length]}">
        <span class="kpi-label">${escapeHTML(seg.name)}${data.has_segments ? ' sub-category' : ''} — MAT (${data.anchor_period})</span>
        <span class="kpi-value">${fmtEGP(seg.values[data.anchor_period])}</span>
        <div class="kpi-sub">${fmtPct(seg.share_of_category_pct)} of ${escapeHTML(data.category)}</div>
        <div class="kpi-note">Leader: ${seg.leader ? escapeHTML(seg.leader.brand) : 'N/A'}${seg.leader ? ` (${fmtPct(seg.leader.share_of_subcategory_pct)})` : ''}</div>
      </div>`).join('');

    document.getElementById('bl-kpis').innerHTML = universeCard + segmentCards;

    data.segments.forEach((seg) => {
      const leaderEl = document.getElementById(`bl-leaders-${slugify(seg.name)}`);
      if (leaderEl) {
        leaderEl.innerHTML = barListHTML(seg.top10, {
          valueKey: data.anchor_period,
          isHeroFn: (it) => isHeroBrandGuess(it.brand),
        });
      }

      const perfEl = document.getElementById(`bl-perf-${slugify(seg.name)}`);
      if (perfEl) {
        perfEl.innerHTML = seg.top30.map((r) => `
          <tr class="${isHeroBrandGuess(r.brand) ? 'is-hero' : ''}">
            <td>${escapeHTML(r.brand)}${isHeroBrandGuess(r.brand) ? '<span class="hero-tag">LUMINA</span>' : ''}</td>
            ${periodCellsHTML(r, displayPeriods)}
            <td class="num">${fmtPct(r.share_of_category_pct)}</td>
            <td class="num">${fmtPct(r.share_of_subcategory_pct)}</td>
          </tr>
        `).join('');
      }
    });

    document.getElementById('bl-top15-table-body').innerHTML = data.top30.map((r) => `
      <tr class="${isHeroBrandGuess(r.brand) ? 'is-hero' : ''}">
        <td>${escapeHTML(r.brand)}${isHeroBrandGuess(r.brand) ? '<span class="hero-tag">LUMINA</span>' : ''}</td>
        ${periodCellsHTML(r, displayPeriods)}
        <td class="num">${fmtPct(r.share_of_category_pct)}</td>
      </tr>
    `).join('');

    const trendCtx = document.getElementById('bl-trend-chart').getContext('2d');
    if (trendChart) trendChart.destroy();
    if (displayPeriods.length === 1) {
      const p = displayPeriods[0];
      trendChart = makeRankedBar(trendCtx, data.top6_trend.map((r) => r.brand), data.top6_trend.map((r) => r[p]));
    } else {
      trendChart = makeLine(trendCtx, displayPeriods, data.top6_trend.map((r) => ({
        label: r.brand,
        data: displayPeriods.map((p) => r[p]),
      })));
    }

    const top15Chart_data = data.top30.slice(0, 15); // chart shows top 15 for readability; table has all 30
    const top15Ctx = document.getElementById('bl-top15-chart').getContext('2d');
    if (top15Chart) top15Chart.destroy();
    top15Chart = makeGroupedBar(top15Ctx, top15Chart_data.map((r) => r.brand), displayPeriods.map((p) => ({
      label: p,
      data: top15Chart_data.map((r) => r[p]),
    })));
  } catch (err) {
    showError(root, err);
  }
}

/* ---------------------------------------------------------------------- */
/* PAGE: Channels / Regions (shared renderer, adaptive across categories)  */
/* ---------------------------------------------------------------------- */

let dimensionCharts = [];

async function renderMarketDimensionPage(dimension) {
  // dimension: 'channels' | 'regions'
  const rootId = dimension === 'channels' ? 'channels-root' : 'regions-root';
  const root = document.getElementById(rootId);
  if (!root) return;
  showLoading(root, `Loading ${dimension}…`);

  const endpoint = dimension === 'channels' ? '/api/channels-analysis' : '/api/regions-analysis';
  const dimKey = dimension === 'channels' ? 'channel' : 'region';

  try {
    const catParam = APP.state.category ? `&category=${encodeURIComponent(APP.state.category)}` : '';
    const data = await fetchJSON(`${endpoint}?period=${APP.state.period}${catParam}`);
    const contributionByDim = data[`contribution_by_${dimKey}`] || {};
    const segmentNames = data.segment_names || [];
    const markets = Object.keys(data.drilldown);
    const displayPeriods = displayPeriodsFor(data.anchor_period);
    const drilldownColspan = 1 + (displayPeriods.length === 3 ? 5 : (growthMetaFor(data.anchor_period) ? 2 : 1));

    const titleEl = document.getElementById('page-title');
    const subtitleEl = document.getElementById('page-subtitle');
    if (titleEl) titleEl.textContent = dimension === 'channels' ? 'Channels' : 'Regions';
    if (subtitleEl) {
      subtitleEl.textContent = data.has_segments
        ? `${data.category} · ${segmentNames.join(' / ')} · top 10 brands per ${dimKey} × sub-category`
        : `${data.category} · top 10 brands per ${dimKey}`;
    }

    const contributionCardsHTML = segmentNames.map((name) => `
      <div class="card">
        <p class="card-eyebrow">Contribution</p>
        <h3 class="card-title">Where ${escapeHTML(name)} sells</h3>
        <p class="card-note">Each ${dimKey}'s share of ${escapeHTML(name)} sales value at ${data.anchor_period}.</p>
        <div class="chart-box"><canvas id="donut-${slugify(name)}"></canvas></div>
        <div class="chart-legend" id="legend-${slugify(name)}"></div>
      </div>
    `).join('');

    const drilldownColumnsHTML = segmentNames.map((name) => `
      <div>
        <h4 style="margin:0 0 10px;font-size:14px;">${escapeHTML(name)} — top 10 brands</h4>
        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr><th>Brand</th>${periodHeadersHTML(displayPeriods)}</tr>
            </thead>
            <tbody id="drilldown-${slugify(name)}"></tbody>
          </table>
        </div>
      </div>
    `).join('');

    root.innerHTML = `
      <div class="card">
        <p class="card-eyebrow">Contribution to Total Market</p>
        <h3 class="card-title">${dimension === 'channels' ? 'Channel' : 'Region'} contribution to Total Market — all categories</h3>
        <p class="card-note">Each ${dimKey}'s sales value (EGP) across all product categories, growth between consecutive MATs, and share of TOTAL EGYPT+PERFUMERY at ${data.anchor_period}. Not scoped to ${escapeHTML(data.category)} -- this is the whole market.</p>
        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>${dimension === 'channels' ? 'Channel' : 'Region'}</th>
                ${periodHeadersHTML(displayPeriods)}
                <th class="num">% of Total Market</th>
              </tr>
            </thead>
            <tbody id="total-market-contribution-body"></tbody>
          </table>
        </div>
      </div>

      <div class="grid" style="grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));">
        ${contributionCardsHTML}
      </div>

      <div class="card">
        <p class="card-eyebrow">Drilldown</p>
        <h3 class="card-title" id="drilldown-title"></h3>
        <p class="card-note" id="drilldown-note"></p>
        <div class="subtabs" id="drilldown-subtabs"></div>
        <div class="grid" style="grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));">
          ${drilldownColumnsHTML}
        </div>
      </div>
      <p class="footer-note">${data.has_segments
        ? `Scope: ${escapeHTML(data.category)}. ${segmentNames.join(' / ')} are Product Category 3 values.`
        : `Scope: ${escapeHTML(data.category)}. No meaningful Product Category 3 segmentation was detected for this category, so this view shows the overall brand ranking instead.`}</p>
    `;

    document.getElementById('total-market-contribution-body').innerHTML = (data.total_market_contribution || []).map((r) => `
      <tr>
        <td>${escapeHTML(r[dimKey])}</td>
        ${periodCellsHTML(r, displayPeriods)}
        <td class="num">${fmtPct(r.share_of_total_market_pct)}</td>
      </tr>
    `).join('');

    dimensionCharts.forEach((c) => c && c.destroy());
    dimensionCharts = segmentNames.map((name, i) => {
      const rows = contributionByDim[name] || [];
      const canvas = document.getElementById(`donut-${slugify(name)}`);
      const chart = makeDonut(canvas.getContext('2d'), rows.map((r) => r[dimKey]), rows.map((r) => r.sales), APP.colors.green);
      const legendEl = document.getElementById(`legend-${slugify(name)}`);
      if (legendEl) {
        legendEl.innerHTML = rows.map((r, j) => `
          <span class="legend-item"><span class="legend-dot" style="background:${APP.colors.green[j % APP.colors.green.length]}"></span>${escapeHTML(r[dimKey])} — ${fmtPct(r.share_pct)}</span>
        `).join('');
      }
      return chart;
    });

    const subtabsWrap = document.getElementById('drilldown-subtabs');
    subtabsWrap.innerHTML = markets.map((m, i) => `<button class="subtab ${i === 0 ? 'active' : ''}" data-market="${escapeHTML(m)}">${escapeHTML(m)}</button>`).join('');

    function renderDrilldown(marketName) {
      const entry = data.drilldown[marketName];
      document.getElementById('drilldown-title').textContent = marketName;
      document.getElementById('drilldown-note').textContent =
        `${data.category} sales in this ${dimKey} (${data.anchor_period}) — ${fmtEGP(entry.total_sales)}. Per-segment top 10 brands, MAT/MAT-1/MAT-2 + growth.`;
      segmentNames.forEach((name) => {
        const seg = entry.segments ? entry.segments[name] : null;
        const el = document.getElementById(`drilldown-${slugify(name)}`);
        if (!el) return;
        if (seg && seg.top10.length) {
          el.innerHTML = seg.top10.map((r) => `
            <tr class="${isHeroBrandGuess(r.brand) ? 'is-hero' : ''}">
              <td>${escapeHTML(r.brand)}${isHeroBrandGuess(r.brand) ? '<span class="hero-tag">LUMINA</span>' : ''}</td>
              ${periodCellsHTML(r, displayPeriods)}
            </tr>
          `).join('');
        } else {
          el.innerHTML = `<tr><td colspan="${drilldownColspan}" class="empty-state">No ${escapeHTML(name)} sales in this ${dimKey} at this period.</td></tr>`;
        }
      });
    }

    subtabsWrap.querySelectorAll('.subtab').forEach((btn) => {
      btn.addEventListener('click', () => {
        subtabsWrap.querySelectorAll('.subtab').forEach((b) => b.classList.toggle('active', b === btn));
        renderDrilldown(btn.getAttribute('data-market'));
      });
    });

    if (markets.length) renderDrilldown(markets[0]);
  } catch (err) {
    showError(root, err);
  }
}

/* ---------------------------------------------------------------------- */
/* PAGE: SKUs                                                              */
/* ---------------------------------------------------------------------- */

let skuDataCache = [];
let skuMode = 'top';

function skuLeaderboardTableHTML(segmentData, segmentLabel) {
  const rows = (segmentData && segmentData.skus) || [];
  if (!rows.length) {
    return `<div class="empty-state">No ${escapeHTML(segmentLabel)} SKUs found.</div>`;
  }
  const displayPeriods = displayPeriodsFor(segmentData.anchor_period);
  return `
    <div class="table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            <th>Brand</th><th>SKU</th>
            ${periodHeadersHTML(displayPeriods)}
          </tr>
        </thead>
        <tbody>
          ${rows.map((r) => `
            <tr class="${isHeroBrandGuess(r.brand) ? 'is-hero' : ''}">
              <td>${escapeHTML(r.brand)}${isHeroBrandGuess(r.brand) ? '<span class="hero-tag">LUMINA</span>' : ''}</td>
              <td>${escapeHTML(r.sku)}</td>
              ${periodCellsHTML(r, displayPeriods)}
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>`;
}

async function renderSkusPage() {
  const root = document.getElementById('skus-root');
  if (!root) return;
  showLoading(root, 'Loading SKUs…');
  try {
    const catParam = APP.state.category ? `&category=${encodeURIComponent(APP.state.category)}` : '';

    // First call (no segment) just to discover this category's adaptive
    // segments -- same has_segments/segment_names pattern as Brand Level.
    const [data, meta] = await Promise.all([
      fetchJSON(`/api/skus?period=${APP.state.period}${catParam}`),
      fetchJSON(`/api/sku-leaderboard?period=${APP.state.period}${catParam}`),
    ]);
    skuDataCache = data;

    const segmentNames = meta.has_segments ? meta.segment_names : null;
    const segmentDatas = segmentNames
      ? await Promise.all(segmentNames.map((name) =>
          fetchJSON(`/api/sku-leaderboard?period=${APP.state.period}${catParam}&segment=${encodeURIComponent(name)}`)))
      : [meta];
    const cardLabels = segmentNames || ['Overall'];

    const titleEl = document.getElementById('page-title');
    const subtitleEl = document.getElementById('page-subtitle');
    if (titleEl) titleEl.textContent = 'SKU Deep Dive';
    if (subtitleEl) {
      subtitleEl.textContent = `${meta.category} · TOTAL EGYPT+PERFUMERY · market reach counted across the 16 regional/channel markets`;
    }

    const leaderboardCardsHTML = cardLabels.map((name, i) => {
      const periodsCount = displayPeriodsFor(segmentDatas[i].anchor_period).length;
      return `
      <div class="card">
        <p class="card-eyebrow">Top 30 SKUs · ${escapeHTML(meta.category)}</p>
        <h3 class="card-title">${escapeHTML(name)} — Top 30 SKUs ${periodsCount === 3 ? 'across 3 MAT periods' : `(MAT ${segmentDatas[i].anchor_period})`}</h3>
        <p class="card-note">Ranked by MAT (${segmentDatas[i].anchor_period}) sales value. Brand and SKU are separate columns.</p>
        <div id="sku-leaderboard-${slugify(name)}"></div>
      </div>
    `;
    }).join('');

    root.innerHTML = `
      ${leaderboardCardsHTML}

      <div class="card">
        <div class="flex-between" style="margin-bottom:14px;flex-wrap:wrap;gap:12px;">
          <div>
            <p class="card-eyebrow">SKU Deep Dive</p>
            <h3 class="card-title mb-0">Top 100 SKUs by sales value — ${escapeHTML(meta.category)}</h3>
          </div>
          <div class="flex flex-gap" style="flex-wrap:wrap;">
            <input type="text" class="search-input" id="sku-search" placeholder="Search item, brand, category…" />
            <div class="toggle-group">
              <button class="toggle-btn active" data-mode="top">Highest 20</button>
              <button class="toggle-btn" data-mode="bottom">Lowest 20 of Top 100</button>
              <button class="toggle-btn" data-mode="all">All 100</button>
            </div>
          </div>
        </div>
        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr><th class="rank">#</th><th>Item</th><th>Brand</th><th>Category</th><th class="num">Total Sales (EGP)</th><th class="num">Market Reach</th></tr>
            </thead>
            <tbody id="sku-table-body"></tbody>
          </table>
        </div>
      </div>
      <p class="footer-note">"Lowest 20 of Top 100" ranks within the top-100 SKUs returned by the API — it is not the lowest-selling SKUs in the full catalog. Both tables above are scoped to the category selected in the nav bar.</p>
    `;

    cardLabels.forEach((name, i) => {
      const el = document.getElementById(`sku-leaderboard-${slugify(name)}`);
      if (el) el.innerHTML = skuLeaderboardTableHTML(segmentDatas[i], name);
    });

    document.getElementById('sku-search').addEventListener('input', (e) => renderSkuTable(e.target.value));
    root.querySelectorAll('.toggle-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        root.querySelectorAll('.toggle-btn').forEach((b) => b.classList.toggle('active', b === btn));
        skuMode = btn.getAttribute('data-mode');
        renderSkuTable(document.getElementById('sku-search').value);
      });
    });

    renderSkuTable('');
  } catch (err) {
    showError(root, err);
  }
}

function renderSkuTable(search) {
  const tbody = document.getElementById('sku-table-body');
  if (!tbody) return;
  let rows = skuDataCache;
  if (search) {
    const q = search.toLowerCase();
    rows = rows.filter((r) =>
      (r['Item Name'] || '').toLowerCase().includes(q) ||
      (r['Brand'] || '').toLowerCase().includes(q) ||
      (r['Category'] || '').toLowerCase().includes(q)
    );
  }
  let sliced = rows;
  if (skuMode === 'top') sliced = rows.slice(0, 20);
  else if (skuMode === 'bottom') sliced = rows.slice(-20).reverse();

  if (!sliced.length) {
    tbody.innerHTML = `<tr><td colspan="6" class="empty-state">No SKUs match "${escapeHTML(search)}".</td></tr>`;
    return;
  }

  tbody.innerHTML = sliced.map((r, i) => `
    <tr>
      <td class="rank">${skuDataCache.indexOf(r) + 1}</td>
      <td>${escapeHTML(r['Item Name'])}</td>
      <td>${escapeHTML(r['Brand'])}</td>
      <td>${escapeHTML(r['Category'])}</td>
      <td class="num">${fmtEGP(r['Total Sales'])}</td>
      <td class="num">${fmtNum(r['Market Count'])} markets</td>
    </tr>
  `).join('');
}

/* ---------------------------------------------------------------------- */
/* Dispatch on load                                                        */
/* ---------------------------------------------------------------------- */

document.addEventListener('DOMContentLoaded', async () => {
  const page = document.body.getAttribute('data-page');

  const renderers = {
    overview: renderOverviewPage,
    'brand-owners': renderBrandOwnersPage,
    'brand-level': renderBrandLevelPage,
    channels: () => renderMarketDimensionPage('channels'),
    regions: () => renderMarketDimensionPage('regions'),
    skus: renderSkusPage,
  };

  const renderCurrent = renderers[page];
  if (!renderCurrent) return;

  // The category filter now lives in the shared top nav (not per-page), so
  // it's initialized once here for every page, before the first render --
  // this makes it apply globally across all 6 tabs, per the client's request.
  initNav(() => renderCurrent());
  await initCategorySelector(() => renderCurrent());
  renderCurrent();
});
