// ==============================================================================
// CAPITOLSEEDER // WASHINGTON TERMINAL CLIENT CONTROLLER
// ==============================================================================

const API_BASE = '/api/v1';

let currentTrades = [];
let currentTab = 'trades';
let liveSocket = null;

document.addEventListener('DOMContentLoaded', () => {
  initNavTabs();
  initFilterControls();
  initDossierModal();
  initLiveWebSocket();
  
  // Initial data loading
  fetchTrades();
  fetchConflicts();
  fetchLeaderboard();
  fetchViolations();
  fetchClusters();
  runSimulation();
});

// Real-Time WebSocket Connection
function initLiveWebSocket() {
  const statusPill = document.getElementById('live-stream-status-pill');
  const statusText = document.getElementById('live-stream-status-text');

  const loc = window.location;
  const wsProtocol = loc.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${wsProtocol}//${loc.host}/api/v1/ws/live-trades`;

  function setStatus(online, text) {
    if (!statusPill || !statusText) return;
    statusText.textContent = text;
    if (online) {
      statusPill.style.borderColor = 'rgba(16, 185, 129, 0.4)';
      statusPill.style.background = 'rgba(16, 185, 129, 0.1)';
      const dot = statusPill.querySelector('.status-dot');
      if (dot) dot.style.background = 'var(--alpha-green)';
    } else {
      statusPill.style.borderColor = 'rgba(239, 68, 68, 0.4)';
      statusPill.style.background = 'rgba(239, 68, 68, 0.1)';
      const dot = statusPill.querySelector('.status-dot');
      if (dot) dot.style.background = 'var(--violation-red)';
    }
  }

  try {
    liveSocket = new WebSocket(wsUrl);

    liveSocket.onopen = () => {
      console.log('[CAPitAL] Live WebSocket stream connected.');
      setStatus(true, 'STREAM: LIVE');
    };

    liveSocket.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'NEW_TRADES' && Array.isArray(msg.trades)) {
          console.log(`[CAPitAL] Received ${msg.trades.length} new live disclosures.`);
          handleIncomingLiveTrades(msg.trades);
        }
      } catch (err) {
        console.warn('[CAPitAL] Failed to parse socket message:', err);
      }
    };

    liveSocket.onclose = () => {
      console.log('[CAPitAL] Live WebSocket stream disconnected. Retrying in 4s...');
      setStatus(false, 'STREAM: DISCONNECTED');
      setTimeout(initLiveWebSocket, 4000);
    };

    liveSocket.onerror = (err) => {
      console.warn('[CAPitAL] WebSocket encountered error:', err);
      liveSocket.close();
    };
  } catch (e) {
    console.error('[CAPitAL] Could not initialize WebSocket:', e);
    setTimeout(initLiveWebSocket, 5000);
  }
}

function handleIncomingLiveTrades(newTrades) {
  const tbody = document.getElementById('trades-table-body');
  if (!tbody) return;

  // Add to internal memory
  currentTrades = [...newTrades, ...currentTrades];

  // Update counter badge
  const countBadge = document.getElementById('trades-count-badge');
  if (countBadge) countBadge.textContent = `${currentTrades.length} Trades`;

  // Update Total Trades Stat Card
  const statTotal = document.getElementById('stat-total-trades');
  if (statTotal) {
    const prev = parseInt(statTotal.textContent.replace(/,/g, '')) || 0;
    statTotal.textContent = (prev + newTrades.length).toLocaleString();
  }

  // Prepend rows with visual animation
  newTrades.forEach(t => {
    const rowHtml = buildTradeRowHtml(t, true);
    tbody.insertAdjacentHTML('afterbegin', rowHtml);
  });

  // Update marquee ticker with latest
  renderTickerMarquee(currentTrades);
}


// Tab Switching
function initNavTabs() {
  const tabs = document.querySelectorAll('.nav-tab');
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');

      const view = tab.dataset.view;
      currentTab = view;

      document.getElementById('view-trades').style.display = view === 'trades' ? 'flex' : 'none';
      document.getElementById('view-conflicts').style.display = view === 'conflicts' ? 'flex' : 'none';
      document.getElementById('view-simulator').style.display = view === 'simulator' ? 'flex' : 'none';
      document.getElementById('view-leaderboard').style.display = view === 'leaderboard' ? 'flex' : 'none';
      document.getElementById('view-violations').style.display = view === 'violations' ? 'flex' : 'none';

      if (view === 'simulator') {
        runSimulation();
      }
    });
  });
}

// Filters
function initFilterControls() {
  const minScoreSlider = document.getElementById('filter-min-score');
  const minScoreLabel = document.getElementById('label-min-score');
  if (minScoreSlider && minScoreLabel) {
    minScoreSlider.addEventListener('input', (e) => {
      minScoreLabel.textContent = `${e.target.value}+`;
    });
  }

  const applyBtn = document.getElementById('btn-apply-filters');
  if (applyBtn) {
    applyBtn.addEventListener('click', () => {
      fetchTrades();
    });
  }

  const resetBtn = document.getElementById('btn-reset-filters');
  if (resetBtn) {
    resetBtn.addEventListener('click', () => {
      document.getElementById('filter-chamber').value = '';
      document.getElementById('filter-party').value = '';
      document.getElementById('filter-owner').value = '';
      document.getElementById('filter-ticker').value = '';
      document.getElementById('filter-violations-only').value = '';
      document.getElementById('filter-min-score').value = 0;
      minScoreLabel.textContent = '0+';
      fetchTrades();
    });
  }

  const refreshBtn = document.getElementById('btn-refresh-trades');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', () => fetchTrades());
  }

  const simBtn = document.getElementById('btn-run-sim');
  if (simBtn) {
    simBtn.addEventListener('click', () => runSimulation());
  }

  const syncBtn = document.getElementById('btn-sync-feed');
  if (syncBtn) {
    syncBtn.addEventListener('click', async () => {
      const originalText = syncBtn.textContent;
      syncBtn.disabled = true;
      syncBtn.textContent = '⏳ SYNCING...';
      try {
        const res = await fetch(`${API_BASE}/trades/sync`, { method: 'POST' });
        const result = await res.json();
        console.log('[CAPitAL] Live sync response:', result);
        // Refresh trades and stat counters
        await fetchTrades();
        await fetchConflicts();
        await fetchViolations();
        await fetchClusters();
      } catch (err) {
        console.error('[CAPitAL] Live sync failed:', err);
      } finally {
        syncBtn.disabled = false;
        syncBtn.textContent = originalText;
      }
    });
  }
}

// 1. Fetch Trades
async function fetchTrades() {
  const chamber = document.getElementById('filter-chamber').value;
  const party = document.getElementById('filter-party').value;
  const owner = document.getElementById('filter-owner').value;
  const ticker = document.getElementById('filter-ticker').value;
  const isViolation = document.getElementById('filter-violations-only').value;
  const minScore = document.getElementById('filter-min-score').value;

  const params = new URLSearchParams({ page_size: '50' });
  if (chamber) params.append('chamber', chamber);
  if (party) params.append('party', party);
  if (owner) params.append('owner_type', owner);
  if (ticker) params.append('ticker', ticker);
  if (isViolation) params.append('is_violation', isViolation);
  if (minScore > 0) params.append('min_score', minScore);

  try {
    const res = await fetch(`${API_BASE}/trades?${params.toString()}`);
    const data = await res.json();
    currentTrades = data.items || [];
    renderTradesTable(currentTrades);
    renderTickerMarquee(currentTrades);
    updateStats();
  } catch (err) {
    console.error('Failed to fetch trades:', err);
  }
}

function buildTradeRowHtml(t, isNew = false) {
  const partyClass = t.party === 'Democrat' ? 'chip-democrat' : (t.party === 'Republican' ? 'chip-republican' : 'chip-independent');
  const scoreVal = t.alpha_score ? (t.alpha_score.composite_alpha_score || 50.0) : 50.0;
  const scoreClass = scoreVal >= 80 ? 'chip-alpha' : (scoreVal >= 60 ? 'chip-conflict' : '');

  let contractChip = '<span style="color: var(--text-muted); font-size: 11px;">None</span>';
  if (t.contracts && t.contracts.length > 0) {
    const c = t.contracts[0];
    contractChip = `<span class="chip chip-conflict" title="${c.agency_name} $${c.award_amount.toLocaleString()}">${c.agency_name.split(' ')[0]} Match</span>`;
  }

  const lagColor = t.is_stock_act_violation ? 'var(--violation-red)' : 'var(--text-muted)';
  const lagBadge = t.is_stock_act_violation ? `<span class="chip chip-violation">${t.filing_lag_days}d VIOLATION</span>` : `<span style="color: ${lagColor}; font-family: var(--font-mono);">${t.filing_lag_days}d</span>`;
  const rowClass = isNew ? 'class="new-live-row"' : '';

  return `
    <tr ${rowClass}>
      <td style="font-family: var(--font-mono); font-size: 12px;">${t.disclosure_date}</td>
      <td>
        <div style="font-weight: 600; cursor: pointer; color: #38bdf8;" onclick="openDossier('${t.bioguide_id}')">
          ${t.politician_name || 'Member'}
        </div>
        <span class="chip ${partyClass}" style="margin-top: 2px;">${t.party || 'I'}-${t.state || 'US'}</span>
      </td>
      <td>
        <span class="ticker-badge">$${t.ticker}</span>
        <div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">${t.asset_type}</div>
      </td>
      <td style="font-family: var(--font-mono);">${t.transaction_type}</td>
      <td style="font-family: var(--font-mono); font-weight: 500;">${t.amount_range_str}</td>
      <td>
        <span style="font-size: 12px; color: ${t.owner_type === 'Spouse' ? 'var(--alpha-gold)' : 'var(--text-secondary)'}; font-weight: ${t.owner_type === 'Spouse' ? '700' : '400'};">
          ${t.owner_type}
        </span>
      </td>
      <td>
        <span class="chip ${scoreClass}">${scoreVal}/100</span>
      </td>
      <td>${contractChip}</td>
      <td>${lagBadge}</td>
      <td>
        <div style="display: flex; gap: 4px;">
          <button class="btn-terminal" style="padding: 3px 6px; font-size: 11px;" onclick='openOcrModal(${JSON.stringify(t).replace(/'/g, "&#39;")})'>
            OCR
          </button>
          <a href="${t.filing_id ? `https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/2024/${t.filing_id}.pdf` : '#'}" target="_blank" class="btn-terminal" style="padding: 3px 6px; font-size: 11px; text-decoration: none;">
            PDF
          </a>
        </div>
      </td>
    </tr>
  `;
}

function renderTradesTable(trades) {
  const tbody = document.getElementById('trades-table-body');
  const countBadge = document.getElementById('trades-count-badge');
  if (countBadge) countBadge.textContent = `${trades.length} Trades`;
  if (!tbody) return;

  if (trades.length === 0) {
    tbody.innerHTML = `<tr><td colspan="10" style="text-align: center; color: var(--text-muted); padding: 40px;">No congressional transactions match current filters.</td></tr>`;
    return;
  }

  tbody.innerHTML = trades.map(t => buildTradeRowHtml(t)).join('');
}


// 2. Marquee Ticker
function renderTickerMarquee(trades) {
  const container = document.getElementById('ticker-marquee-inner');
  if (!container || !trades.length) return;

  const itemsHtml = trades.slice(0, 15).map(t => {
    const partyChip = t.party === 'Democrat' ? 'chip-democrat' : 'chip-republican';
    return `
      <div class="ticker-item" onclick='openOcrModal(${JSON.stringify(t).replace(/'/g, "&#39;")})'>
        <span class="chip ${partyChip}">${t.party ? t.party[0] : 'I'}</span>
        <strong>${t.politician_name ? t.politician_name.split(' ').pop() : 'Member'}</strong>
        <span style="color: var(--alpha-gold); font-weight: 700;">$${t.ticker}</span>
        <span style="color: var(--text-muted);">${t.amount_range_str.split('-')[0].trim()}</span>
        <span class="chip chip-alpha">${t.alpha_score ? t.alpha_score.composite_alpha_score : 50}</span>
      </div>
    `;
  }).join('');

  // Duplicate for seamless loop
  container.innerHTML = itemsHtml + itemsHtml;
}

// 3. Conflict Matrix
async function fetchConflicts() {
  try {
    const res = await fetch(`${API_BASE}/conflicts/live?min_conflict_score=75`);
    const conflicts = await res.json();
    const container = document.getElementById('conflict-matrix');
    if (!container) return;

    if (!conflicts.length) {
      container.innerHTML = `<div style="color: var(--text-muted); grid-column: 1 / -1; padding: 30px; text-align: center;">No active high-conflict trades identified.</div>`;
      return;
    }

    container.innerHTML = conflicts.map(c => {
      const t = c.trade;
      const partyClass = t.party === 'Democrat' ? 'chip-democrat' : 'chip-republican';
      return `
        <div class="matrix-card">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px;">
            <div>
              <span class="ticker-badge" style="font-size: 15px;">$${t.ticker}</span>
              <span style="font-size: 12px; color: var(--text-secondary); margin-left: 6px;">${t.company_name}</span>
            </div>
            <span class="chip chip-conflict">${c.conflict_score}/100</span>
          </div>

          <div style="margin-bottom: 8px; font-size: 12px;">
            <strong>${t.politician_name}</strong> <span class="chip ${partyClass}">${t.party}-${t.state}</span>
          </div>

          <div style="font-size: 12px; color: #a78bfa; margin-bottom: 6px; font-family: var(--font-mono);">
            🏛️ ${c.committee_name} (${c.committee_role})
          </div>

          <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 10px; line-height: 1.4;">
            ${c.rationale}
          </div>

          ${c.contracts && c.contracts.length > 0 ? `
            <div style="background: rgba(139, 92, 246, 0.1); border: 1px solid rgba(139, 92, 246, 0.3); border-radius: 4px; padding: 8px; font-size: 11px;">
              <strong style="color: #c084fc;">DoD / Federal Award:</strong> $${c.contracts[0].award_amount.toLocaleString()}<br>
              <span style="color: var(--text-muted);">${c.contracts[0].days_between_trade_and_contract} days relative to trade</span>
            </div>
          ` : ''}
        </div>
      `;
    }).join('');

    const statConf = document.getElementById('stat-high-conflicts');
    if (statConf) statConf.textContent = conflicts.length;
  } catch (err) {
    console.error('Failed to fetch conflicts:', err);
  }
}

// 4. Leaderboard
async function fetchLeaderboard() {
  try {
    const res = await fetch(`${API_BASE}/politicians/leaderboard?limit=15`);
    const leaderboard = await res.json();
    const tbody = document.getElementById('leaderboard-table-body');
    if (!tbody) return;

    tbody.innerHTML = leaderboard.map((p, idx) => {
      const partyClass = p.party === 'Democrat' ? 'chip-democrat' : (p.party === 'Republican' ? 'chip-republican' : 'chip-independent');
      return `
        <tr>
          <td style="font-family: var(--font-mono); font-weight: 700; color: ${idx === 0 ? 'var(--alpha-gold)' : 'var(--text-muted)'};">
            #${idx + 1}
          </td>
          <td>
            <div style="font-weight: 600; cursor: pointer; color: #38bdf8;" onclick="openDossier('${p.bioguide_id}')">
              ${p.first_name} ${p.last_name}
            </div>
            <div style="font-size: 11px; color: var(--text-muted);">${p.leadership_title || 'Member of Congress'}</div>
          </td>
          <td style="font-family: var(--font-mono);">${p.chamber}</td>
          <td><span class="chip ${partyClass}">${p.party}-${p.state}</span></td>
          <td style="font-size: 12px; color: var(--text-secondary);">${p.leadership_title || 'Committee Member'}</td>
          <td style="font-family: var(--font-mono); font-weight: 700; color: var(--alpha-green);">${p.win_rate}%</td>
          <td style="font-family: var(--font-mono);">$${(p.total_volume / 1000000).toFixed(1)}M</td>
          <td><span class="chip chip-alpha">${p.alpha_score}/100</span></td>
          <td>
            <button class="btn-terminal" onclick="openDossier('${p.bioguide_id}')">DOSSIER</button>
          </td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    console.error('Failed to fetch leaderboard:', err);
  }
}

// 5. Violations
async function fetchViolations() {
  try {
    const res = await fetch(`${API_BASE}/violations`);
    const data = await res.json();
    const tbody = document.getElementById('violations-table-body');
    if (!tbody) return;

    const violations = data.violations || [];
    const statViol = document.getElementById('stat-violations');
    if (statViol) statViol.textContent = data.total_violations_count;
    const statFines = document.getElementById('stat-fines');
    if (statFines) statFines.textContent = `Est. Fines: $${data.total_estimated_fines.toLocaleString()}`;

    if (!violations.length) {
      tbody.innerHTML = `<tr><td colspan="11" style="text-align: center; color: var(--text-muted); padding: 30px;">Zero STOCK Act violations detected. All filings compliant.</td></tr>`;
      return;
    }

    tbody.innerHTML = violations.map(v => {
      const partyClass = v.party === 'Democrat' ? 'chip-democrat' : 'chip-republican';
      return `
        <tr>
          <td><strong>${v.politician_name}</strong></td>
          <td style="font-family: var(--font-mono);">${v.chamber}</td>
          <td><span class="chip ${partyClass}">${v.party}</span></td>
          <td><span class="ticker-badge">$${v.ticker}</span></td>
          <td style="font-family: var(--font-mono); font-size: 12px;">${v.transaction_date}</td>
          <td style="font-family: var(--font-mono); font-size: 12px;">${v.disclosure_date}</td>
          <td style="font-family: var(--font-mono); font-weight: 700; color: var(--violation-red);">${v.filing_lag_days}d</td>
          <td style="font-family: var(--font-mono); color: var(--violation-red); font-weight: 700;">+${v.days_overdue}d</td>
          <td><span class="chip chip-violation">${v.violation_severity}</span></td>
          <td style="font-family: var(--font-mono); font-weight: 700; color: var(--alpha-gold);">$${v.estimated_statutory_fine}</td>
          <td>
            <a href="${v.doc_url || '#'}" target="_blank" class="btn-terminal" style="text-decoration: none; font-size: 11px;">VIEW</a>
          </td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    console.error('Failed to fetch violations:', err);
  }
}

// 6. Clusters
async function fetchClusters() {
  try {
    const res = await fetch(`${API_BASE}/bipartisan-clusters?window_days=14`);
    const clusters = await res.json();
    const statClust = document.getElementById('stat-clusters');
    if (statClust) statClust.textContent = clusters.length;
  } catch (err) {
    console.error('Failed to fetch clusters:', err);
  }
}

// 7. Simulation Backtest
async function runSimulation() {
  const memberSelect = document.getElementById('sim-member-select');
  const bioguideId = memberSelect ? memberSelect.value : '';

  const params = new URLSearchParams({ initial_capital: '100000' });
  if (bioguideId) params.append('bioguide_id', bioguideId);

  try {
    const res = await fetch(`${API_BASE}/simulate/shadow-portfolio?${params.toString()}`);
    const data = await res.json();

    const statRet = document.getElementById('sim-stat-return');
    if (statRet) statRet.textContent = `+${data.metrics.cumulative_return}%`;

    const statAlpha = document.getElementById('sim-stat-alpha');
    if (statAlpha) statAlpha.textContent = `+${data.metrics.cumulative_alpha}%`;

    const statWin = document.getElementById('sim-stat-winrate');
    if (statWin) statWin.textContent = `${data.metrics.win_rate}%`;

    const statSharpe = document.getElementById('sim-stat-sharpe');
    if (statSharpe) statSharpe.textContent = data.metrics.sharpe_ratio;

    renderPortfolioChart(data.portfolio_curve, data.benchmark_curve);
  } catch (err) {
    console.error('Failed to run simulation:', err);
  }
}

// 8. Dossier Modal
async function openDossier(bioguideId) {
  try {
    const res = await fetch(`${API_BASE}/politicians/${bioguideId}`);
    const dossier = await res.json();
    const pol = dossier.politician;

    const modal = document.getElementById('dossier-modal');
    const title = document.getElementById('dossier-modal-title');
    const content = document.getElementById('dossier-modal-content');
    if (!modal || !content) return;

    if (title) title.textContent = `CONGRESSIONAL DOSSIER: ${pol.first_name} ${pol.last_name}`;

    const partyClass = pol.party === 'Democrat' ? 'chip-democrat' : 'chip-republican';

    content.innerHTML = `
      <div style="display: flex; gap: 20px; margin-bottom: 20px;">
        <div style="width: 80px; height: 80px; background: #1e293b; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 28px; font-weight: 700; color: var(--alpha-gold); border: 2px solid var(--border-color);">
          ${pol.first_name[0]}${pol.last_name[0]}
        </div>
        <div>
          <h2 style="font-size: 20px; font-weight: 700; margin-bottom: 4px;">${pol.first_name} ${pol.last_name}</h2>
          <div style="display: flex; gap: 8px; align-items: center; margin-bottom: 6px;">
            <span class="chip ${partyClass}">${pol.party}-${pol.state}</span>
            <span style="font-size: 12px; color: var(--text-secondary); font-family: var(--font-mono);">${pol.chamber}</span>
            <span style="font-size: 12px; color: var(--alpha-gold); font-family: var(--font-mono);">${pol.leadership_title || ''}</span>
          </div>
          <div style="font-size: 12px; color: var(--text-muted); font-family: var(--font-mono);">
            90d Win Rate: <strong style="color: var(--alpha-green);">${pol.win_rate}%</strong> • 
            Total Traded: <strong style="color: var(--text-primary);">$${(pol.total_volume / 1000000).toFixed(1)}M</strong> • 
            Composite Alpha: <strong style="color: var(--alpha-gold);">${pol.alpha_score}/100</strong>
          </div>
        </div>
      </div>

      <div style="margin-bottom: 16px;">
        <h4 style="font-family: var(--font-mono); font-size: 12px; color: var(--text-secondary); margin-bottom: 8px; text-transform: uppercase;">
          Committee Assignments & Jurisdictions
        </h4>
        <div style="display: flex; flex-direction: column; gap: 6px;">
          ${dossier.committees.map(c => `
            <div style="background: #080c14; padding: 10px; border-radius: 4px; border: 1px solid var(--border-color); font-size: 12px;">
              <div style="font-weight: 600; color: #a78bfa;">${c.committee_name} (${c.role})</div>
              <div style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">
                Jurisdiction Keywords: ${c.jurisdiction_keywords.join(', ')}
              </div>
            </div>
          `).join('')}
        </div>
      </div>

      <div>
        <h4 style="font-family: var(--font-mono); font-size: 12px; color: var(--text-secondary); margin-bottom: 8px; text-transform: uppercase;">
          Recent Disclosed Trades
        </h4>
        <div class="table-responsive" style="max-height: 250px;">
          <table class="terminal-table" style="font-size: 11px;">
            <thead>
              <tr>
                <th>Date</th>
                <th>Ticker</th>
                <th>Asset</th>
                <th>Type</th>
                <th>Amount</th>
                <th>Owner</th>
                <th>Alpha</th>
              </tr>
            </thead>
            <tbody>
              ${dossier.recent_trades.map(t => `
                <tr>
                  <td>${t.disclosure_date}</td>
                  <td><span class="ticker-badge">$${t.ticker}</span></td>
                  <td>${t.asset_type}</td>
                  <td>${t.transaction_type}</td>
                  <td>${t.amount_range_str}</td>
                  <td style="color: ${t.owner_type === 'Spouse' ? 'var(--alpha-gold)' : 'inherit'}; font-weight: ${t.owner_type === 'Spouse' ? 'bold' : 'normal'};">${t.owner_type}</td>
                  <td><span class="chip chip-alpha">${t.alpha_score ? t.alpha_score.composite_alpha_score : '--'}</span></td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      </div>
    `;

    modal.classList.add('open');
  } catch (err) {
    console.error('Failed to open dossier:', err);
  }
}

function initDossierModal() {
  const closeBtn = document.getElementById('btn-close-dossier-modal');
  const modal = document.getElementById('dossier-modal');
  if (closeBtn && modal) {
    closeBtn.addEventListener('click', () => modal.classList.remove('open'));
    modal.addEventListener('click', (e) => {
      if (e.target === modal) modal.classList.remove('open');
    });
  }
}

function updateStats() {
  const statTrades = document.getElementById('stat-total-trades');
  if (statTrades) statTrades.textContent = currentTrades.length;
}
