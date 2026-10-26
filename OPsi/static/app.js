/**
 * OPsi — Institutional Options Cockpit Engine
 * Handles reactive state, Top 5 card deck, candidate screener table,
 * live symbol search, multi-column sorting, and explainability drawer.
 */

// Global State
let candidates = [];
let top5Items = [];
let sortKey = 'score';
let sortDir = -1; // -1: descending, 1: ascending
let currentStrategy = '';
let currentAssetType = 'all';
let searchQuery = '';
let activeCandidate = null;
let groupBySymbol = true; // Default to clean accordion view
let expandedSymbols = new Set();
let currentScanInfo = null; // {id, universe, n_candidates} of the scan behind the panel
let fallbackBadge = '';

const STRATEGY_LABELS = {
  csp: 'Cash-Secured Put',
  covered_call: 'Covered Call',
  bull_put_spread: 'Bull Put Spread',
  iron_condor: 'Iron Condor'
};

function strategyLabel(s) {
  return STRATEGY_LABELS[s] || String(s).replace(/_/g, ' ');
}

function fmt(n, d = 1) {
  const v = Number(n);
  return Number.isFinite(v) ? v.toFixed(d) : '-';
}

function esc(s) {
  return String(s || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function calculateDTE(expiryDateStr) {
  if (!expiryDateStr) return null;
  const now = new Date();
  const exp = new Date(expiryDateStr);
  const diffTime = exp.getTime() - now.getTime();
  const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
  return diffDays > 0 ? diffDays : 0;
}

// --------------------------------------------------------------------------
// Top 5 Opportunity Cards (Deprecated in favor of Split-Screen Cockpit)
// --------------------------------------------------------------------------
function renderTop5Cards() {
  // Split cockpit displays all candidates in Master-Detail layout
}


// --------------------------------------------------------------------------
// Screener Table & Filtering
// --------------------------------------------------------------------------
function getFilteredAndSortedRows() {
  let list = candidates.slice();

  // Asset type filter
  if (currentAssetType !== 'all') {
    list = list.filter(c => c.asset_type === currentAssetType);
  }

  // Symbol text filter
  if (searchQuery.trim()) {
    const q = searchQuery.trim().toUpperCase();
    list = list.filter(c => c.symbol.toUpperCase().includes(q));
  }

  // Sort
  list.sort((a, b) => {
    let va = a[sortKey];
    let vb = b[sortKey];
    if (va === null || va === undefined) va = -Infinity;
    if (vb === null || vb === undefined) vb = -Infinity;

    if (typeof va === 'string') {
      return sortDir * va.localeCompare(vb);
    }
    return sortDir * (va - vb);
  });

  return list;
}

async function loadAttributionStrip(strategy) {
  const box = document.getElementById('attribution-strip');
  if (!box || !strategy) return;
  try {
    const res = await fetch(`/api/attribution?strategy=${encodeURIComponent(strategy)}&weeks=12`);
    const data = await res.json();
    const buckets = (data && data.buckets) || [];
    const total = buckets.reduce((a, b) => a + (b.n || 0), 0);
    if (!total) {
      box.innerHTML = `<span class="scan-meta">validation accumulating (n=0)</span>`;
      return;
    }
    if (total < 5) {
      box.innerHTML = `<span class="scan-meta">validation accumulating (n=${total})</span>`;
      return;
    }
    box.innerHTML = buckets.map(b => {
      const win = b.win_rate === null || b.win_rate === undefined ? '—' : `${Math.round(b.win_rate * 100)}%`;
      return `<span class="scan-meta">${esc(b.label)}:${win} (n=${b.n})</span>`;
    }).join(' · ');
  } catch (e) {
    box.innerHTML = `<span class="scan-meta">validation unavailable</span>`;
  }
}

function selectCandidate(candidate, rowElement) {
  if (!candidate) return;
  activeCandidate = candidate;

  // Highlight active row in table
  const tbl = document.getElementById('tbl');
  if (tbl) {
    tbl.querySelectorAll('tr.tr-expandable').forEach(r => r.classList.remove('active-row'));
  }
  if (rowElement) {
    rowElement.classList.add('active-row');
  }

  // Render detail into right inspector pane
  const inspectorContent = document.getElementById('inspector-content');
  if (!inspectorContent) return;

  const dte = calculateDTE(candidate.expiry);
  const stratLabel = strategyLabel(candidate.strategy);
  const assetBadge = candidate.asset_type === 'etf'
    ? `<span class="asset-badge etf">ETF</span>`
    : `<span class="asset-badge stock">STOCK</span>`;

  inspectorContent.innerHTML = `
    <div class="inspector-header-card">
      <div>
        <div style="display:flex; align-items:center; gap:8px; margin-bottom:6px;">
          ${assetBadge}
          <span class="strat-badge ${esc(candidate.strategy || 'csp')}">${esc(stratLabel)}</span>
        </div>
        <div id="attribution-strip" class="attribution-strip"></div>
        <div class="inspector-title-sym">${esc(candidate.symbol)} <span style="font-size:1.1rem; font-weight:500; color:var(--text-secondary);">$${fmt(candidate.strike, 2)} Strike</span></div>
        <div class="inspector-subtitle">Expiry: ${esc(candidate.expiry)} · ${dte !== null ? `${dte} DTE` : ''}</div>
      </div>
      <div class="drawer-score" style="text-align:right;">
        <div class="drawer-score-val">${fmt(candidate.score, 1)}</div>
        <span class="card-score-lbl">Score</span>
      </div>
    </div>
    ${buildCandidateDetailHtml(candidate)}
  `;

  bindCopyButtons(inspectorContent);
  loadAttributionStrip(candidate.strategy);
}

function skipBreakdown(s) {
  if (!s) return '';
  const parts = [];
  if (s.n_skip_price) parts.push(`${s.n_skip_price} price-filtered`);
  if (s.n_empty_chain) parts.push(`${s.n_empty_chain} chainless`);
  if (s.n_skip_stale) parts.push(`${s.n_skip_stale} stale`);
  return parts.length ? ` (${parts.join(', ')})` : '';
}

function renderTable() {
  const container = document.getElementById('tbl');
  const countEl = document.getElementById('candidate-count');
  if (!container) return;

  const rows = getFilteredAndSortedRows();

  if (countEl) {
    countEl.textContent = fallbackBadge + `${rows.length} opportunities passed criteria`;
  }

  if (!rows || rows.length === 0) {
    const scanNote = currentScanInfo && currentScanInfo.universe
      ? `<small>Scan #${esc(String(currentScanInfo.id))} (${esc(currentScanInfo.universe)}) returned ${currentScanInfo.n_candidates ?? 0} option candidates${skipBreakdown(currentScanInfo)}. <a href="/universes" style="color:var(--accent-emerald);">Scan a US universe instead &rarr;</a></small>`
      : `<small>Try clearing the search filter or switching strategies.</small>`;
    container.innerHTML = `
      <div class="empty-state">
        <p>No matching candidate contracts found.</p>
        ${scanNote}
      </div>`;
    const inspectorContent = document.getElementById('inspector-content');
    if (inspectorContent) {
      inspectorContent.innerHTML = `
        <div class="inspector-placeholder">
          <p style="font-weight:500; font-size:0.95rem; color:var(--text-secondary);">No matching opportunities found</p>
          <small style="color:var(--text-muted);">Clear the search filter or switch strategies.</small>
        </div>
      `;
    }
    return;
  }

  const sortArrow = key => (key === sortKey ? (sortDir === 1 ? ' ↑' : ' ↓') : '');
  const activeCls = key => (key === sortKey ? 'sort-active' : '');

  const thead = `
    <thead>
      <tr>
        <th data-k="score" class="${activeCls('score')}">Score${sortArrow('score')}</th>
        <th data-k="symbol" class="${activeCls('symbol')}">Symbol${sortArrow('symbol')}</th>
        <th data-k="asset_type" class="${activeCls('asset_type')}">Type${sortArrow('asset_type')}</th>
        <th data-k="strategy" class="${activeCls('strategy')}">Strategy${sortArrow('strategy')}</th>
        <th data-k="strike" class="${activeCls('strike')}">Strike${sortArrow('strike')}</th>
        <th data-k="expiry" class="${activeCls('expiry')}">Expiry / DTE${sortArrow('expiry')}</th>
        <th data-k="ret_ann" class="${activeCls('ret_ann')}">Ann. Return${sortArrow('ret_ann')}</th>
        <th data-k="prob_otm" class="${activeCls('prob_otm')}">OTM Prob${sortArrow('prob_otm')}</th>
      </tr>
    </thead>
  `;

  let tbody = '';

  if (groupBySymbol) {
    // Group rows by symbol
    const groups = new Map();
    rows.forEach(r => {
      if (!groups.has(r.symbol)) {
        groups.set(r.symbol, []);
      }
      groups.get(r.symbol).push(r);
    });

    if (countEl) {
      countEl.textContent = fallbackBadge + `${groups.size} distinct tickers · ${rows.length} total opportunities`;
    }

    let groupHtml = [];
    groups.forEach((items, sym) => {
      const topItem = items[0]; // best scoring in group
      const otherItems = items.slice(1);
      const isExpanded = expandedSymbols.has(sym);
      const dte = calculateDTE(topItem.expiry);
      const dteBadge = dte !== null ? `<span style="color:var(--text-muted);">(${dte}d)</span>` : '';
      const stratClass = esc(topItem.strategy || 'csp');
      const assetBadge = topItem.asset_type === 'etf'
        ? `<span class="asset-badge etf">ETF</span>`
        : `<span class="asset-badge stock">STOCK</span>`;
      const isActive = activeCandidate && activeCandidate.symbol === topItem.symbol && activeCandidate.strike === topItem.strike && activeCandidate.expiry === topItem.expiry;

      const chevron = otherItems.length > 0
        ? `<span class="symbol-group-chevron ${isExpanded ? 'expanded' : ''}" data-toggle-sym="${esc(sym)}" title="Show/hide ${otherItems.length} other contracts">
             <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="m9 18 6-6-6-6"/></svg>
           </span>`
        : `<span style="width:18px; display:inline-block;"></span>`;

      const variationBadge = otherItems.length > 0
        ? `<span class="variation-count-badge" data-toggle-sym="${esc(sym)}" title="Open all variations">+${otherItems.length} variations</span>`
        : '';

      // Main parent row (Best opportunity for this symbol)
      let rowHtml = `
        <tr class="tr-expandable ${isActive ? 'active-row' : ''}" data-sym="${esc(sym)}" data-strike="${topItem.strike}" data-expiry="${topItem.expiry}" tabindex="0" role="button">
          <td class="td-score">${fmt(topItem.score, 1)}</td>
          <td class="td-symbol">
            ${chevron}
            <span>${esc(topItem.symbol)}</span>
            ${variationBadge}
          </td>
          <td>${assetBadge}</td>
          <td><span class="strat-badge ${stratClass}">${esc(strategyLabel(topItem.strategy))}</span></td>
          <td class="td-mono">$${fmt(topItem.strike, 2)}</td>
          <td class="td-mono">${esc(topItem.expiry)} ${dteBadge}</td>
          <td class="td-ret">+${fmt(Number(topItem.ret_ann) * 100, 1)}%</td>
          <td class="td-mono">${topItem.prob_otm !== null ? (Number(topItem.prob_otm) * 100).toFixed(1) + '%' : '-'}</td>
        </tr>
      `;

      // Child variation rows if expanded
      if (isExpanded && otherItems.length > 0) {
        otherItems.forEach(child => {
          const cDte = calculateDTE(child.expiry);
          const cDteBadge = cDte !== null ? `<span style="color:var(--text-muted);">(${cDte}d)</span>` : '';
          const cStratClass = esc(child.strategy || 'csp');
          const cAssetBadge = child.asset_type === 'etf'
            ? `<span class="asset-badge etf" style="opacity:0.6;">ETF</span>`
            : `<span class="asset-badge stock" style="opacity:0.6;">STOCK</span>`;
          const isChildActive = activeCandidate && activeCandidate.symbol === child.symbol && activeCandidate.strike === child.strike && activeCandidate.expiry === child.expiry;

          rowHtml += `
            <tr class="tr-expandable tr-variation-child ${isChildActive ? 'active-row' : ''}" data-sym="${esc(child.symbol)}" data-strike="${child.strike}" data-expiry="${child.expiry}" tabindex="0" role="button">
              <td class="td-score" style="opacity:0.85;">${fmt(child.score, 1)}</td>
              <td class="td-symbol">
                <span style="color:var(--text-muted); font-size:0.75rem; font-family:var(--font-mono);">↳ var.</span>
              </td>
              <td>${cAssetBadge}</td>
              <td><span class="strat-badge ${cStratClass}">${esc(strategyLabel(child.strategy))}</span></td>
              <td class="td-mono">$${fmt(child.strike, 2)}</td>
              <td class="td-mono">${esc(child.expiry)} ${cDteBadge}</td>
              <td class="td-ret">+${fmt(Number(child.ret_ann) * 100, 1)}%</td>
              <td class="td-mono">${child.prob_otm !== null ? (Number(child.prob_otm) * 100).toFixed(1) + '%' : '-'}</td>
            </tr>
          `;
        });
      }

      groupHtml.push(rowHtml);
    });
    tbody = groupHtml.join('');
  } else {
    // Flat regular rows
    tbody = rows.map((c, i) => {
      const dte = calculateDTE(c.expiry);
      const dteBadge = dte !== null ? `<span style="color:var(--text-muted);">(${dte}d)</span>` : '';
      const stratClass = esc(c.strategy || 'csp');
      const assetBadge = c.asset_type === 'etf'
        ? `<span class="asset-badge etf">ETF</span>`
        : `<span class="asset-badge stock">STOCK</span>`;
      const isActive = activeCandidate && activeCandidate.symbol === c.symbol && activeCandidate.strike === c.strike && activeCandidate.expiry === c.expiry;

      return `
        <tr class="tr-expandable ${isActive ? 'active-row' : ''}" data-sym="${esc(c.symbol)}" data-strike="${c.strike}" data-expiry="${c.expiry}" tabindex="0" role="button" aria-label="${esc(c.symbol)} row">
          <td class="td-score">${fmt(c.score, 1)}</td>
          <td class="td-symbol">${esc(c.symbol)}</td>
          <td>${assetBadge}</td>
          <td><span class="strat-badge ${stratClass}">${esc(strategyLabel(c.strategy))}</span></td>
          <td class="td-mono">$${fmt(c.strike, 2)}</td>
          <td class="td-mono">${esc(c.expiry)} ${dteBadge}</td>
          <td class="td-ret">+${fmt(Number(c.ret_ann) * 100, 1)}%</td>
          <td class="td-mono">${c.prob_otm !== null ? (Number(c.prob_otm) * 100).toFixed(1) + '%' : '-'}</td>
        </tr>
      `;
    }).join('');
  }

  container.innerHTML = `<table class="terminal-table">${thead}<tbody>${tbody}</tbody></table>`;

  // Bind header sorts
  container.querySelectorAll('th[data-k]').forEach(th => {
    th.addEventListener('click', () => {
      const k = th.getAttribute('data-k');
      if (k === sortKey) {
        sortDir = -sortDir;
      } else {
        sortKey = k;
        sortDir = (k === 'score' || k === 'ret_ann' || k === 'prob_otm') ? -1 : 1;
      }
      renderTable();
    });
  });

  // Bind chevron and badge clicks to toggle accordion
  container.querySelectorAll('[data-toggle-sym]').forEach(el => {
    el.addEventListener('click', (e) => {
      e.stopPropagation();
      const s = el.getAttribute('data-toggle-sym');
      if (expandedSymbols.has(s)) {
        expandedSymbols.delete(s);
      } else {
        expandedSymbols.add(s);
      }
      renderTable();
    });
  });

  // Bind row clicks to select candidate into right inspector pane
  container.querySelectorAll('tr.tr-expandable').forEach(tr => {
    const sym = tr.getAttribute('data-sym');
    const strike = parseFloat(tr.getAttribute('data-strike'));
    const expiry = tr.getAttribute('data-expiry');
    const rowItem = rows.find(r => r.symbol === sym && Math.abs(r.strike - strike) < 0.001 && r.expiry === expiry);

    if (rowItem) {
      tr.addEventListener('click', () => {
        selectCandidate(rowItem, tr);
      });

      tr.addEventListener('keydown', e => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          selectCandidate(rowItem, tr);
        }
      });
    }
  });

  // If no candidate is active or active is not in view, auto-select first row
  if (rows.length > 0) {
    if (!activeCandidate || !rows.some(r => r.symbol === activeCandidate.symbol && r.strike === activeCandidate.strike)) {
      const firstRowEl = container.querySelector('tr.tr-expandable');
      selectCandidate(rows[0], firstRowEl);
    }
  }
}

// --------------------------------------------------------------------------
// Detailed Breakdown Builder (Used for both Cards & Table Sub-rows)
// --------------------------------------------------------------------------
function buildCandidateDetailHtml(candidate) {
  const dte = calculateDTE(candidate.expiry);
  const stratLabel = strategyLabel(candidate.strategy);

  // Factor breakdown computation
  const factors = [
    { label: 'Annualized Return', val: fmt(Number(candidate.ret_ann) * 100, 1) + '%', pct: Math.min(100, Math.max(0, Number(candidate.ret_ann) * 100)) },
    { label: 'Exercise (OTM) Probability', val: candidate.prob_otm !== null ? (Number(candidate.prob_otm) * 100).toFixed(1) + '%' : '-', pct: Number(candidate.prob_otm) * 100 || 0 },
    { label: 'Liquidity Score', val: fmt(candidate.liq, 3), pct: (Number(candidate.liq) || 0) * 100 },
    { label: 'Implied Volatility Rank', val: fmt(candidate.iv_rank, 3), pct: (Number(candidate.iv_rank) || 0) * 100 },
    { label: 'Underlying Trend', val: fmt(candidate.trend, 3), pct: (Number(candidate.trend) || 0) * 100 },
    { label: 'Model Adjustment', val: fmt(candidate.adj, 3), pct: Math.max(0, Math.min(100, ((Number(candidate.adj) || 1.0) - 0.8) / 0.4 * 100)) }
  ];

  const factorsHtml = factors.map(f => `
    <div class="factor-item">
      <div class="factor-row">
        <span class="factor-label">${esc(f.label)}</span>
        <span class="factor-val">${esc(f.val)}</span>
      </div>
      <div class="factor-bar-track">
        <div class="factor-bar-fill" style="width: ${Math.max(4, Math.min(100, f.pct))}%"></div>
        </div>
      </div>
    `).join('');

  // Legs & Order Blueprint Construction
  let legsHtml = '';
  let orderSpec = `${candidate.symbol} ${candidate.expiry} $${fmt(candidate.strike, 2)} ${candidate.strategy.toUpperCase()}`;

  if (candidate.strategy === 'csp') {
    const prem = fmt(candidate.max_profit ? candidate.max_profit / 100 : 0.5, 2);
    orderSpec = `STO 1x ${candidate.symbol} ${candidate.expiry} $${fmt(candidate.strike, 2)} PUT @ Mid $${prem}`;
    legsHtml = `
      <table class="legs-table">
        <thead><tr><th>Action</th><th>Leg</th><th>Strike</th><th>Type</th></tr></thead>
        <tbody>
          <tr>
            <td><span class="action-badge sto">STO (Sell)</span></td>
            <td>Short Put</td>
            <td>$${fmt(candidate.strike, 2)}</td>
            <td>Put</td>
          </tr>
        </tbody>
      </table>
    `;
  } else if (candidate.strategy === 'covered_call') {
    const prem = fmt(candidate.max_profit ? candidate.max_profit / 100 : 0.5, 2);
    orderSpec = `LONG 100x ${candidate.symbol} + STO 1x ${candidate.expiry} $${fmt(candidate.strike, 2)} CALL @ Mid $${prem}`;
    legsHtml = `
      <table class="legs-table">
        <thead><tr><th>Action</th><th>Leg</th><th>Strike / Price</th><th>Type</th></tr></thead>
        <tbody>
          <tr>
            <td><span class="action-badge bto">HOLD</span></td>
            <td>Underlying</td>
            <td>100 Shares</td>
            <td>Stock/ETF</td>
          </tr>
          <tr>
            <td><span class="action-badge sto">STO (Sell)</span></td>
            <td>Short Call</td>
            <td>$${fmt(candidate.strike, 2)}</td>
            <td>Call</td>
          </tr>
        </tbody>
      </table>
    `;
  } else if (candidate.strategy === 'bull_put_spread' && candidate.legs && candidate.legs.length >= 2) {
    const [shortLeg, longLeg] = candidate.legs;
    orderSpec = `STO 1x ${candidate.symbol} ${candidate.expiry} $${fmt(shortLeg.strike, 2)} PUT | BTO 1x $${fmt(longLeg.strike, 2)} PUT (Net Credit: $${fmt(shortLeg.mid - longLeg.mid, 2)})`;
    legsHtml = `
      <table class="legs-table">
        <thead><tr><th>Action</th><th>Leg</th><th>Strike</th><th>Mid</th></tr></thead>
        <tbody>
          <tr>
            <td><span class="action-badge sto">STO (Sell)</span></td>
            <td>Short Put</td>
            <td>$${fmt(shortLeg.strike, 2)}</td>
            <td>$${fmt(shortLeg.mid, 2)}</td>
          </tr>
          <tr>
            <td><span class="action-badge bto">BTO (Buy)</span></td>
            <td>Long Put</td>
            <td>$${fmt(longLeg.strike, 2)}</td>
            <td>$${fmt(longLeg.mid, 2)}</td>
          </tr>
        </tbody>
      </table>
    `;
  } else {
    legsHtml = `
      <div style="font-size:0.8rem; color:var(--text-muted); padding:8px 0;">
        Multi-leg structure: ${esc(candidate.strategy.replace(/_/g, ' '))}
      </div>
    `;
  }

  function renderPayoffSvg(c) {
    const k = Number(c.strike) || 20.0;
    const maxProfit = Number(c.max_profit) || 50.0;
    const maxLoss = Number(c.max_loss) || 150.0;
    const be = Number(c.breakeven) || (k * 0.95);
    const strat = c.strategy || 'csp';

    let ruleExplanation = '';
    let curvePath = '';
    let profitArea = '';
    let lossArea = '';
    let beX = 140;

    if (strat === 'csp') {
      ruleExplanation = `<b>Rule:</b> If the stock stays above <b>$${fmt(k, 2)}</b> on expiry, net <b>+$${fmt(maxProfit, 0)}</b> profit is kept. Loss starts below <b>$${fmt(be, 2)}</b>.`;
      beX = 140;
      curvePath = `M 20,105 L ${beX},60 L 220,25 L 320,25`;
      profitArea = `M ${beX},60 L 220,25 L 320,25 L 320,60 Z`;
      lossArea = `M 20,60 L ${beX},60 L 20,105 Z`;
    } else if (strat === 'covered_call') {
      ruleExplanation = `<b>Rule:</b> If the stock rises to strike <b>$${fmt(k, 2)}</b>, max <b>+$${fmt(maxProfit, 0)}</b> profit is taken. Breakeven: <b>$${fmt(be, 2)}</b>.`;
      beX = 130;
      curvePath = `M 20,105 L ${beX},60 L 230,25 L 320,25`;
      profitArea = `M ${beX},60 L 230,25 L 320,25 L 320,60 Z`;
      lossArea = `M 20,60 L ${beX},60 L 20,105 Z`;
    } else if (strat === 'bull_put_spread') {
      ruleExplanation = `<b>Rule:</b> As long as the stock stays above upper strike <b>$${fmt(k, 2)}</b>, max <b>+$${fmt(maxProfit, 0)}</b> profit is taken. Max loss is strictly capped at <b>-$${fmt(maxLoss, 0)}</b>.`;
      beX = 160;
      curvePath = `M 20,100 L 90,100 L ${beX},60 L 220,25 L 320,25`;
      profitArea = `M ${beX},60 L 220,25 L 320,25 L 320,60 Z`;
      lossArea = `M 20,60 L ${beX},60 L 90,100 L 20,100 Z`;
    } else {
      ruleExplanation = `<b>Rule:</b> Max <b>+$${fmt(maxProfit, 0)}</b> profit is earned when the stock stays in range. Wings limit risk.`;
      beX = 100;
      curvePath = `M 20,95 L 80,95 L 120,25 L 220,25 L 260,95 L 320,95`;
      profitArea = `M 100,60 L 120,25 L 220,25 L 240,60 Z`;
      lossArea = `M 20,60 L 100,60 L 80,95 L 20,95 Z`;
    }

    return `
      <div class="payoff-chart-container">
        <div class="payoff-chart-header">
          <span>Expiry Payoff (Profit / Loss Diagram)</span>
          <div class="payoff-legend">
            <span class="legend-item"><span class="legend-dot profit"></span> Profit Zone</span>
            <span class="legend-item"><span class="legend-dot loss"></span> Loss Zone</span>
            <span class="legend-item"><span class="legend-dot be"></span> Breakeven</span>
          </div>
        </div>

        <svg class="payoff-svg" viewBox="0 0 340 120">
          <defs>
            <linearGradient id="profitGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="#10b981" stop-opacity="0.35"/>
              <stop offset="100%" stop-color="#10b981" stop-opacity="0.05"/>
            </linearGradient>
            <linearGradient id="lossGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="#ef4444" stop-opacity="0.05"/>
              <stop offset="100%" stop-color="#ef4444" stop-opacity="0.35"/>
            </linearGradient>
          </defs>

          <path d="${profitArea}" fill="url(#profitGrad)" />
          <path d="${lossArea}" fill="url(#lossGrad)" />

          <line x1="15" y1="60" x2="325" y2="60" stroke="rgba(255,255,255,0.2)" stroke-dasharray="3,3" stroke-width="1.2" />
          <text x="328" y="63" fill="#64748b" font-size="9" font-family="var(--font-mono)">$0</text>

          <path d="${curvePath}" fill="none" stroke="#f8fafc" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" />

          <line x1="200" y1="25" x2="320" y2="25" stroke="#10b981" stroke-width="1" stroke-dasharray="2,2" />
          <text x="315" y="20" fill="#10b981" font-size="10" font-family="var(--font-mono)" font-weight="700" text-anchor="end">MAX: +$${fmt(maxProfit, 0)}</text>

          <text x="25" y="115" fill="#ef4444" font-size="10" font-family="var(--font-mono)" font-weight="700">RISK: -$${fmt(maxLoss, 0)}</text>

          <circle cx="${beX}" cy="60" r="4.5" fill="#f59e0b" stroke="#0b111e" stroke-width="1.5" />
          <line x1="${beX}" y1="45" x2="${beX}" y2="75" stroke="#f59e0b" stroke-width="1" stroke-dasharray="2,2" />
          <text x="${beX}" y="78" fill="#f59e0b" font-size="9.5" font-family="var(--font-mono)" font-weight="700" text-anchor="middle">Breakeven $${fmt(be, 2)}</text>

          <text x="25" y="55" fill="#94a3b8" font-size="8.5">← Stock Down</text>
          <text x="280" y="55" fill="#94a3b8" font-size="8.5">Stock Up →</text>
        </svg>

        <div class="payoff-rule-box">
          ${ruleExplanation}
        </div>
      </div>
    `;
  }

  return `
    <div class="detail-columns-layout">
      <!-- Left Column: Trade Blueprint & Payoff -->
      <div>
        <div class="blueprint-card" style="margin-top:0;">
          <div class="blueprint-header">
            <span>Trade Blueprint & Capital</span>
            <span style="color:var(--text-muted); font-size:0.75rem;">1 Contract (x100)</span>
          </div>
          <div class="blueprint-grid">
            <div class="blueprint-metric">
              <span class="blueprint-metric-lbl">Max Profit</span>
              <span class="blueprint-metric-val profit">+$${fmt(candidate.max_profit || 0, 0)}</span>
            </div>
            <div class="blueprint-metric">
              <span class="blueprint-metric-lbl">Max Risk</span>
              <span class="blueprint-metric-val loss">$${fmt(candidate.max_loss || 0, 0)}</span>
            </div>
            <div class="blueprint-metric">
              <span class="blueprint-metric-lbl">Break-even</span>
              <span class="blueprint-metric-val">$${fmt(candidate.breakeven || candidate.strike, 2)}</span>
            </div>
          </div>
          <div>${legsHtml}</div>
          ${renderPayoffSvg(candidate)}
        </div>
      </div>

      <!-- Right Column: Order Blueprint & Conviction Decomposition -->
      <div style="display:flex; flex-direction:column; gap:16px;">
        <div>
          <div class="drawer-section-title" style="margin-top:0;">Execution Order Spec</div>
          <div style="background:var(--bg-base); padding:12px; border-radius:var(--radius-sm); border:1px solid var(--border-subtle); margin-bottom:10px;">
            <code style="font-family:var(--font-mono); font-size:0.82rem; color:var(--text-primary); line-height:1.4; display:block;">${esc(orderSpec)}</code>
          </div>
          <button class="btn-copy-order btn-inline-copy" data-spec="${esc(orderSpec)}">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>
            Copy Broker Order Specification
          </button>
        </div>

        <div>
          <div class="drawer-section-title">6-Factor Conviction Decomposition</div>
          <div class="factor-grid">${factorsHtml}</div>
        </div>
      </div>
    </div>
  `;
}

function bindCopyButtons(parent) {
  parent.querySelectorAll('.btn-inline-copy').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const spec = btn.getAttribute('data-spec');
      if (!spec) return;
      navigator.clipboard.writeText(spec).then(() => {
        const originalHtml = btn.innerHTML;
        btn.innerHTML = `
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M20 6 9 17l-5-5"/></svg>
          Copied to Clipboard!
        `;
        setTimeout(() => {
          btn.innerHTML = originalHtml;
        }, 2000);
      }).catch(() => {
        alert('Copied: ' + spec);
      });
    });
  });
}


// --------------------------------------------------------------------------
// Strategy Filter Bar
// --------------------------------------------------------------------------
async function loadStrategies() {
  try {
    const res = await fetch('/api/strategies');
    const data = await res.json();
    const container = document.getElementById('strats');
    if (!container) return;

    const mkBtn = (val, label) => `
      <button class="strat-pill" data-s="${val}" aria-pressed="${val === currentStrategy}">
        ${label}
      </button>
    `;

    container.innerHTML = mkBtn('', 'All Strategies') +
      (data.strategies || []).map(s => mkBtn(s, strategyLabel(s))).join('');

    container.querySelectorAll('button[data-s]').forEach(btn => {
      btn.addEventListener('click', () => {
        currentStrategy = btn.getAttribute('data-s') || '';
        container.querySelectorAll('button[data-s]').forEach(b => {
          b.setAttribute('aria-pressed', (b.getAttribute('data-s') || '') === currentStrategy ? 'true' : 'false');
        });
        loadData();
      });
    });
  } catch (err) {
    console.error('Failed to load strategies:', err);
  }
}

// --------------------------------------------------------------------------
// Main Data Fetching & UI Paint
// --------------------------------------------------------------------------
async function loadData() {
  const params = new URLSearchParams();
  if (currentStrategy) params.append('strategy', currentStrategy);
  if (currentAssetType && currentAssetType !== 'all') params.append('asset_type', currentAssetType);

  const qs = params.toString() ? '?' + params.toString() : '';
  const statusPill = document.getElementById('scan-status-text');

  try {
    const resTop = await fetch('/api/top5' + qs);
    const dataTop = await resTop.json();
    top5Items = dataTop.items || [];

    if (statusPill) {
      if (dataTop.as_of !== null && dataTop.as_of !== undefined) {
        statusPill.textContent = `Scan #${dataTop.as_of} Live`;
      } else {
        statusPill.textContent = 'No scan completed yet';
      }
    }

    fallbackBadge = (dataTop.as_of_is_latest === false && dataTop.as_of !== null) ? `showing last non-empty scan #${dataTop.as_of} · ` : '';

    try {
      const resScans = await fetch('/api/scans?limit=25');
      const dataScans = await resScans.json();
      currentScanInfo = ((dataScans && dataScans.scans) || []).find(s => s.id === dataTop.as_of) || null;
    } catch (scanErr) {
      currentScanInfo = null;
    }

    if (dataTop.as_of !== null && dataTop.as_of !== undefined) {
      const candParams = new URLSearchParams();
      candParams.append('scan_id', dataTop.as_of);
      candParams.append('limit', '800');
      candParams.append('per_symbol_limit', '30');
      if (currentStrategy) candParams.append('strategy', currentStrategy);
      if (currentAssetType && currentAssetType !== 'all') candParams.append('asset_type', currentAssetType);

      const resCands = await fetch(`/api/candidates?` + candParams.toString());
      const dataCands = await resCands.json();
      candidates = dataCands.items || [];
    } else {
      candidates = [];
    }
  } catch (err) {
    console.error('Error fetching data:', err);
    if (statusPill) statusPill.textContent = 'API Offline';
    top5Items = [];
    candidates = [];
  }

  renderTop5Cards(top5Items);
  renderTable();
}

// --------------------------------------------------------------------------
// Watchlist Management
// --------------------------------------------------------------------------
// --------------------------------------------------------------------------
// Lists Page loaders
// --------------------------------------------------------------------------
async function loadListsPage() {
  await Promise.all([loadWatchlists(), loadRecentScans(), loadMathSettings()]);
}

// --------------------------------------------------------------------------
// Global scan progress (all pages): polls the 202-started background scan
// every 2s, updates the under-header bar, refreshes the page when done.
// --------------------------------------------------------------------------
let activeScanSeen = null;
let scanToastTimer = null;

async function startScan(url, btn, busyLabel) {
  const orig = btn.innerHTML;
  btn.innerHTML = esc(busyLabel);
  btn.disabled = true;
  try {
    const res = await fetch(url, { method: 'POST' });
    if (res.status === 409) {
      alert('A scan is already running — progress above.');
      return;
    }
    const scanRes = await res.json();
    if (scanRes.status === 'ok') {
      pollScanProgress();
    } else {
      alert('Could not start scan.');
    }
  } catch (e) {
    alert('Scan error: ' + e.message);
  } finally {
    btn.innerHTML = orig;
    btn.disabled = false;
  }
}

function showScanToast(text) {
  const toast = document.getElementById('scan-toast');
  if (!toast) return;
  toast.textContent = text;
  toast.hidden = false;
  if (scanToastTimer) clearTimeout(scanToastTimer);
  scanToastTimer = setTimeout(() => { toast.hidden = true; }, 9000);
}

async function onScanFinished(scanId) {
  try {
    const res = await fetch('/api/scans?limit=10');
    const data = await res.json();
    const s = ((data && data.scans) || []).find(x => x.id === scanId);
    const extra = skipBreakdown(s);
    showScanToast(s
      ? `Scan #${s.id} done · ${s.universe || 'custom'} · ${s.n_candidates ?? 0} candidates${extra}`
      : `Scan #${scanId} done`);
  } catch (e) {
    showScanToast(`Scan #${scanId} done`);
  }
  const page = (location.pathname.split('/')[1] || 'panel');
  if (page === 'panel') loadData();
  else if (page === 'universes') { loadPresets(); loadUniverses(); }
  else if (page === 'lists') { loadWatchlists(); loadRecentScans(); }
  else if (page === 'settings') loadMathSettings();
}

async function pollScanProgress() {
  const bar = document.getElementById('scan-progress');
  if (!bar) return;
  const fill = document.getElementById('scan-progress-fill');
  const label = document.getElementById('scan-progress-text');
  try {
    const res = await fetch('/api/scans/active');
    const st = await res.json();
    if (st && st.running) {
      activeScanSeen = st.scan_id;
      bar.hidden = false;
      const pct = st.total > 0 ? Math.round((st.done / st.total) * 100) : 0;
      if (fill) fill.style.transform = `scaleX(${st.total > 0 ? st.done / st.total : 0})`;
      if (label) label.textContent = `Scan #${st.scan_id} · ${st.universe || ''} · ${st.done}/${st.total} · ${st.symbol || ''}`;
    } else if (activeScanSeen !== null) {
      const doneId = activeScanSeen;
      activeScanSeen = null;
      bar.hidden = true;
      onScanFinished(doneId);
    } else {
      bar.hidden = true;
    }
  } catch (e) {
    bar.hidden = true;
  }
}

function fmtScanDate(iso) {
  if (!iso) return '-';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? '-' : d.toLocaleString('en-US', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
}

async function fetchScansByUniverse() {
  try {
    const res = await fetch('/api/scans?limit=50');
    const data = await res.json();
    const map = {};
    for (const s of (data && data.scans) || []) {
      const key = (s.universe || '').toLowerCase();
      if (key && !map[key]) map[key] = s;
    }
    return map;
  } catch (err) {
    console.error('Scans fetch error:', err);
    return {};
  }
}

async function loadRecentScans() {
  const box = document.getElementById('recent-scans-list');
  if (!box) return;
  try {
    const res = await fetch('/api/scans?limit=10');
    const data = await res.json();
    const scans = (data && data.scans) || [];
    if (scans.length === 0) {
      box.innerHTML = `
        <div style="padding:16px; text-align:center; color:var(--text-muted); background:var(--bg-surface); border-radius:var(--radius-sm);">
          No scan records yet.
        </div>`;
      return;
    }
    box.innerHTML = scans.map(s => `
      <div class="watchlist-item-card">
        <div class="wl-card-info">
          <div class="wl-card-title">#${s.id} · ${esc(s.universe || 'custom')}</div>
          <div class="scan-meta">${esc(s.status || '')} · ${s.n_candidates ?? 0} candidates · ${fmtScanDate(s.finished_at || s.started_at)}</div>
        </div>
      </div>
    `).join('');
  } catch (err) {
    console.error('Recent scans error:', err);
  }
}

// --------------------------------------------------------------------------
// Scan Math settings (adjustable thresholds/weights/multipliers)
// --------------------------------------------------------------------------
const MATH_LABELS = {
  filters: 'Filters (Layer-1)',
  weights: 'Score Weights (Layer-2)',
  academic: 'Academic Multipliers (Layer-3)',
  general: 'General',
  flags: 'Flags',
  dte_min: 'DTE min (days)', dte_max: 'DTE max (days)',
  put_lo: 'Put delta low', put_hi: 'Put delta high',
  call_lo: 'Call delta low', call_hi: 'Call delta high',
  spread_max: 'Max spread / mid', vol_min: 'Min volume', oi_min: 'Min open interest',
  capital_max: 'Capital cap ($)', csp_price_max: 'CSP max stock ($)',
  cc_capital_max: 'Outlier strike filter ($)', width_max: 'Max spread width ($)',
  pairs_max: 'Max matches per short', earnings_days: 'Earnings exclusion (days)',
  spread_penalty: 'Spread penalty factor',
  ret: 'Return', otm: 'OTM probability', liq: 'Liquidity', iv: 'IV rank', trend: 'Trend',
  ret_norm_hi: 'Return norm cap',
  skew_hi: 'Skew upper threshold (IV)', skew_lo: 'Skew lower threshold (IV)',
  m_skew_hi: 'Multiplier: high IV', m_skew_lo: 'Multiplier: attractive premium',
  term_dte: 'Short-term threshold (DTE)', m_term: 'Multiplier: short term',
  jump_days: 'Earnings window (days)', m_jump: 'Multiplier: near earnings',
  clamp_lo: 'Multiplier lower bound', clamp_hi: 'Multiplier upper bound',
  risk_free: 'Risk-free rate', stock_w: 'Stock score weight', contract_w: 'Contract score weight',
  skew: 'Skew', term: 'Term', jump: 'Earnings'
};

let mathDefaults = null;

async function loadMathSettings() {
  const box = document.getElementById('math-settings');
  if (!box) return;
  try {
    const data = await (await fetch('/api/settings/params')).json();
    mathDefaults = data.defaults;
    renderMathSettings(box, data.active);
  } catch (err) {
    console.error('Math settings error:', err);
    box.innerHTML = `<div style="color:var(--text-muted);">Could not load settings.</div>`;
  }
}

function renderMathSettings(box, active) {
  box.innerHTML = Object.entries(active).map(([section, vals]) => `
    <div class="math-group">
      <div class="math-group-title">${esc(MATH_LABELS[section] || section)}</div>
      ${Object.entries(vals).map(([k, v]) => {
        const label = MATH_LABELS[k] || k;
        if (typeof v === 'boolean') {
          return `<label class="math-field math-check"><input type="checkbox" data-sec="${section}" data-key="${k}" ${v ? 'checked' : ''}><span>${esc(label)}</span></label>`;
        }
        const step = Number.isInteger(v) ? '1' : '0.01';
        return `<label class="math-field"><span>${esc(label)}</span><input class="input-styled math-num" type="number" step="${step}" value="${v}" data-sec="${section}" data-key="${k}"></label>`;
      }).join('')}
    </div>`).join('');
  updateWeightNote();
  box.oninput = updateWeightNote;
}

function readMathSettings() {
  const box = document.getElementById('math-settings');
  const body = {};
  if (!box) return body;
  box.querySelectorAll('[data-sec]').forEach(el => {
    const sec = el.getAttribute('data-sec');
    const key = el.getAttribute('data-key');
    body[sec] = body[sec] || {};
    if (el.type === 'checkbox') {
      body[sec][key] = el.checked;
    } else {
      const v = parseFloat(el.value);
      body[sec][key] = Number.isFinite(v) ? v : 0;
    }
  });
  return body;
}

function updateWeightNote() {
  const note = document.getElementById('math-weight-note');
  if (!note) return;
  const body = readMathSettings();
  const w = (body && body.weights) || {};
  const sum = ['ret', 'otm', 'liq', 'iv', 'trend'].reduce((a, k) => a + (Number(w[k]) || 0), 0);
  note.textContent = `Weight total: ${sum.toFixed(2)} (auto-normalized if not 1)`;
}

async function saveMathSettings(payload, note) {
  const res = await fetch('/api/settings/params', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ params: payload })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    alert(err.detail || 'Could not save.');
    return;
  }
  const data = await res.json();
  const box = document.getElementById('math-settings');
  if (box) renderMathSettings(box, data.active);
  if (note) {
    note.textContent = 'Saved — future scans will use this set.';
    setTimeout(updateWeightNote, 3000);
  }
}

function bindMathSettings() {
  const btnSave = document.getElementById('btn-math-save');
  if (btnSave) {
    btnSave.addEventListener('click', async () => {
      btnSave.disabled = true;
      try {
        await saveMathSettings(readMathSettings(), document.getElementById('math-weight-note'));
      } catch (e) {
        alert('Connection error: ' + e.message);
      } finally {
        btnSave.disabled = false;
      }
    });
  }
  const btnReset = document.getElementById('btn-math-reset');
  if (btnReset) {
    btnReset.addEventListener('click', async () => {
      if (!mathDefaults) return;
      if (!confirm('Reset all math settings to defaults?')) return;
      btnReset.disabled = true;
      try {
        await saveMathSettings(mathDefaults, document.getElementById('math-weight-note'));
      } catch (e) {
        alert('Connection error: ' + e.message);
      } finally {
        btnReset.disabled = false;
      }
    });
  }
}

async function loadWatchlists() {
  const container = document.getElementById('watchlist-items-list');
  if (!container) return;

  try {
    const res = await fetch('/api/watchlists');
    const lists = await res.json();
    if (!lists || lists.length === 0) {
      container.innerHTML = `
        <div style="padding:20px; text-align:center; color:var(--text-muted); background:var(--bg-surface); border-radius:var(--radius-sm);">
          No custom lists yet. Add your first list above!
        </div>
      `;
    } else {
    container.innerHTML = lists.map(w => `
      <div class="watchlist-item-card">
        <div class="wl-card-info">
          <div class="wl-card-title">${esc(w.name)}</div>
          <div class="wl-sym-tags">
            ${w.symbols.map(s => `<span class="wl-tag">${esc(s)}</span>`).join('')}
          </div>
        </div>
        <div class="wl-card-actions">
          <button class="btn-sm-scan" data-scan-wlid="${w.id}">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="margin-right:3px;"><polygon points="5 3 19 12 5 21 5 3"/></svg>
            Scan This List
          </button>
          <button class="btn-sm-del" data-del-wlid="${w.id}" title="Delete List">&times;</button>
        </div>
      </div>
    `).join('');

    // Bind scan watchlist buttons
    container.querySelectorAll('[data-scan-wlid]').forEach(btn => {
      btn.addEventListener('click', () => {
        const wid = btn.getAttribute('data-scan-wlid');
        startScan(`/api/scan-custom?watchlist_id=${wid}`, btn, 'Scanning...');
      });
    });

    // Bind delete buttons
    container.querySelectorAll('[data-del-wlid]').forEach(btn => {
      btn.addEventListener('click', async () => {
        const wid = btn.getAttribute('data-del-wlid');
        if (!confirm('Are you sure you want to delete this list?')) return;
        try {
          await fetch(`/api/watchlists/${wid}`, { method: 'DELETE' });
          loadWatchlists();
        } catch (e) {
          alert('Could not delete: ' + e.message);
        }
      });
    });
    } // else: empty message shown when there are no custom lists; presets/universes still load
  } catch (err) {
    console.error('Watchlist fetch error:', err);
  }
}

async function loadUniverses() {
  const uniContainer = document.getElementById('universe-items-list');
  if (!uniContainer) return;

  try {
    const [res, scansByUni] = await Promise.all([fetch('/api/universes'), fetchScansByUniverse()]);
    const data = await res.json();
    const unis = (data && data.universes) || [];
    if (unis.length === 0) {
      uniContainer.innerHTML = `
        <div style="padding:16px; text-align:center; color:var(--text-muted); background:var(--bg-surface); border-radius:var(--radius-sm);">
          Index universes could not be loaded.
        </div>
      `;
      return;
    }

    uniContainer.innerHTML = unis.map(u => {
      const last = scansByUni[(u.id || '').toLowerCase()];
      const lastTxt = last
        ? ` · last: #${last.id} ${esc(last.status || '')} · ${last.n_candidates ?? 0} candidates · ${fmtScanDate(last.finished_at || last.started_at)}`
        : ' · not scanned yet';
      const cacheTxt = u.cached_at ? ` · cached ${fmtScanDate(u.cached_at)}` : '';
      const exp = u.expect;
      const expTxt = exp && exp.of ? ` · CSP-ok ${exp.csp_ok}/${exp.of}${exp.unknown ? ` (${exp.unknown} unknown)` : ''}` : ' · expectation after first scan';
      return `
      <div class="watchlist-item-card" style="border-color: rgba(16,185,129,0.35);">
        <div class="wl-card-info">
          <div class="wl-card-title">${esc(u.title)}</div>
          <div style="font-size:0.78rem; color:var(--text-muted); margin-bottom:4px;">${esc(u.desc)}</div>
          <div class="scan-meta">${u.count ? `<b style="color:var(--text-secondary);">${u.count} symbols</b>` : ''}${cacheTxt}${lastTxt}${expTxt}</div>
        </div>
        <div class="wl-card-actions">
          <button class="btn-sm-scan" data-scan-universe="${esc(u.id)}">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="margin-right:3px;"><polygon points="5 3 19 12 5 21 5 3"/></svg>
            Scan This Universe
          </button>
        </div>
      </div>
      `;
    }).join('');

    uniContainer.querySelectorAll('[data-scan-universe]').forEach(btn => {
      btn.addEventListener('click', () => {
        const uid = btn.getAttribute('data-scan-universe') || '';
        startScan(`/api/scan-custom?universe=${encodeURIComponent(uid)}`, btn, 'Scanning universe...');
      });
    });
  } catch (err) {
    console.error('Universes fetch error:', err);
  }
}

async function loadPresets() {
  const presetContainer = document.getElementById('preset-items-list');
  if (!presetContainer) return;

  try {
    const res = await fetch('/api/presets');
    const presets = await res.json();
    if (!presets) return;

    presetContainer.innerHTML = Object.entries(presets).map(([key, p]) => {
      const exp = p.expect;
      const expTxt = exp && exp.of ? `CSP-ok ${exp.csp_ok}/${exp.of}${exp.unknown ? ` (${exp.unknown} unknown)` : ''}` : 'expectation after first scan';
      return `
        <div class="watchlist-item-card" style="border-color: rgba(6,182,212,0.35);">
        <div class="wl-card-info">
          <div class="wl-card-title">${esc(p.title)}</div>
          <div style="font-size:0.78rem; color:var(--text-muted); margin-bottom:4px;">${esc(p.desc)}</div>
          <div class="scan-meta">${expTxt}</div>
          <div class="wl-sym-tags">
            ${p.symbols.map(s => `<span class="wl-tag" style="color:var(--accent-cyan); border-color:rgba(6,182,212,0.3);">${esc(s)}</span>`).join('')}
          </div>
        </div>
        <div class="wl-card-actions">
          <button class="btn-sm-scan" data-scan-preset-syms="${p.symbols.join(',')}" style="background:rgba(6,182,212,0.15); color:var(--accent-cyan); border-color:rgba(6,182,212,0.4);">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="margin-right:3px;"><polygon points="5 3 19 12 5 21 5 3"/></svg>
            Scan This Universe
          </button>
          <button class="btn-action" data-add-preset-wlid="${key}" title="Save to My Lists" style="padding:5px 10px; font-size:0.75rem;">
            + Add to My List
          </button>
        </div>
      </div>
    `;
    }).join('');

    // Bind scan preset buttons
    presetContainer.querySelectorAll('[data-scan-preset-syms]').forEach(btn => {
      btn.addEventListener('click', () => {
        const symsStr = btn.getAttribute('data-scan-preset-syms') || '';
        const syms = symsStr.split(',').filter(Boolean);
        const queryParams = syms.map(s => `symbols=${encodeURIComponent(s)}`).join('&');
        startScan(`/api/scan-custom?${queryParams}`, btn, 'Scanning universe...');
      });
    });

    // Bind add preset to custom watchlist buttons
    presetContainer.querySelectorAll('[data-add-preset-wlid]').forEach(btn => {
      btn.addEventListener('click', async () => {
        const key = btn.getAttribute('data-add-preset-wlid');
        const p = presets[key];
        if (!p) return;
        btn.disabled = true;
        try {
          const res = await fetch('/api/watchlists', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: p.title.replace(/^[^\w\s]+/, '').trim(), symbols: p.symbols })
          });
          if (res.ok) {
            await loadWatchlists();
          } else {
            const err = await res.json();
            alert(err.detail || 'Could not add.');
          }
        } catch (e) {
          alert('Error: ' + e.message);
        } finally {
          btn.disabled = false;
        }
      });
    });
  } catch (err) {
    console.error('Presets fetch error:', err);
  }
}

// --------------------------------------------------------------------------
// Initialization & Listeners
// --------------------------------------------------------------------------
function init() {
  // Asset filter pills
  const assetPills = document.querySelectorAll('#asset-type-filters .asset-pill');
  assetPills.forEach(pill => {
    pill.addEventListener('click', () => {
      assetPills.forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      currentAssetType = pill.getAttribute('data-type') || 'all';
      loadData();
    });
  });

  // Search input listener
  const searchInput = document.getElementById('filter-search');
  if (searchInput) {
    searchInput.addEventListener('input', e => {
      searchQuery = e.target.value;
      renderTable();
    });
  }

  // Refresh button
  const refreshBtn = document.getElementById('btn-refresh');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', () => {
      loadData();
    });
  }

  // Group by symbol toggle button
  const toggleGroupBtn = document.getElementById('btn-toggle-group');
  if (toggleGroupBtn) {
    toggleGroupBtn.addEventListener('click', () => {
      groupBySymbol = !groupBySymbol;
      if (groupBySymbol) {
        toggleGroupBtn.classList.add('active');
        toggleGroupBtn.querySelector('span').textContent = 'Grouped View';
      } else {
        toggleGroupBtn.classList.remove('active');
        toggleGroupBtn.querySelector('span').textContent = 'Flat List';
      }
      renderTable();
    });
  }

  // Create watchlist form
  const btnCreateWl = document.getElementById('btn-create-wl');
  const inputWlName = document.getElementById('wl-name-input');
  const inputWlSyms = document.getElementById('wl-syms-input');
  if (btnCreateWl && inputWlName && inputWlSyms) {
    btnCreateWl.addEventListener('click', async () => {
      const name = inputWlName.value.trim();
      const rawSyms = inputWlSyms.value.split(/[\s,]+/).filter(Boolean);
      if (!name) {
        alert('Please enter a list name.');
        return;
      }
      if (rawSyms.length === 0) {
        alert('Please enter at least one stock/ETF symbol (e.g. AAPL, NVDA, SPY).');
        return;
      }

      btnCreateWl.disabled = true;
      try {
        const res = await fetch('/api/watchlists', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name, symbols: rawSyms })
        });
        if (!res.ok) {
          const errData = await res.json();
          alert(errData.detail || 'Error adding list.');
          return;
        }
        inputWlName.value = '';
        inputWlSyms.value = '';
        loadWatchlists();
      } catch (e) {
        alert('Connection error: ' + e.message);
      } finally {
        btnCreateWl.disabled = false;
      }
    });
  }

  const page = (location.pathname.split('/')[1] || 'panel');
  if (page === 'panel') {
    loadStrategies();
    loadData();
  } else if (page === 'universes') {
    loadPresets();
    loadUniverses();
  } else if (page === 'lists') {
    loadWatchlists();
    loadRecentScans();
  } else if (page === 'settings') {
    loadMathSettings();
  }
  bindMathSettings();
  pollScanProgress();
  setInterval(pollScanProgress, 2000);
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
