/* ═══════════════════════════════════════════════════════════════
   SALES BI PLATFORM — LIVE DASHBOARD
   Real-time polling · Chart.js live updates · Toast notifications
   Order ticker · Live clock · Connection monitoring
═══════════════════════════════════════════════════════════════ */

'use strict';

/* ══════════════════════════════
   CONFIG
══════════════════════════════ */
const API_BASE      = 'http://localhost:8765';
const POLL_INTERVAL = 5000;    // ms between data refreshes
const CLOCK_TICK    = 1000;    // ms between clock ticks

/* ══════════════════════════════
   PAGE TITLES
══════════════════════════════ */
const PAGE_TITLES = {
  overview:     'Sales overview',
  sales:        'Sales trends',
  products:     'Product performance',
  transactions: 'Recent orders',
  alerts:       'Needs attention',
};

const ALERT_TITLES = {
  low_margin: 'Margins are below target',
  low_daily_revenue: 'Daily sales are below target',
};

/* ══════════════════════════════
   CHART.JS DEFAULTS
══════════════════════════════ */
Chart.defaults.color                          = '#8892b0';
Chart.defaults.font.family                    = "'Inter', sans-serif";
Chart.defaults.font.size                      = 12;
Chart.defaults.plugins.legend.display         = false;
Chart.defaults.plugins.tooltip.backgroundColor = '#1a2035';
Chart.defaults.plugins.tooltip.borderColor    = 'rgba(255,255,255,0.1)';
Chart.defaults.plugins.tooltip.borderWidth    = 1;
Chart.defaults.plugins.tooltip.padding        = 10;
Chart.defaults.plugins.tooltip.titleColor     = '#f0f2ff';
Chart.defaults.plugins.tooltip.bodyColor      = '#8892b0';
Chart.defaults.plugins.tooltip.cornerRadius   = 8;
Chart.defaults.animation.duration             = 600;

const gridColor = 'rgba(255,255,255,0.05)';

/* ══════════════════════════════
   STATE
══════════════════════════════ */
let charts        = {};         // id → Chart instance
let activeSection = 'overview';
let chartsBuilt   = {};
let lastData      = null;       // previous snapshot for change detection
let isConnected   = false;
let lastSeenOrders = new Set(); // track order IDs for new-order toasts
let pollTimer     = null;
let seenOrders    = new Set();

/* ══════════════════════════════
   UTILS
══════════════════════════════ */
const fmtINR = n => '₹' + Math.round(Number(n) || 0).toLocaleString('en-IN');
const fmtPct = n => parseFloat(n).toFixed(2) + '%';
const fmtCount = n => Math.round(Number(n) || 0).toLocaleString('en-IN');

function makeGradient(ctx, color1, color2, height = 260) {
  const g = ctx.createLinearGradient(0, 0, 0, height);
  g.addColorStop(0, color1);
  g.addColorStop(1, color2);
  return g;
}

function formatIndianDate(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? ''
    : date.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}

/* ══════════════════════════════
   CONNECTION STATUS
══════════════════════════════ */
function setConnected(ok) {
  isConnected = ok;
  const dot  = document.getElementById('conn-dot');
  const text = document.getElementById('conn-text');
  if (!dot || !text) return;
  if (ok) {
    dot.className  = 'conn-dot connected';
    text.textContent = 'Live';
  } else {
    dot.className  = 'conn-dot disconnected';
    text.textContent = 'Offline';
  }
}

/* ══════════════════════════════
   LIVE CLOCK
══════════════════════════════ */
function startClock() {
  const el = document.getElementById('live-clock');
  if (!el) return;
  function tick() {
    const now = new Date();
    el.textContent = now.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }
  tick();
  setInterval(tick, CLOCK_TICK);
}

/* ══════════════════════════════
   TOAST NOTIFICATIONS
══════════════════════════════ */
let toastQueue = [];
let toastActive = false;

function showToast(message, type = 'info', icon = '●') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `<span class="toast-icon">${icon}</span><span class="toast-msg">${message}</span>`;
  container.appendChild(toast);

  requestAnimationFrame(() => {
    requestAnimationFrame(() => toast.classList.add('visible'));
  });

  setTimeout(() => {
    toast.classList.remove('visible');
    setTimeout(() => toast.remove(), 400);
  }, 3500);
}

/* ══════════════════════════════
   ORDER TICKER
══════════════════════════════ */
function pushTicker(event) {
  const ticker = document.getElementById('ticker-inner');
  if (!ticker) return;

  const item = document.createElement('span');
  item.className = 'ticker-item';
  item.innerHTML =
    `<span class="ticker-order">${event.order_id}</span>` +
    `<span class="ticker-sep">·</span>` +
    `<span class="ticker-product">${event.product}</span>` +
    `<span class="ticker-sep">·</span>` +
    `<span class="ticker-region">${event.state || event.region}</span>` +
    `<span class="ticker-sep">·</span>` +
    `<span class="ticker-rev">${fmtINR(event.total_with_gst ?? event.revenue)} incl. GST</span>` +
    `<span class="ticker-time">${event.time}</span>`;

  // Prepend so newest is on the left
  ticker.insertBefore(item, ticker.firstChild);

  // Keep at most 15 items in the ticker
  while (ticker.children.length > 15) {
    ticker.removeChild(ticker.lastChild);
  }
}

/* ══════════════════════════════
   REFRESH SPINNER
══════════════════════════════ */
function setRefreshing(active) {
  const btn = document.getElementById('refresh-btn');
  const ind = document.getElementById('refresh-indicator');
  if (btn) btn.classList.toggle('spinning', active);
  if (ind) ind.classList.toggle('active', active);
}

/* ══════════════════════════════
   KPI COUNTER ANIMATION
══════════════════════════════ */
function animateCounter(el, target, formatter = n => Math.round(n).toLocaleString('en-IN'), duration = 900) {
  if (!el) return;
  const start    = performance.now();
  const from     = parseFloat(el.dataset.current || '0');
  const isFloat  = !Number.isInteger(target);

  el.dataset.current = String(target);

  function step(now) {
    const pct    = Math.min((now - start) / duration, 1);
    const eased  = 1 - Math.pow(1 - pct, 3);
    const val    = from + (target - from) * eased;

    el.textContent = formatter(val);

    if (pct < 1) requestAnimationFrame(step);
    else el.textContent = formatter(target);
  }
  requestAnimationFrame(step);
}

/* ══════════════════════════════
   DATA FETCH & APPLY
══════════════════════════════ */
async function fetchData() {
  try {
    setRefreshing(true);
    const res = await fetch(`${API_BASE}/api/data`, { cache: 'no-store' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    setConnected(true);
    applyData(data);
    lastData = data;
    updateLastRefreshed();
    return true;
  } catch (err) {
    setConnected(false);
    console.warn('[poll] Failed:', err.message);
    return false;
  } finally {
    setRefreshing(false);
  }
}

function updateLastRefreshed() {
  const el = document.getElementById('last-refreshed');
  if (!el) return;
  el.textContent = new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

/* ── Apply data snapshot to the entire UI ── */
function applyData(data) {
  const kpi = data.kpi || {};

  // ── KPI Cards ──
  animateCounter(document.getElementById('kpi-revenue'), Number(kpi.revenue || 0), fmtINR);
  animateCounter(document.getElementById('kpi-profit'),  Number(kpi.gross_profit || 0), fmtINR);
  animateCounter(document.getElementById('kpi-orders'),  Number(kpi.orders || 0), fmtCount);
  animateCounter(document.getElementById('kpi-units'),   Number(kpi.units  || 0), fmtCount);

  // Sub-labels
  const aov = kpi.average_order_value ? fmtINR(kpi.average_order_value) : '-';
  const mgn = fmtPct(Number(kpi.gross_margin_pct || 0));
  const customerCount = Number(kpi.customers || 0);
  const categoryCount = new Set((data.product || []).map(product => product.category).filter(Boolean)).size;
  safeText('kpi-sub-revenue', `Average order: ${aov}`);
  safeText('kpi-sub-gst', `GST estimate: ${fmtINR(kpi.gst_collected || 0)}`);
  safeText('kpi-sub-profit',  `${mgn} margin after costs`);
  safeText('kpi-sub-orders',  `From ${customerCount.toLocaleString('en-IN')} ${customerCount === 1 ? 'customer' : 'customers'}`);
  safeText('kpi-sub-categories', `Across ${categoryCount} product ${categoryCount === 1 ? 'category' : 'categories'}`);

  // ── Pipeline run info ──
  const run = data.pipeline || {};
  if (run.run_at_utc) {
    const alertCount = Number(run.alerts || 0);
    safeText('pipeline-rows', `${Number(run.rows_loaded || 0).toLocaleString('en-IN')} orders`);
    safeText('pipeline-alerts', `${alertCount} ${alertCount === 1 ? 'alert' : 'alerts'}`);
    const d = new Date(run.run_at_utc);
    safeText('pipeline-time', d.toLocaleString('en-IN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }));
  }

  const thresholds = data.thresholds || {};
  const minimumMargin = Number(thresholds.minimum_margin_pct ?? 20);
  const minimumDailyRevenue = Number(thresholds.minimum_daily_revenue ?? 100_000);
  safeText('config-margin-value', `${minimumMargin}%`);
  safeText('config-margin-note', `We’ll flag margins below ${minimumMargin}%.`);
  safeText('config-daily-sales-value', fmtINR(minimumDailyRevenue));
  safeText('config-daily-sales-note', `We’ll flag days below ${fmtINR(minimumDailyRevenue)}.`);
  const marginFill = document.getElementById('config-margin-fill');
  if (marginFill) marginFill.style.width = `${Math.max(0, Math.min(minimumMargin, 100))}%`;
  const marginCurrent = document.getElementById('config-margin-current');
  if (marginCurrent) {
    marginCurrent.style.left = `${Math.max(0, Math.min(Number(kpi.gross_margin_pct || 0), 100))}%`;
  }
  const dailyRows = data.daily || [];
  const latestDailyRevenue = Number(dailyRows[dailyRows.length - 1]?.revenue || 0);
  const dailyProgress = minimumDailyRevenue > 0
    ? Math.max(0, Math.min(latestDailyRevenue / minimumDailyRevenue * 100, 100))
    : 100;
  const dailyFill = document.getElementById('config-daily-sales-fill');
  const dailyMarker = document.getElementById('config-daily-sales-current');
  if (dailyFill) {
    dailyFill.style.width = `${dailyProgress}%`;
    dailyFill.classList.toggle('danger', latestDailyRevenue < minimumDailyRevenue);
  }
  if (dailyMarker) {
    dailyMarker.style.left = `${dailyProgress}%`;
    dailyMarker.classList.toggle('danger', latestDailyRevenue < minimumDailyRevenue);
  }

  // ── Alert badge ──
  const activeAlerts = (data.alerts || []).filter(a => a.type !== 'none');
  const badge = document.getElementById('alert-badge');
  if (badge) badge.textContent = activeAlerts.length;

  // ── Charts ──
  updateCharts(data);
  updateProductCards(data.product || []);

  // ── Transactions table ──
  updateTransactionTable(data.transactions || []);

  // ── Alerts section ──
  updateAlertsSection(data.alerts || []);

  // ── Live events (new orders) ──
  processLiveEvents(data.live_events || []);
}

function safeText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

/* ══════════════════════════════
   CHART UPDATE HELPERS
══════════════════════════════ */
function setChartData(id, labels, datasets) {
  const chart = charts[id];
  if (!chart) return;
  chart.data.labels = labels;
  datasets.forEach((ds, i) => {
    if (chart.data.datasets[i]) {
      chart.data.datasets[i].data = ds;
    }
  });
  chart.update('active');
}

function updateCharts(data) {
  const daily   = data.daily   || [];
  const state   = data.state   || [];
  const channel = data.channel || [];
  const product = data.product || [];

  // Daily trend
  setChartData('dailyChart',
    daily.map(r => r.order_date ? r.order_date.slice(5) : r.order_date),
    [daily.map(r => +r.revenue), daily.map(r => +r.gross_profit)]
  );

  // Channel revenue donut
  setChartData('channelChart',
    channel.map(r => r.channel),
    [channel.map(r => +r.revenue)]
  );

  // State bar
  setChartData('regionChart',
    state.map(r => r.state),
    [state.map(r => +r.revenue)]
  );
  if (charts['regionChart']) {
    const palette = ['rgba(96,165,250,0.8)', 'rgba(34,211,164,0.8)', 'rgba(249,115,22,0.8)', 'rgba(167,139,250,0.8)'];
    charts['regionChart'].data.datasets[0].backgroundColor = state.map((_, index) => palette[index % palette.length]);
    charts['regionChart'].update('active');
  }
  const channelPalette = ['#e879f9', '#7c6df9', '#fbbf24', '#22d3a4'];
  ['channelChart', 'channelUnitsChart'].forEach(id => {
    const chart = charts[id];
    if (!chart) return;
    chart.data.datasets[0].backgroundColor = channel.map((_, index) => channelPalette[index % channelPalette.length]);
    chart.update('active');
  });

  // Margin bar
  if (charts['marginChart']) {
    charts['marginChart'].data.labels = state.map(r => r.state);
    charts['marginChart'].data.datasets[0].data = state.map(r => +r.gross_margin_pct);
    charts['marginChart'].data.datasets[0].backgroundColor = state.map(r =>
      +r.gross_margin_pct >= 60 ? 'rgba(34,211,164,0.8)'
        : +r.gross_margin_pct >= 45 ? 'rgba(124,109,249,0.8)'
        : 'rgba(249,115,22,0.8)'
    );
    charts['marginChart'].update('active');
  }

  // Sales breakdown (sales section)
  setChartData('salesBreakdownChart',
    daily.map(r => r.order_date ? r.order_date.slice(5) : r.order_date),
    [daily.map(r => +r.revenue), daily.map(r => +r.units)]
  );

  // Cost vs Revenue
  setChartData('costRevenueChart',
    state.map(r => r.state),
    [state.map(r => +r.revenue), state.map(r => +r.cost)]
  );

  // Channel units
  setChartData('channelUnitsChart',
    channel.map(r => r.channel),
    [channel.map(r => +r.units)]
  );

  // Product
  setChartData('productChart',
    product.map(r => r.product_name),
    [product.map(r => +r.revenue), product.map(r => +r.units)]
  );

  // Category donut
  const catMap = {};
  product.forEach(r => {
    catMap[r.category] = (catMap[r.category] || 0) + +r.revenue;
  });
  const catLabels = Object.keys(catMap);
  const catData   = catLabels.map(k => catMap[k]);
  setChartData('categoryChart', catLabels, [catData]);

  // State table
  updateRegionTable(state);
}

/* ══════════════════════════════
   TABLE UPDATES
══════════════════════════════ */
function stateBadge(state) {
  return `<span class="state-badge">${state}</span>`;
}

function marginChip(m) {
  return `<span class="margin-chip" style="--m:${m}">${parseFloat(m).toFixed(2)}%</span>`;
}

function updateRegionTable(states) {
  const tbody = document.querySelector('#regionTable tbody');
  if (!tbody || !states.length) return;
  tbody.innerHTML = states.map(r => `
    <tr>
      <td>${stateBadge(r.state)}</td>
      <td>${r.orders}</td>
      <td>${r.units}</td>
      <td>${fmtINR(r.revenue)}</td>
      <td>${fmtINR(r.gst_collected)}</td>
      <td>${fmtINR(r.total_with_gst)}</td>
      <td>${fmtINR(r.cost)}</td>
      <td>${fmtINR(r.gross_profit)}</td>
      <td>${marginChip(r.gross_margin_pct)}</td>
    </tr>`).join('');
}

function updateProductCards(products) {
  const cardIds = { 'P-100': 'p100', 'P-200': 'p200', 'P-300': 'p300' };
  products.forEach(product => {
    const id = cardIds[product.product_id];
    if (!id) return;
    safeText(`${id}-rev`, fmtINR(product.revenue));
    safeText(`${id}-units`, fmtCount(product.units));
    safeText(`${id}-margin`, fmtPct(product.gross_margin_pct));
  });
}

function channelChip(ch) {
  const cls = { Online: 'online', Direct: 'direct', Distributor: 'distributor', Retail: 'retail' }[ch] || 'online';
  return `<span class="channel-chip ${cls}">${ch}</span>`;
}

function updateStateFilter(transactions) {
  const filter = document.getElementById('txState');
  if (!filter) return;

  const selected = filter.value;
  const states = [...new Set(transactions.map(row => row.state || row.region).filter(Boolean))].sort();
  filter.replaceChildren(new Option('All states', ''));
  states.forEach(state => filter.add(new Option(state, state)));
  if (states.includes(selected)) filter.value = selected;
}

function updateTransactionTable(transactions) {
  const tbody = document.getElementById('txBody');
  if (!tbody) return;

  updateStateFilter(transactions);
  const rows = transactions.map(r => {
    const isNew = !seenOrders.has(r.order_id);
    if (isNew) seenOrders.add(r.order_id);
    return `<tr data-state="${r.state || r.region}" data-channel="${r.channel}" class="${isNew && lastData ? 'row-new' : ''}">
      <td><span class="order-id">${r.order_id}</span></td>
      <td>${formatIndianDate(r.order_date)}</td>
      <td>${stateBadge(r.state || r.region)}</td>
      <td>${channelChip(r.channel)}</td>
      <td>${r.product_name}</td>
      <td>${r.category}</td>
      <td>${r.quantity}</td>
      <td>${fmtINR(r.unit_price)}</td>
      <td>${fmtINR(r.revenue)}</td>
      <td>${fmtPct(r.gst_rate_pct || 0)}</td>
      <td>${fmtINR(r.gst_amount)}</td>
      <td>${fmtINR(r.total_with_gst)}</td>
      <td>${fmtINR(r.gross_profit)}</td>
      <td>${marginChip(r.gross_margin_pct)}</td>
    </tr>`;
  });

  tbody.innerHTML = rows.join('');
  safeText('txCount', `${transactions.length.toLocaleString('en-IN')} orders`);
  filterTable(); // re-apply filters
}

function updateAlertsSection(alerts) {
  const grid = document.getElementById('alerts-live-grid');
  if (!grid) return;

  const active = alerts.filter(a => a.type !== 'none');
  if (!active.length) {
    grid.innerHTML = `<div class="alert-card alert-info">
      <div class="alert-icon-wrap">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#22d3a4" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
      </div>
      <div class="alert-body">
        <div class="alert-top-row"><span class="alert-type">All clear</span><span class="alert-severity info">Looking good</span></div>
        <p class="alert-message">Everything looks good — nothing needs your attention right now.</p>
      </div>
    </div>`;
    return;
  }

  grid.innerHTML = active.map(a => {
    const sev    = a.severity || 'info';
    const iconColor = sev === 'high' ? '#f87171' : sev === 'medium' ? '#f59e0b' : '#60a5fa';
    const title = ALERT_TITLES[a.type] || String(a.type || 'Update').replace(/_/g, ' ');
    return `<div class="alert-card alert-${sev}">
      <div class="alert-icon-wrap">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="${iconColor}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
          <line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line>
        </svg>
      </div>
      <div class="alert-body">
        <div class="alert-top-row">
          <span class="alert-type">${title}</span>
          <span class="alert-severity ${sev}">${sev.charAt(0).toUpperCase() + sev.slice(1)}</span>
        </div>
        <p class="alert-message">${a.message}</p>
        <div class="alert-meta"><span>Live</span></div>
      </div>
    </div>`;
  }).join('');
}

/* ══════════════════════════════
   LIVE EVENTS PROCESSING
══════════════════════════════ */
function processLiveEvents(events) {
  events.forEach(ev => {
    if (!lastSeenOrders.has(ev.order_id)) {
      lastSeenOrders.add(ev.order_id);
      if (lastData !== null) {
        // Not on first load — this is genuinely new
        showToast(`A new order just came in: ${ev.product} × ${ev.qty} from ${ev.state || ev.region} — ${fmtINR(ev.total_with_gst ?? ev.revenue)} incl. GST`, 'success', '↑');
        pushTicker(ev);
      } else {
        pushTicker(ev);  // populate ticker on first load silently
      }
    }
  });
}

/* ══════════════════════════════
   CHART BUILDERS (first-time)
══════════════════════════════ */
function buildDailyChart() {
  const canvas = document.getElementById('dailyChart');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const rg = makeGradient(ctx, 'rgba(124,109,249,0.35)', 'rgba(124,109,249,0)');
  const pg = makeGradient(ctx, 'rgba(34,211,164,0.25)',  'rgba(34,211,164,0)');

  charts['dailyChart'] = new Chart(ctx, {
    type: 'line',
    data: {
      labels: [],
      datasets: [
        { label: 'Sales (excl. GST)', data: [], borderColor: '#7c6df9', backgroundColor: rg, borderWidth: 2.5, pointBackgroundColor: '#7c6df9', pointRadius: 4, pointHoverRadius: 6, tension: 0.4, fill: true },
        { label: 'Gross Profit', data: [], borderColor: '#22d3a4', backgroundColor: pg, borderWidth: 2.5, pointBackgroundColor: '#22d3a4', pointRadius: 4, pointHoverRadius: 6, tension: 0.4, fill: true },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => ` ${c.dataset.label}: ${fmtINR(c.parsed.y)}` } } },
      scales: {
        x: { grid: { color: gridColor }, border: { dash: [4, 4] } },
        y: { grid: { color: gridColor }, border: { dash: [4, 4] }, ticks: { callback: fmtINR } },
      },
    },
  });
}

function buildChannelChart() {
  const ctx = document.getElementById('channelChart')?.getContext('2d');
  if (!ctx) return;
  charts['channelChart'] = new Chart(ctx, {
    type: 'doughnut',
    data: { labels: [], datasets: [{ data: [], backgroundColor: ['#e879f9', '#7c6df9', '#fbbf24'], borderWidth: 0, hoverOffset: 8 }] },
    options: {
      responsive: true, maintainAspectRatio: false, cutout: '68%',
      plugins: {
        legend: { display: true, position: 'bottom', labels: { padding: 16, boxWidth: 10, usePointStyle: true, pointStyle: 'circle' } },
        tooltip: { callbacks: { label: c => ` ${c.label}: ${fmtINR(c.parsed)}` } },
      },
    },
  });
}

function buildRegionChart() {
  const ctx = document.getElementById('regionChart')?.getContext('2d');
  if (!ctx) return;
  charts['regionChart'] = new Chart(ctx, {
    type: 'bar',
    data: { labels: [], datasets: [{ label: 'Sales (excl. GST)', data: [], backgroundColor: ['rgba(96,165,250,0.8)', 'rgba(34,211,164,0.8)', 'rgba(249,115,22,0.8)', 'rgba(167,139,250,0.8)'], borderRadius: 6, borderSkipped: false }] },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { tooltip: { callbacks: { label: c => ` Sales (excl. GST): ${fmtINR(c.parsed.y)}` } } },
      scales: { x: { grid: { display: false } }, y: { grid: { color: gridColor }, border: { dash: [4, 4] }, ticks: { callback: fmtINR } } },
    },
  });
}

function buildMarginChart() {
  const ctx = document.getElementById('marginChart')?.getContext('2d');
  if (!ctx) return;
  charts['marginChart'] = new Chart(ctx, {
    type: 'bar',
    data: { labels: [], datasets: [{ label: 'Gross Margin %', data: [], backgroundColor: [], borderRadius: 6, borderSkipped: false }] },
    options: {
      indexAxis: 'y', responsive: true, maintainAspectRatio: false,
      plugins: { tooltip: { callbacks: { label: c => ` Margin: ${c.parsed.x}%` } } },
      scales: { x: { grid: { color: gridColor }, border: { dash: [4, 4] }, ticks: { callback: v => v + '%' }, max: 100 }, y: { grid: { display: false } } },
    },
  });
}

function buildSalesBreakdownChart() {
  const canvas = document.getElementById('salesBreakdownChart');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const rg  = makeGradient(ctx, 'rgba(124,109,249,0.4)', 'rgba(124,109,249,0)');
  charts['salesBreakdownChart'] = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: [],
      datasets: [
        { type: 'line', label: 'Sales (excl. GST)', data: [], borderColor: '#7c6df9', backgroundColor: rg, borderWidth: 2.5, pointBackgroundColor: '#7c6df9', pointRadius: 4, tension: 0.4, fill: true, yAxisID: 'yRevenue' },
        { type: 'bar',  label: 'Items sold',        data: [], backgroundColor: 'rgba(34,211,164,0.7)', borderRadius: 5, yAxisID: 'yUnits' },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: true, position: 'top', align: 'end', labels: { padding: 16, boxWidth: 10, usePointStyle: true, pointStyle: 'circle' } } },
      scales: {
        x:        { grid: { display: false } },
        yRevenue: { grid: { color: gridColor }, border: { dash: [4, 4] }, ticks: { callback: fmtINR }, position: 'left' },
        yUnits:   { grid: { display: false }, ticks: { callback: v => v + ' u' }, position: 'right' },
      },
    },
  });
}

function buildCostRevenueChart() {
  const ctx = document.getElementById('costRevenueChart')?.getContext('2d');
  if (!ctx) return;
  charts['costRevenueChart'] = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: [],
      datasets: [
        { label: 'Sales (excl. GST)', data: [], backgroundColor: 'rgba(124,109,249,0.8)', borderRadius: 5 },
        { label: 'Cost',    data: [], backgroundColor: 'rgba(248,113,113,0.7)', borderRadius: 5 },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { display: true, position: 'top', align: 'end', labels: { padding: 12, boxWidth: 10, usePointStyle: true, pointStyle: 'circle' } },
        tooltip: { callbacks: { label: c => ` ${c.dataset.label}: ${fmtINR(c.parsed.y)}` } },
      },
      scales: { x: { grid: { display: false } }, y: { grid: { color: gridColor }, border: { dash: [4, 4] }, ticks: { callback: fmtINR } } },
    },
  });
}

function buildChannelUnitsChart() {
  const ctx = document.getElementById('channelUnitsChart')?.getContext('2d');
  if (!ctx) return;
  charts['channelUnitsChart'] = new Chart(ctx, {
    type: 'doughnut',
    data: { labels: [], datasets: [{ data: [], backgroundColor: ['#e879f9', '#7c6df9', '#fbbf24'], borderWidth: 0, hoverOffset: 8 }] },
    options: {
      responsive: true, maintainAspectRatio: false, cutout: '68%',
      plugins: {
        legend: { display: true, position: 'bottom', labels: { padding: 16, boxWidth: 10, usePointStyle: true, pointStyle: 'circle' } },
        tooltip: { callbacks: { label: c => ` ${c.label}: ${c.parsed} units` } },
      },
    },
  });
}

function buildProductChart() {
  const ctx = document.getElementById('productChart')?.getContext('2d');
  if (!ctx) return;
  charts['productChart'] = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: [],
      datasets: [
        { label: 'Sales (excl. GST)',  data: [], backgroundColor: ['rgba(249,115,22,0.8)', 'rgba(124,109,249,0.8)', 'rgba(34,211,164,0.8)'], borderRadius: 6, yAxisID: 'yRevenue' },
        { label: 'Items sold',  data: [], backgroundColor: ['rgba(249,115,22,0.25)', 'rgba(124,109,249,0.25)', 'rgba(34,211,164,0.25)'], borderRadius: 6, yAxisID: 'yUnits' },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { display: true, position: 'top', align: 'end', labels: { padding: 12, boxWidth: 10, usePointStyle: true, pointStyle: 'circle' } },
        tooltip: { callbacks: { label: c => c.datasetIndex === 0 ? ` Sales (excl. GST): ${fmtINR(c.parsed.y)}` : ` Items sold: ${c.parsed.y}` } },
      },
      scales: {
        x:        { grid: { display: false } },
        yRevenue: { grid: { color: gridColor }, border: { dash: [4, 4] }, ticks: { callback: fmtINR }, position: 'left' },
        yUnits:   { grid: { display: false }, position: 'right', ticks: { callback: v => v + ' u' } },
      },
    },
  });
}

function buildCategoryChart() {
  const ctx = document.getElementById('categoryChart')?.getContext('2d');
  if (!ctx) return;
  charts['categoryChart'] = new Chart(ctx, {
    type: 'doughnut',
    data: { labels: [], datasets: [{ data: [], backgroundColor: ['#f97316', '#7c6df9', '#22d3a4'], borderWidth: 0, hoverOffset: 8 }] },
    options: {
      responsive: true, maintainAspectRatio: false, cutout: '68%',
      plugins: {
        legend: { display: true, position: 'bottom', labels: { padding: 16, boxWidth: 10, usePointStyle: true, pointStyle: 'circle' } },
        tooltip: { callbacks: { label: c => ` ${c.label}: ${fmtINR(c.parsed)}` } },
      },
    },
  });
}

/* ══════════════════════════════
   SECTION CHARTS REGISTRY
══════════════════════════════ */
function buildSectionCharts(name) {
  switch (name) {
    case 'overview':
      buildDailyChart(); buildChannelChart(); buildRegionChart(); buildMarginChart(); break;
    case 'sales':
      buildSalesBreakdownChart(); buildCostRevenueChart(); buildChannelUnitsChart(); break;
    case 'products':
      buildProductChart(); buildCategoryChart(); break;
  }
}

/* ══════════════════════════════
   NAVIGATION
══════════════════════════════ */
function showSection(name, el) {
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));

  const target = document.getElementById('section-' + name);
  if (target) target.classList.add('active');
  if (el) el.classList.add('active');

  document.getElementById('pageTitle').textContent = PAGE_TITLES[name] || name;
  activeSection = name;

  if (!chartsBuilt[name]) {
    chartsBuilt[name] = true;
    buildSectionCharts(name);
    // Charts were just built, apply current data
    if (lastData) updateCharts(lastData);
  }
}

/* ══════════════════════════════
   SIDEBAR TOGGLE
══════════════════════════════ */
function toggleSidebar() {
  document.getElementById('sidebar').classList.toggle('collapsed');
}

/* ══════════════════════════════
   TRANSACTION FILTER
══════════════════════════════ */
function filterTable() {
  const search  = (document.getElementById('txSearch')?.value  || '').toLowerCase();
  const state   = document.getElementById('txState')?.value    || '';
  const channel = document.getElementById('txChannel')?.value  || '';

  const rows = document.querySelectorAll('#txBody tr');
  let visible = 0;
  rows.forEach(row => {
    const ok = (!search  || row.textContent.toLowerCase().includes(search)) &&
               (!state   || row.dataset.state   === state)   &&
               (!channel || row.dataset.channel === channel);
    row.classList.toggle('hidden-row', !ok);
    if (ok) visible++;
  });
  safeText('txCount', `Showing ${visible} of ${rows.length} orders`);
}

/* ══════════════════════════════
   MANUAL REFRESH
══════════════════════════════ */
async function manualRefresh() {
  showToast('Getting the latest numbers…', 'info', '⟳');
  try {
    const res = await fetch(`${API_BASE}/api/refresh`, { cache: 'no-store' });
    if (!res.ok) {
      const error = await res.json();
      throw new Error(error.detail || error.error || `HTTP ${res.status}`);
    }
    if (!await fetchData()) {
      throw new Error('Pipeline refreshed, but dashboard data could not be loaded');
    }
    showToast('You’re all caught up.', 'success', '✓');
  } catch (err) {
    showToast(`Refresh failed: ${err.message}`, 'error', '✗');
  }
}

async function manualSimulate() {
  showToast('Adding a sample order…', 'info', '+');
  try {
    const res = await fetch(`${API_BASE}/api/simulate`, { cache: 'no-store' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    showToast('Sample order added. It’ll appear shortly.', 'success', '✓');
    setTimeout(fetchData, 1500);
  } catch (err) {
    showToast(`Couldn’t add the sample order: ${err.message}`, 'error', '✗');
  }
}

/* ══════════════════════════════
   POLLING LOOP
══════════════════════════════ */
function startPolling() {
  fetchData(); // immediate first fetch
  pollTimer = setInterval(fetchData, POLL_INTERVAL);
}

/* ══════════════════════════════
   INIT
══════════════════════════════ */
document.addEventListener('DOMContentLoaded', () => {
  // Build overview charts immediately
  chartsBuilt['overview'] = true;
  buildSectionCharts('overview');

  startClock();
  startPolling();
});
