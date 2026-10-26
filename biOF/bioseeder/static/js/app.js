// BioSeeder Terminal Application State & Orchestrator
class BioSeederApp {
  constructor() {
    this.currentTab = "calendar";
    this.catalysts = [];
    this.screenerItems = [];

    this.searchInput = document.getElementById("search-input");
    this.phaseFilter = document.getElementById("phase-filter");
    this.typeFilter = document.getElementById("type-filter");
    this.daysFilter = document.getElementById("days-filter");
    this.mcapFilter = document.getElementById("mcap-filter");
    this.scoreFilter = document.getElementById("score-filter");
    this.healthFilter = document.getElementById("health-filter");
    this.btnResetFilters = document.getElementById("btn-reset-filters");
    this.btnSeed = document.getElementById("btn-seed");
    this.clockEl = document.getElementById("terminal-clock");

    this.initEvents();
    this.startClock();
    this.loadData();
  }

  startClock() {
    const update = () => {
      if (this.clockEl) {
        const now = new Date();
        this.clockEl.textContent = now.toISOString().slice(11, 19) + " UTC";
      }
    };
    update();
    setInterval(update, 1000);
  }

  initEvents() {
    // Tab switching
    document.querySelectorAll(".tab-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        this.switchTab(btn.dataset.tab);
      });
    });

    // Filters
    if (this.searchInput) {
      this.searchInput.addEventListener("input", () => this.applyFilters());
    }
    if (this.phaseFilter) {
      this.phaseFilter.addEventListener("change", () => this.applyFilters());
    }
    if (this.typeFilter) {
      this.typeFilter.addEventListener("change", () => this.applyFilters());
    }
    if (this.daysFilter) {
      this.daysFilter.addEventListener("change", () => this.applyFilters());
    }
    if (this.mcapFilter) {
      this.mcapFilter.addEventListener("change", () => this.applyFilters());
    }
    if (this.scoreFilter) {
      this.scoreFilter.addEventListener("change", () => this.applyFilters());
    }
    if (this.healthFilter) {
      this.healthFilter.addEventListener("change", () => this.applyFilters());
    }
    if (this.btnResetFilters) {
      this.btnResetFilters.addEventListener("click", () => {
        if (this.searchInput) this.searchInput.value = "";
        if (this.phaseFilter) this.phaseFilter.value = "";
        if (this.typeFilter) this.typeFilter.value = "";
        if (this.daysFilter) this.daysFilter.value = "";
        if (this.mcapFilter) this.mcapFilter.value = "";
        if (this.scoreFilter) this.scoreFilter.value = "";
        if (this.healthFilter) this.healthFilter.value = "";
        this.applyFilters();
      });
    }

    // Seed button
    if (this.btnSeed) {
      this.btnSeed.addEventListener("click", async () => {
        this.btnSeed.disabled = true;
        this.btnSeed.textContent = "Seeding...";
        try {
          await fetch("/api/v1/seed", { method: "POST" });
          await this.loadData();
        } finally {
          this.btnSeed.disabled = false;
          this.btnSeed.textContent = "⚡ Refresh / Seed Pipeline";
        }
      });
    }
  }

  switchTab(tabId) {
    this.currentTab = tabId;
    document.querySelectorAll(".tab-content").forEach(el => el.style.display = "none");
    
    const target = document.getElementById(`view-${tabId}`);
    if (target) target.style.display = "block";

    const filterBar = document.getElementById("filter-bar");
    if (filterBar) {
      filterBar.style.display = (tabId === "live-feed" || tabId === "tradingview") ? "none" : "flex";
    }

    if (tabId === "screener") {
      this.loadScreener();
    } else if (tabId === "tradingview") {
      this.initTradingViewTab();
    }
  }

  initTradingViewTab() {
    if (!this.tvTabInitialized) {
      this.tvTabInitialized = true;
      document.querySelectorAll(".btn-tv-quick").forEach(btn => {
        btn.addEventListener("click", () => {
          const ticker = btn.dataset.ticker;
          const selectEl = document.getElementById("tv-select-ticker");
          if (selectEl) selectEl.value = ticker;
          this.loadTradingViewWidget("tradingview-widget-container", ticker);
        });
      });

      const selectEl = document.getElementById("tv-select-ticker");
      if (selectEl) {
        selectEl.addEventListener("change", (e) => {
          const ticker = e.target.value;
          this.loadTradingViewWidget("tradingview-widget-container", ticker);
        });
      }
    }
    const currentTicker = this.activeTvTicker || "VRTX";
    this.loadTradingViewWidget("tradingview-widget-container", currentTicker);
  }

  loadTradingViewWidget(containerId, ticker) {
    const container = document.getElementById(containerId);
    if (!container) return;

    this.activeTvTicker = ticker;
    const tickerEl = document.getElementById("tv-active-ticker");
    if (tickerEl) tickerEl.textContent = ticker;

    const selectEl = document.getElementById("tv-select-ticker");
    if (selectEl && selectEl.value !== ticker) {
      selectEl.value = ticker;
    }

    const names = {
      "VRTX": "Vertex Pharmaceuticals (NASDAQ)",
      "REGN": "Regeneron Pharmaceuticals (NASDAQ)",
      "GILD": "Gilead Sciences (NASDAQ)",
      "BIIB": "Biogen (NASDAQ)",
      "MRNA": "Moderna (NASDAQ)",
      "BNTX": "BioNTech (NASDAQ)",
      "ALNY": "Alnylam Pharmaceuticals (NASDAQ)",
      "ARGX": "Argenx SE (NASDAQ)",
      "SRPT": "Sarepta Therapeutics (NASDAQ)",
      "VKTX": "Viking Therapeutics (NASDAQ)",
      "CRSP": "CRISPR Therapeutics (NASDAQ)",
      "MDGL": "Madrigal Pharmaceuticals (NASDAQ)",
      "CYTK": "Cytokinetics (NASDAQ)",
      "INSM": "Insmed (NASDAQ)",
      "BBIO": "BridgeBio Pharma (NASDAQ)",
      "ARWR": "Arrowhead Pharmaceuticals (NASDAQ)",
      "IOVA": "Iovance Biotherapeutics (NASDAQ)",
      "NTLA": "Intellia Therapeutics (NASDAQ)",
      "BEAM": "Beam Therapeutics (NASDAQ)",
      "AXSM": "Axsome Therapeutics (NASDAQ)",
      "DNLI": "Denali Therapeutics (NASDAQ)",
      "RXRX": "Recursion Pharmaceuticals (NASDAQ)",
      "KYMR": "Kymera Therapeutics (NASDAQ)",
      "BCRX": "BioCryst Pharmaceuticals (NASDAQ)",
      "SLS": "SELLAS Life Sciences (NASDAQ)",
      "APTO": "Aptose Biosciences (NASDAQ)",
      "NANO": "Nanovest Therapeutics (NASDAQ)",
      "XBI": "SPDR S&P Biotech ETF (NYSE Arca)",
      "IBB": "iShares Biotechnology ETF (NASDAQ)"
    };
    const nameEl = document.getElementById("tv-active-name");
    if (nameEl) nameEl.textContent = names[ticker] || `${ticker} Equity`;

    container.innerHTML = "";
    const iframe = document.createElement("iframe");
    iframe.style.width = "100%";
    iframe.style.height = "100%";
    iframe.style.border = "none";
    iframe.src = `https://s.tradingview.com/widgetembed/?frameElementId=tradingview_widget&symbol=${encodeURIComponent(ticker)}&interval=D&hidesidetoolbar=0&symboledit=1&saveimage=1&toolbarbg=0a0e17&studies=%5B%5D&theme=dark&style=1&timezone=Etc%2FUTC&studies_overrides=%7B%7D&overrides=%7B%7D&enabled_features=%5B%5D&disabled_features=%5B%5D&locale=en&utm_source=localhost`;
    container.appendChild(iframe);
  }

  async loadData() {
    try {
      const res = await fetch("/api/v1/catalysts");
      const data = await res.json();
      this.catalysts = data.items || [];

      // Auto-seed if database is empty
      if (this.catalysts.length === 0) {
        await fetch("/api/v1/seed", { method: "POST" });
        const resAfter = await fetch("/api/v1/catalysts");
        const dataAfter = await resAfter.json();
        this.catalysts = dataAfter.items || [];
      }

      this.updateKPIs();
      this.applyFilters();
      if (window.tickerManager) {
        window.tickerManager.loadFeed();
      }
    } catch (err) {
      console.error("Failed to load catalysts:", err);
    }
  }

  async loadScreener() {
    try {
      const res = await fetch("/api/v1/screener");
      const data = await res.json();
      this.screenerItems = data.items || [];
      this.applyFilters();
    } catch (err) {
      console.error("Failed to load screener:", err);
    }
  }

  updateKPIs() {
    // Unique tracked companies
    const uniqueTickers = new Set(this.catalysts.map(c => c.ticker));
    const trackedEl = document.getElementById("kpi-tracked-count");
    if (trackedEl) trackedEl.textContent = uniqueTickers.size;

    // PDUFA next 30 days (strictly future/current window)
    const pdufa30d = this.catalysts.filter(c => 
      (c.catalyst_type.includes("PDUFA") || c.catalyst_type.includes("Approval")) && 
      c.days_to_event >= 0 &&
      c.days_to_event <= 30
    ).length;
    const pdufaEl = document.getElementById("kpi-pdufa-count");
    if (pdufaEl) pdufaEl.textContent = pdufa30d;

    // High Bio-Alpha (>= 75)
    const highAlpha = this.catalysts.filter(c => c.bio_alpha_score >= 75.0).length;
    const alphaEl = document.getElementById("kpi-high-alpha-count");
    if (alphaEl) alphaEl.textContent = highAlpha;

    // Dilution hazards
    const dilutionAlerts = this.catalysts.filter(c => c.dilution_flag).length;
    const dilutionEl = document.getElementById("kpi-dilution-count");
    if (dilutionEl) dilutionEl.textContent = dilutionAlerts;
  }

  applyFilters() {
    const q = (this.searchInput?.value || "").toLowerCase().trim();
    const phase = this.phaseFilter?.value || "";
    const type = this.typeFilter?.value || "";
    const daysVal = this.daysFilter?.value || "";
    const mcapVal = this.mcapFilter?.value || "";
    const scoreVal = this.scoreFilter?.value || "";
    const healthVal = this.healthFilter?.value || "";

    // 1. Filter Catalysts Calendar
    const filteredCatalysts = this.catalysts.filter(item => {
      // Ticker / Company / Drug / Indication text query
      if (q) {
        const matchesTicker = (item.ticker || "").toLowerCase().includes(q);
        const matchesCompany = (item.company_name || "").toLowerCase().includes(q);
        const matchesDrug = (item.drug_name || "").toLowerCase().includes(q);
        const matchesIndication = (item.indication || "").toLowerCase().includes(q);
        const matchesArea = (item.therapeutic_area || "").toLowerCase().includes(q);
        if (!matchesTicker && !matchesCompany && !matchesDrug && !matchesIndication && !matchesArea) {
          return false;
        }
      }

      // Clinical Phase filter
      if (phase && !(item.phase || "").toLowerCase().includes(phase.toLowerCase())) {
        return false;
      }

      // Catalyst Type filter
      if (type && !(item.catalyst_type || "").toLowerCase().includes(type.toLowerCase())) {
        return false;
      }

      // Target Date & Countdown timeframe filter
      if (daysVal === "past") {
        if (item.days_to_event >= 0) return false;
      } else if (daysVal) {
        const maxDays = parseInt(daysVal, 10);
        if (item.days_to_event < 0 || item.days_to_event > maxDays) {
          return false;
        }
      }

      // Bio-Alpha Score filter
      if (scoreVal) {
        const score = item.bio_alpha_score ?? 0;
        if (scoreVal === "high" && score < 75.0) return false;
        if (scoreVal === "med" && (score < 50.0 || score >= 75.0)) return false;
        if (scoreVal === "low" && score >= 50.0) return false;
      }

      // Financial Health / Dilution Risk filter
      if (healthVal) {
        if (healthVal === "dilution" && !item.dilution_flag) return false;
        if (healthVal === "safe" && item.dilution_flag) return false;
      }

      return true;
    });

    if (window.calendarManager) {
      window.calendarManager.renderCatalysts(filteredCatalysts);
    }

    // 2. Filter Screener Items
    if (this.screenerItems && this.screenerItems.length > 0) {
      const filteredScreener = this.screenerItems.filter(item => {
        // Ticker / Asset / Indication
        if (q) {
          const matchesTicker = (item.ticker || "").toLowerCase().includes(q);
          const matchesDrug = (item.drug_name || "").toLowerCase().includes(q);
          const matchesIndication = (item.indication || "").toLowerCase().includes(q);
          if (!matchesTicker && !matchesDrug && !matchesIndication) {
            return false;
          }
        }

        // Phase
        if (phase && !(item.phase || "").toLowerCase().includes(phase.toLowerCase())) {
          return false;
        }

        // Market Cap Filter
        if (mcapVal) {
          const mcap = item.market_cap; // in Millions USD
          if (mcap === null || mcap === undefined) return false;
          if (mcapVal === "micro" && mcap >= 300) return false;
          if (mcapVal === "small" && (mcap < 300 || mcap >= 2000)) return false;
          if (mcapVal === "mid" && (mcap < 2000 || mcap >= 10000)) return false;
          if (mcapVal === "large" && mcap < 10000) return false;
        }

        // Composite Alpha Score
        if (scoreVal) {
          const score = item.composite_score ?? 0;
          if (scoreVal === "high" && score < 75.0) return false;
          if (scoreVal === "med" && (score < 50.0 || score >= 75.0)) return false;
          if (scoreVal === "low" && score >= 50.0) return false;
        }

        // Dilution / Financial Health
        if (healthVal) {
          if (healthVal === "dilution" && !item.dilution_flag) return false;
          if (healthVal === "safe" && item.dilution_flag) return false;
        }

        return true;
      });

      if (window.calendarManager) {
        window.calendarManager.renderScreener(filteredScreener);
      }
    }
  }
}

document.addEventListener("DOMContentLoaded", () => {
  window.app = new BioSeederApp();
});
