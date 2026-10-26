// INseeder Web Terminal Client Logic
document.addEventListener("DOMContentLoaded", () => {
    // State
    let allTrades = [];
    let allSignals = [];
    let currentFilter = "all";
    let currentSignalFilter = "all";
    let searchTerm = "";

    // Major US Equity Indices Constituents
    const DOW30 = new Set([
        "AAPL", "AMGN", "AMZN", "AXP", "BA", "CAT", "CRM", "CSCO", "CVX", "DIS",
        "DOW", "GS", "HD", "HON", "IBM", "INTC", "JNJ", "JPM", "KO", "MCD",
        "MMM", "MRK", "MSFT", "NKE", "NVDA", "PG", "SHW", "TRV", "UNH", "V", "VZ", "WMT"
    ]);

    const NASDAQ100 = new Set([
        "AAPL", "ABNB", "ADBE", "ADI", "ADP", "ADSK", "AEP", "AMAT", "AMD", "AMGN",
        "AMZN", "ANSS", "APP", "ASML", "AVGO", "AXON", "BIIB", "BKNG", "BKR", "CCEP",
        "CDNS", "CEG", "CHTR", "CMCSA", "COST", "CPRT", "CRWD", "CSCO", "CSGP", "CSX",
        "CTAS", "CTSH", "DASH", "DDOG", "DLTR", "DXCM", "EA", "EXC", "FANG", "FAST",
        "FTNT", "GEHC", "GFS", "GILD", "GOOG", "GOOGL", "HON", "IDXX", "INTC", "INTU",
        "ISRG", "KDP", "KHC", "KLAC", "LIN", "LRCX", "LULU", "MAR", "MCHP", "MDLZ",
        "MELI", "META", "MNST", "MRNA", "MRVL", "MSFT", "MSTR", "MU", "NFLX", "NVDA",
        "NXPI", "ODFL", "ON", "ORLY", "PANW", "PAYX", "PCAR", "PDD", "PEP", "PLTR",
        "PYPL", "QCOM", "REGN", "ROP", "ROST", "SBUX", "SNPS", "TEAM", "TMUS", "TSLA",
        "TTD", "TTWO", "TXN", "VRSK", "VRTX", "WBD", "WDAY", "XEL", "ZS"
    ]);

    const SP500 = new Set([
        ...Array.from(DOW30),
        ...Array.from(NASDAQ100),
        "ABT", "ACN", "AFL", "AIG", "ALL", "AME", "AMP", "AMT", "AON", "APD",
        "APH", "ARE", "ATO", "AVB", "AVY", "AWK", "BAC", "BALL", "BAX", "BBWI",
        "BBY", "BDX", "BEN", "BF.B", "BG", "BLK", "BMY", "BR", "BRK.B", "BSX",
        "BWA", "BX", "C", "CAG", "CAH", "CARR", "CB", "CBOE", "CBRE", "CCI",
        "CCL", "CDW", "CF", "CFG", "CHD", "CHRW", "CI", "CINF", "CL", "CLX",
        "CMA", "CME", "CMG", "CMS", "CNC", "CNP", "COF", "COO", "COP", "COR",
        "CPB", "CPT", "CRL", "CTRA", "CTVA", "CVS", "CZR", "D", "DAL", "DAY",
        "DE", "DFS", "DG", "DGX", "DHI", "DHR", "DLR", "DOV", "DPZ", "DRI",
        "DTE", "DUK", "DVA", "DVN", "ECL", "ED", "EFX", "EG", "EIX", "EL",
        "ELV", "EMN", "EMR", "EOG", "EPAM", "EQIX", "EQR", "EQT", "ES", "ESS",
        "ETN", "ETR", "EVRG", "EW", "EXPD", "EXPE", "EXR", "F", "FCX", "FDS",
        "FE", "FFIV", "FI", "FICO", "FIS", "FITB", "FLT", "FMC", "FOX", "FOXA",
        "FRT", "FSLR", "FTV", "GD", "GE", "GEN", "GIR", "GL", "GLW", "GM",
        "GNRC", "GPC", "GPN", "GRMN", "GWW", "HAL", "HBAN", "HCA", "HES", "HIG",
        "HII", "HLT", "HOLX", "HPE", "HPQ", "HRL", "HSIC", "HST", "HSY", "HUBB",
        "HUM", "HWM", "ICE", "IEX", "IFF", "INCY", "INVH", "IP", "IPG", "IQV",
        "IR", "IRM", "IT", "ITW", "IVZ", "J", "JBHT", "JBL", "JKHY", "JNJ",
        "JNPR", "K", "KEY", "KEYS", "KIM", "KKR", "KMB", "KMI", "KMX", "KR",
        "KVUE", "L", "LDOS", "LEN", "LH", "LHX", "LKQ", "LLY", "LMT", "LNT",
        "LOW", "LRCX", "LUV", "LVS", "LW", "LYB", "LYV", "MA", "MAA", "MAS",
        "MCO", "MCK", "MDT", "MET", "MGM", "MHK", "MKC", "MLM", "MMC", "MO",
        "MOH", "MOS", "MPC", "MPWR", "MRK", "MS", "MSCI", "MSI", "MTB", "MTD",
        "MTCH", "NDAQ", "NDSN", "NEE", "NEM", "NI", "NOC", "NOW", "NRG", "NSC",
        "NTAP", "NTRS", "NUE", "NVST", "NWL", "NWS", "NWSA", "O", "OKE", "OMC",
        "ORCL", "OTIS", "OXY", "PARA", "PAYC", "PCG", "PEG", "PFE", "PFG", "PGR",
        "PH", "PHM", "PKG", "PKI", "PLD", "PNC", "PNR", "PNW", "PODD", "POOL",
        "PPG", "PPL", "PRU", "PSA", "PTC", "PWR", "PXD", "QRVO", "RCL", "RE",
        "REG", "RF", "RHI", "RJF", "RL", "RMD", "ROK", "ROL", "RSG", "RTX",
        "RVTY", "SBAC", "SBNY", "SCHW", "SEDG", "SEE", "SHW", "SJM", "SLB", "SNA",
        "SO", "SPG", "SPGI", "SRE", "STE", "STLD", "STT", "STX", "STZ", "SWK",
        "SWKS", "SYF", "SYK", "SYY", "T", "TAP", "TDG", "TDY", "TECH", "TEL",
        "TER", "TFC", "TFX", "TGT", "TJX", "TMO", "TPR", "TRGP", "TRMB", "TROW",
        "TRV", "TSCO", "TSN", "TT", "TXT", "TYL", "UAL", "UDR", "UHS", "ULTA",
        "UNP", "UPS", "URI", "USB", "VFC", "VICI", "VLO", "VMC", "VNO", "VRSN",
        "VTR", "VTRS", "VZ", "WAB", "WAT", "WDC", "WEC", "WELL", "WFC", "WHR",
        "WM", "WMB", "WRB", "WRK", "WST", "WTW", "WY", "WYNN", "XEL", "XOM",
        "XYL", "YUM", "ZBH", "ZBRA", "ZION", "ZTS"
    ]);

    // Hyperliquid Markets Cache
    let hyperliquidMarkets = [];
    let hyperliquidSymbols = new Set();
    let hlCurrentFilter = "all";

    function getIndexBadge(ticker) {
        if (!ticker) return "";
        const clean = ticker.trim().toUpperCase();
        let badges = [];

        if (hyperliquidSymbols.has(clean)) {
            badges.push(`<span class="index-tag index-hl" title="Listed on Hyperliquid L1">⚡ HYPERLIQUID</span>`);
        }
        if (DOW30.has(clean)) {
            badges.push(`<span class="index-tag index-dow30" title="Dow Jones Industrial Average (Dow 30)">DOW 30</span>`);
        }
        if (NASDAQ100.has(clean)) {
            badges.push(`<span class="index-tag index-nasdaq100" title="Nasdaq 100 Index">NDX 100</span>`);
        } else if (SP500.has(clean)) {
            badges.push(`<span class="index-tag index-sp500" title="S&P 500 Index">S&P 500</span>`);
        }
        return badges.join("");
    }

    // DOM Elements
    const tabButtons = document.querySelectorAll(".tab-btn");
    const tabContents = document.querySelectorAll(".tab-content");
    const tradesTbody = document.getElementById("trades-tbody");
    const signalsContainer = document.getElementById("signals-container");
    const rulesContainer = document.getElementById("rules-container");
    const positionsTbody = document.getElementById("positions-tbody");
    const ordersTbody = document.getElementById("orders-tbody");
    const hlTbody = document.getElementById("hl-tbody");

    // Stats Elements
    const statTotalTrades = document.getElementById("stat-total-trades");
    const statTotalSignals = document.getElementById("stat-total-signals");
    const statPortfolioValue = document.getElementById("stat-portfolio-value");
    const statUnrealizedPnl = document.getElementById("stat-unrealized-pnl");
    const badgeStreamCount = document.getElementById("badge-stream-count");
    const badgeSignalCount = document.getElementById("badge-signal-count");

    // Portfolio Elements
    const portfolioTotalEquity = document.getElementById("portfolio-total-equity");
    const portfolioCash = document.getElementById("portfolio-cash");
    const portfolioPositionsVal = document.getElementById("portfolio-positions-val");
    const portfolioPnl = document.getElementById("portfolio-pnl");

    // Modal Elements
    const orderModal = document.getElementById("order-modal");
    const btnManualOrder = document.getElementById("btn-manual-order");
    const btnCloseModal = document.getElementById("btn-close-modal");
    const orderForm = document.getElementById("order-form");
    const orderSymbolInput = document.getElementById("order-symbol");
    const orderQtyInput = document.getElementById("order-qty");
    const orderPriceInput = document.getElementById("order-price");
    const orderSideSelect = document.getElementById("order-side");

    // Rule Form
    const ruleForm = document.getElementById("rule-form");

    // Filter Elements
    const searchInput = document.getElementById("stream-search-ticker");
    const filterPills = document.querySelectorAll(".pill");

    // 1. Tab Switching
    tabButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            const targetTab = btn.getAttribute("data-tab");
            tabButtons.forEach(b => b.classList.remove("active"));
            tabContents.forEach(c => c.classList.remove("active"));

            btn.classList.add("active");
            document.getElementById(targetTab)?.classList.add("active");

            if (targetTab === "tab-portfolio") {
                fetchPortfolio();
            } else if (targetTab === "tab-rules") {
                fetchRules();
            } else if (targetTab === "tab-signals") {
                fetchSignals();
            } else if (targetTab === "tab-hyperliquid") {
                fetchHyperliquidMarkets();
            }
        });
    });

    // 2. Filters & Search
    filterPills.forEach(pill => {
        pill.addEventListener("click", () => {
            filterPills.forEach(p => p.classList.remove("active"));
            pill.classList.add("active");
            currentFilter = pill.getAttribute("data-filter");
            renderTrades();
        });
    });

    searchInput?.addEventListener("input", (e) => {
        searchTerm = e.target.value.trim().toUpperCase();
        renderTrades();
    });

    // Security helpers for HTML and URL sanitization
    function escapeHtml(str) {
        if (str === null || str === undefined) return "";
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function safeUrl(url) {
        if (!url || typeof url !== "string") return "#";
        const trimmed = url.trim();
        if (trimmed.startsWith("https://") || trimmed.startsWith("http://")) {
            return escapeHtml(trimmed);
        }
        return "#";
    }

    // 3. Render Trades Table
    function renderTrades() {
        if (!tradesTbody) return;

        let filtered = allTrades.filter(trade => {
            const ticker = (trade.ticker || "").toUpperCase();

            // Search filter
            if (searchTerm && !ticker.includes(searchTerm)) {
                return false;
            }

            // Index & Platform filters
            if (currentFilter === "hyperliquid" && !hyperliquidSymbols.has(ticker)) return false;
            if (currentFilter === "sp500" && !SP500.has(ticker)) return false;
            if (currentFilter === "nasdaq100" && !NASDAQ100.has(ticker)) return false;
            if (currentFilter === "dow30" && !DOW30.has(ticker)) return false;

            // Pill filters
            if (currentFilter === "P" && trade.transaction_code !== "P") return false;
            if (currentFilter === "S" && trade.transaction_code !== "S") return false;
            if (currentFilter === "large" && (trade.value || 0) < 100000) return false;
            if (currentFilter === "exec") {
                const title = (trade.insider_title || "").toUpperCase();
                if (!title.includes("CEO") && !title.includes("CFO")) return false;
            }
            return true;
        });

        tradesTbody.innerHTML = filtered.map(t => {
            const isPurchase = t.transaction_code === "P";
            const badgeClass = isPurchase ? "badge-purchase" : "badge-sale";
            const badgeText = isPurchase ? "BUY (P)" : `SELL (${escapeHtml(t.transaction_code)})`;
            const planBadge = t.is_10b5_1 
                ? '<span class="chip">10b5-1 Plan</span>' 
                : '<span class="chip chip-highlight">Discretionary</span>';
            const indexBadge = getIndexBadge(t.ticker);

            return `
                <tr>
                    <td class="mono-number" style="color: var(--text-muted); font-size: 11px;">
                        ${escapeHtml(t.filing_date ? t.filing_date.substring(0, 10) : "-")}
                    </td>
                    <td>
                        <div style="display: flex; align-items: center; gap: 4px; flex-wrap: wrap;">
                            <span class="ticker-badge">${escapeHtml(t.ticker)}</span>
                            ${indexBadge}
                        </div>
                        <div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">
                            ${escapeHtml(t.company_name || "")}
                        </div>
                    </td>
                    <td>
                        <strong>${escapeHtml(t.insider_name)}</strong>
                        <div style="font-size: 11px; color: var(--text-secondary);">
                            ${escapeHtml(t.insider_title || "Executive")}
                        </div>
                    </td>
                    <td><span class="action-badge ${badgeClass}">${badgeText}</span></td>
                    <td class="mono-number">${Number(t.shares || 0).toLocaleString()}</td>
                    <td class="mono-number">$${Number(t.price || 0).toFixed(2)}</td>
                    <td class="mono-number" style="font-weight: 700; color: ${isPurchase ? 'var(--accent-emerald)' : 'var(--accent-red)'};">
                        $${Number(t.value || 0).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}
                    </td>
                    <td class="mono-number" style="color: var(--text-secondary);">
                        ${Number(t.shares_owned_after || 0).toLocaleString()}
                    </td>
                    <td>${planBadge}</td>
                    <td>
                        <a href="${safeUrl(t.sec_url)}" target="_blank" rel="noopener noreferrer" class="btn btn-outline btn-sm" style="text-decoration: none;">
                            SEC Form 4
                        </a>
                    </td>
                </tr>
            `;
        }).join("");
    }

    // 4. Render Signals Grid
    function renderSignals(signals = allSignals) {
        if (!signalsContainer) return;

        let filtered = (signals || []).filter(s => {
            const ticker = (s.ticker || "").toUpperCase();
            if (currentSignalFilter === "hyperliquid" && !hyperliquidSymbols.has(ticker)) return false;
            if (currentSignalFilter === "sp500" && !SP500.has(ticker)) return false;
            if (currentSignalFilter === "nasdaq100" && !NASDAQ100.has(ticker)) return false;
            if (currentSignalFilter === "dow30" && !DOW30.has(ticker)) return false;
            if (currentSignalFilter === "cluster" && (s.cluster_count || 1) < 2) return false;
            return true;
        });

        if (filtered.length === 0) {
            signalsContainer.innerHTML = `
                <div style="grid-column: 1/-1; text-align: center; padding: 48px; color: var(--text-muted);">
                    No signals found matching the selected filter.
                </div>
            `;
            return;
        }

        signalsContainer.innerHTML = filtered.map(s => {
            const score = s.score || 0;
            const breakdown = typeof s.details_json === "string" ? JSON.parse(s.details_json || "{}") : (s.details_json || {});
            const indexBadge = getIndexBadge(s.ticker);
            
            return `
                <div class="signal-card">
                    <div class="signal-card-header">
                        <div>
                            <div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">
                                <span class="ticker-badge" style="font-size: 16px; padding: 4px 10px;">${escapeHtml(s.ticker)}</span>
                                ${indexBadge}
                            </div>
                            <div style="font-size: 12px; color: var(--text-secondary); margin-top: 4px;">
                                ${escapeHtml(s.company_name || "")}
                            </div>
                        </div>
                        <div class="signal-score-badge">
                            <span class="signal-score-num">${score}</span>
                            <span class="signal-score-total">/100</span>
                        </div>
                    </div>

                    <div style="font-size: 13px;">
                        <strong>${escapeHtml(s.insider_name)}</strong> &bull; <span style="color: var(--text-secondary);">${escapeHtml(s.insider_title || "Executive")}</span>
                    </div>

                    <div class="breakdown-chips">
                        ${breakdown.role ? `<span class="chip chip-highlight">${escapeHtml(breakdown.role)} (+${breakdown.role_points} pts)</span>` : ""}
                        ${breakdown.value_points ? `<span class="chip chip-highlight">$ Volume (+${breakdown.value_points} pts)</span>` : ""}
                        ${breakdown.increase_points ? `<span class="chip chip-highlight">Position +${breakdown.increase_points} pts</span>` : ""}
                        ${s.cluster_count >= 2 ? `<span class="chip" style="background: rgba(168, 85, 247, 0.15); border-color: var(--accent-purple); color: var(--accent-purple); font-weight: 600;">🔥 Cluster: ${s.cluster_count} Insiders</span>` : ""}
                        ${breakdown.discretionary_points ? `<span class="chip">Discretionary Buy</span>` : ""}
                    </div>

                    <div style="display: flex; justify-content: space-between; align-items: baseline; padding: 10px; background: var(--bg-secondary); border-radius: var(--radius-sm);">
                        <span style="font-size: 12px; color: var(--text-muted);">Trade Value</span>
                        <span class="mono-number" style="font-size: 16px; font-weight: 700; color: var(--accent-emerald);">
                            $${Number(s.value || 0).toLocaleString()}
                        </span>
                    </div>

                    <div style="display: flex; gap: 8px;">
                        <button class="btn btn-primary btn-sm btn-block btn-copy-trade" 
                            data-symbol="${escapeHtml(s.ticker)}" 
                            data-price="${s.price || 100}" 
                            data-signal-id="${s.id}">
                            Copy Trade (Simulate)
                        </button>
                        <a href="${safeUrl(s.sec_url)}" target="_blank" rel="noopener noreferrer" class="btn btn-outline btn-sm" style="text-decoration: none;">
                            Filing
                        </a>
                    </div>
                </div>
            `;
        }).join("");

        // Attach copy trade click handlers
        document.querySelectorAll(".btn-copy-trade").forEach(btn => {
            btn.addEventListener("click", () => {
                const symbol = btn.getAttribute("data-symbol");
                const price = parseFloat(btn.getAttribute("data-price")) || 100;
                const signalId = btn.getAttribute("data-signal-id");
                
                openOrderModal(symbol, price, signalId);
            });
        });
    }

    // 5. Fetch API Endpoints
    async function fetchTrades() {
        try {
            const resp = await fetch("/api/trades?limit=100");
            if (resp.ok) {
                allTrades = await resp.json();
                statTotalTrades.textContent = allTrades.length;
                badgeStreamCount.textContent = allTrades.length;
                renderTrades();
            }
        } catch (e) {
            console.error("Error fetching trades:", e);
        }
    }

    async function fetchSignals() {
        try {
            const resp = await fetch("/api/signals?limit=50");
            if (resp.ok) {
                allSignals = await resp.json();
                statTotalSignals.textContent = allSignals.length;
                badgeSignalCount.textContent = allSignals.length;
                renderSignals(allSignals);
            }
        } catch (e) {
            console.error("Error fetching signals:", e);
        }
    }

    // Attach Signal Filter Pills
    document.querySelectorAll("#signal-filter-pills .pill").forEach(pill => {
        pill.addEventListener("click", () => {
            document.querySelectorAll("#signal-filter-pills .pill").forEach(p => p.classList.remove("active"));
            pill.classList.add("active");
            currentSignalFilter = pill.getAttribute("data-signal-filter");
            renderSignals(allSignals);
        });
    });

    async function fetchRules() {
        try {
            const resp = await fetch("/api/rules");
            if (resp.ok) {
                const rules = await resp.json();
                renderRules(rules);
            }
        } catch (e) {
            console.error("Error fetching rules:", e);
        }
    }

    function renderRules(rules) {
        if (!rulesContainer) return;
        if (rules.length === 0) {
            rulesContainer.innerHTML = `<p style="color: var(--text-muted); font-size: 13px;">No active rules configured. Create a rule using the form on the left.</p>`;
            return;
        }

        rulesContainer.innerHTML = rules.map(r => `
            <div class="rule-item">
                <div class="rule-info">
                    <h4>${escapeHtml(r.name)}</h4>
                    <div class="rule-meta">
                        <span>Min Score: <strong>${r.min_score}</strong></span>
                        <span>Min Value: <strong>$${Number(r.min_value).toLocaleString()}</strong></span>
                        <span>Target: <strong>${escapeHtml(r.broker_target).toUpperCase()}</strong></span>
                        ${r.auto_execute ? '<span class="chip chip-highlight">Auto-Exec</span>' : ''}
                    </div>
                </div>
                <button class="btn btn-danger btn-sm btn-delete-rule" data-rule-id="${r.id}">Delete</button>
            </div>
        `).join("");

        document.querySelectorAll(".btn-delete-rule").forEach(btn => {
            btn.addEventListener("click", async () => {
                const id = btn.getAttribute("data-rule-id");
                if (confirm("Delete this rule?")) {
                    await fetch(`/api/rules/${id}`, { method: "DELETE" });
                    fetchRules();
                }
            });
        });
    }

    async function fetchPortfolio() {
        try {
            const resp = await fetch("/api/portfolio");
            if (resp.ok) {
                const data = await resp.json();
                const totalEquity = Number(data.portfolio_value || 100000).toLocaleString(undefined, {minimumFractionDigits: 2});
                const cash = Number(data.cash || 100000).toLocaleString(undefined, {minimumFractionDigits: 2});
                const posVal = Number(data.positions_value || 0).toLocaleString(undefined, {minimumFractionDigits: 2});
                const pnl = Number(data.unrealized_pnl || 0);

                statPortfolioValue.textContent = `$${totalEquity}`;
                statUnrealizedPnl.textContent = `${pnl >= 0 ? '+' : ''}$${pnl.toFixed(2)}`;
                statUnrealizedPnl.style.color = pnl >= 0 ? "var(--accent-emerald)" : "var(--accent-red)";

                portfolioTotalEquity.textContent = `$${totalEquity}`;
                portfolioCash.textContent = `$${cash}`;
                portfolioPositionsVal.textContent = `$${posVal}`;
                portfolioPnl.textContent = `${pnl >= 0 ? '+' : ''}$${pnl.toFixed(2)}`;
                portfolioPnl.style.color = pnl >= 0 ? "var(--accent-emerald)" : "var(--accent-red)";

                // Render positions
                const positions = data.positions || [];
                if (positionsTbody) {
                    if (positions.length === 0) {
                        positionsTbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 24px;">No active open positions in paper portfolio.</td></tr>`;
                    } else {
                        positionsTbody.innerHTML = positions.map(p => `
                            <tr>
                                <td><span class="ticker-badge">${escapeHtml(p.symbol)}</span></td>
                                <td class="mono-number">${p.qty}</td>
                                <td class="mono-number">$${Number(p.avg_entry_price).toFixed(2)}</td>
                                <td class="mono-number">$${Number(p.current_price).toFixed(2)}</td>
                                <td class="mono-number" style="color: ${p.unrealized_pnl >= 0 ? 'var(--accent-emerald)' : 'var(--accent-red)'}; font-weight: 700;">
                                    ${p.unrealized_pnl >= 0 ? '+' : ''}$${Number(p.unrealized_pnl).toFixed(2)}
                                </td>
                                <td>
                                    <button class="btn btn-outline btn-sm btn-sell-pos" data-symbol="${escapeHtml(p.symbol)}" data-qty="${p.qty}" data-price="${p.current_price}">
                                        Sell Position
                                    </button>
                                </td>
                            </tr>
                        `).join("");

                        document.querySelectorAll(".btn-sell-pos").forEach(btn => {
                            btn.addEventListener("click", () => {
                                const symbol = btn.getAttribute("data-symbol");
                                const qty = parseFloat(btn.getAttribute("data-qty"));
                                const price = parseFloat(btn.getAttribute("data-price"));
                                openOrderModal(symbol, price, null, "sell", qty);
                            });
                        });
                    }
                }

                // Render recent orders
                const orders = data.recent_orders || [];
                if (ordersTbody) {
                    if (orders.length === 0) {
                        ordersTbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 24px;">No executed orders yet.</td></tr>`;
                    } else {
                        ordersTbody.innerHTML = orders.map(o => `
                            <tr>
                                <td style="color: var(--text-muted); font-size: 11px;">${escapeHtml(o.created_at || "-")}</td>
                                <td><span class="ticker-badge">${escapeHtml(o.symbol)}</span></td>
                                <td><span class="action-badge ${o.side === 'buy' ? 'badge-purchase' : 'badge-sale'}">${escapeHtml(o.side.toUpperCase())}</span></td>
                                <td class="mono-number">${o.qty}</td>
                                <td class="mono-number">$${Number(o.fill_price).toFixed(2)}</td>
                                <td class="mono-number" style="font-weight: 700;">$${(o.qty * o.fill_price).toLocaleString(undefined, {minimumFractionDigits: 2})}</td>
                                <td><span class="chip chip-highlight">${escapeHtml(o.status.toUpperCase())}</span></td>
                            </tr>
                        `).join("");
                    }
                }
            }
        } catch (e) {
            console.error("Error fetching portfolio:", e);
        }
    }

    // 6. Modal Functions
    function openOrderModal(symbol = "", price = 100, signalId = null, side = "buy", qty = 10) {
        orderSymbolInput.value = symbol;
        orderPriceInput.value = price.toFixed(2);
        orderQtyInput.value = qty;
        orderSideSelect.value = side;
        orderModal.setAttribute("data-signal-id", signalId || "");
        orderModal.classList.remove("hidden");
    }

    btnCloseModal?.addEventListener("click", () => orderModal.classList.add("hidden"));
    btnManualOrder?.addEventListener("click", () => openOrderModal());

    orderForm?.addEventListener("submit", async (e) => {
        e.preventDefault();
        const symbol = orderSymbolInput.value.trim().toUpperCase();
        const qty = parseFloat(orderQtyInput.value);
        const price = parseFloat(orderPriceInput.value);
        const side = orderSideSelect.value;
        const signalId = orderModal.getAttribute("data-signal-id") || null;

        try {
            const resp = await fetch("/api/orders/execute", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    symbol,
                    qty,
                    side,
                    price,
                    signal_id: signalId ? parseInt(signalId) : null,
                    broker: "paper"
                })
            });
            const result = await resp.json();
            if (result.status === "filled") {
                alert(`Order filled! ${side.toUpperCase()} ${qty} shares of ${symbol} at $${price.toFixed(2)}`);
                orderModal.classList.add("hidden");
                fetchPortfolio();
            } else {
                alert(`Order failed: ${result.reason || result.status}`);
            }
        } catch (err) {
            alert("Error submitting order: " + err.message);
        }
    });

    // 7. Rule Form Submission
    ruleForm?.addEventListener("submit", async (e) => {
        e.preventDefault();
        const name = document.getElementById("rule-name").value.trim();
        const minScore = parseInt(document.getElementById("rule-min-score").value);
        const minValue = parseFloat(document.getElementById("rule-min-value").value);
        const positionSize = parseFloat(document.getElementById("rule-position-size").value);
        const brokerTarget = document.getElementById("rule-broker").value;
        const autoExecute = document.getElementById("rule-auto-execute").checked ? 1 : 0;

        const roleBoxes = document.querySelectorAll("input[name='role']:checked");
        const allowedRoles = Array.from(roleBoxes).map(cb => cb.value);

        const typeBoxes = document.querySelectorAll("input[name='type']:checked");
        const allowedTypes = Array.from(typeBoxes).map(cb => cb.value);

        try {
            const resp = await fetch("/api/rules", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    name,
                    min_score: minScore,
                    min_value: minValue,
                    allowed_roles: allowedRoles,
                    allowed_types: allowedTypes,
                    auto_execute: autoExecute,
                    broker_target: brokerTarget,
                    position_size_usd: positionSize
                })
            });
            if (resp.ok) {
                alert("Rule successfully created and activated!");
                ruleForm.reset();
                fetchRules();
            }
        } catch (err) {
            alert("Error creating rule: " + err.message);
        }
    });

    // 8. Server-Sent Events (SSE) Live Stream
    function initSSE() {
        const sse = new EventSource("/api/stream");
        const statusText = document.getElementById("connection-status-text");

        sse.onopen = () => {
            if (statusText) statusText.textContent = "SEC FEED CONNECTED";
        };

        sse.onmessage = (e) => {
            try {
                const msg = JSON.parse(e.data);
                if (msg.type === "trade") {
                    allTrades.unshift(msg.data);
                    statTotalTrades.textContent = allTrades.length;
                    badgeStreamCount.textContent = allTrades.length;
                    renderTrades();
                } else if (msg.type === "signal") {
                    fetchSignals();
                    fetchPortfolio();
                }
            } catch (err) {
                console.error("SSE parse error:", err);
            }
        };

        sse.onerror = () => {
            if (statusText) statusText.textContent = "FEED RECONNECTING...";
        };
    }

    // 8. Hyperliquid Intelligence Hub Functions
    async function fetchHyperliquidMarkets() {
        if (!hlTbody) return;
        try {
            const resp = await fetch("/api/hyperliquid/markets");
            if (resp.ok) {
                const data = await resp.json();
                hyperliquidMarkets = data.markets || [];
                hyperliquidSymbols = new Set(hyperliquidMarkets.map(m => m.symbol.toUpperCase()));
                
                const badgeHl = document.getElementById("badge-hl-count");
                if (badgeHl) badgeHl.textContent = hyperliquidMarkets.length;

                renderHyperliquidTable();
                // Re-render trades and signals so Hyperliquid badges appear
                renderTrades();
                renderSignals(allSignals);
            } else {
                hlTbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--accent-red); padding: 24px;">Failed to fetch live Hyperliquid markets.</td></tr>`;
            }
        } catch (err) {
            console.error("Error fetching Hyperliquid markets:", err);
            if (hlTbody) {
                hlTbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--accent-red); padding: 24px;">Error connecting to Hyperliquid network.</td></tr>`;
            }
        }
    }

    function renderHyperliquidTable() {
        if (!hlTbody) return;

        let filtered = hyperliquidMarkets.filter(m => {
            if (hlCurrentFilter === "buys" && (m.insider_buy_count || 0) === 0) return false;
            if (hlCurrentFilter === "sells" && (m.insider_sell_count || 0) === 0) return false;
            return true;
        });

        if (filtered.length === 0) {
            hlTbody.innerHTML = `
                <tr>
                    <td colspan="8" style="text-align: center; padding: 48px; color: var(--text-muted);">
                        No insider-traded Hyperliquid assets found matching the selected filter.
                    </td>
                </tr>
            `;
            return;
        }

        hlTbody.innerHTML = filtered.map(m => {
            const fundingPercent = (m.funding_rate * 100).toFixed(4);
            const fundingColor = m.funding_rate >= 0 ? "var(--accent-emerald)" : "var(--accent-red)";
            const latestTrade = (m.recent_trades && m.recent_trades.length > 0) ? m.recent_trades[0] : null;

            let insiderSummaryHtml = `
                <div style="display: flex; gap: 6px; align-items: center; flex-wrap: wrap;">
                    ${m.insider_buy_count > 0 ? `<span class="action-badge badge-purchase" style="font-size: 11px;">${m.insider_buy_count} BUY</span>` : ""}
                    ${m.insider_sell_count > 0 ? `<span class="action-badge badge-sale" style="font-size: 11px;">${m.insider_sell_count} SELL</span>` : ""}
                    <span class="chip" style="font-size: 11px;">Total: ${m.insider_trade_count}</span>
                </div>
            `;

            let latestTradeHtml = '<span style="color: var(--text-muted); font-size: 11px;">-</span>';
            if (latestTrade) {
                const isBuy = latestTrade.transaction_code === "P";
                latestTradeHtml = `
                    <div>
                        <div style="font-weight: 600; font-size: 12px; color: ${isBuy ? 'var(--accent-emerald)' : 'var(--text-primary)'};">
                            ${escapeHtml(latestTrade.insider_name)}
                        </div>
                        <div style="font-size: 11px; color: var(--text-secondary); margin-top: 2px;">
                            ${escapeHtml(latestTrade.insider_title || "Officer")} &bull; 
                            <span style="font-weight: 600;">$${Number(latestTrade.value || 0).toLocaleString()}</span>
                        </div>
                    </div>
                `;
            }

            return `
                <tr style="background: rgba(0, 245, 155, 0.02);">
                    <td>
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <span class="ticker-badge" style="font-weight: 700; font-size: 15px; color: var(--accent-emerald);">${escapeHtml(m.symbol)}</span>
                            <span class="chip" style="font-size: 10px; border-color: rgba(0,245,155,0.4);">L1 PERP</span>
                        </div>
                        <div style="font-size: 11px; color: var(--text-muted); margin-top: 3px;">
                            ${escapeHtml(m.company_name || "")}
                        </div>
                    </td>
                    <td class="mono-number" style="font-weight: 700; font-size: 14px;">$${Number(m.mark_price).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 4})}</td>
                    <td class="mono-number" style="color: ${fundingColor}; font-weight: 600;">${fundingPercent}%</td>
                    <td class="mono-number" style="font-weight: 600;">$${Number(m.volume_24h).toLocaleString(undefined, {maximumFractionDigits: 0})}</td>
                    <td class="mono-number">${Number(m.open_interest).toLocaleString(undefined, {maximumFractionDigits: 1})}</td>
                    <td>${insiderSummaryHtml}</td>
                    <td>${latestTradeHtml}</td>
                    <td>
                        <div style="display: flex; gap: 6px;">
                            <a href="https://app.hyperliquid.xyz/trade/${encodeURIComponent(m.symbol)}" target="_blank" rel="noopener noreferrer" class="btn btn-primary btn-sm" style="text-decoration: none; padding: 5px 12px; font-size: 11px; font-weight: 600;">
                                Open on Hyperliquid ↗
                            </a>
                            <button class="btn btn-outline btn-sm btn-copy-trade" data-symbol="${escapeHtml(m.symbol)}" data-price="${m.mark_price}" style="padding: 5px 10px; font-size: 11px;">
                                Simulate
                            </button>
                        </div>
                    </td>
                </tr>
            `;
        }).join("");

        // Attach sim buttons
        hlTbody.querySelectorAll(".btn-copy-trade").forEach(btn => {
            btn.addEventListener("click", () => {
                const sym = btn.getAttribute("data-symbol");
                const prc = parseFloat(btn.getAttribute("data-price")) || 100;
                openOrderModal(sym, prc, null);
            });
        });
    }

    // Attach Hyperliquid Hub filters
    document.getElementById("hl-filter-all")?.addEventListener("click", () => {
        document.getElementById("hl-filter-all").classList.add("active");
        document.getElementById("hl-filter-buys")?.classList.remove("active");
        document.getElementById("hl-filter-sells")?.classList.remove("active");
        hlCurrentFilter = "all";
        renderHyperliquidTable();
    });

    document.getElementById("hl-filter-buys")?.addEventListener("click", () => {
        document.getElementById("hl-filter-buys").classList.add("active");
        document.getElementById("hl-filter-all")?.classList.remove("active");
        document.getElementById("hl-filter-sells")?.classList.remove("active");
        hlCurrentFilter = "buys";
        renderHyperliquidTable();
    });

    document.getElementById("hl-filter-sells")?.addEventListener("click", () => {
        document.getElementById("hl-filter-sells").classList.add("active");
        document.getElementById("hl-filter-all")?.classList.remove("active");
        document.getElementById("hl-filter-buys")?.classList.remove("active");
        hlCurrentFilter = "sells";
        renderHyperliquidTable();
    });

    document.getElementById("hl-refresh-btn")?.addEventListener("click", () => {
        fetchHyperliquidMarkets();
    });

    // Initialize
    fetchTrades();
    fetchSignals();
    fetchHyperliquidMarkets();
    fetchRules();
    fetchPortfolio();
    initSSE();
});
