window.escapeHtml = window.escapeHtml || function(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
};
var escapeHtml = window.escapeHtml;

// BioSeeder Company & Pipeline Dossier Modal Manager
class DossierManager {
  constructor() {
    this.modal = document.getElementById("dossier-modal");
    this.closeBtn = document.getElementById("modal-close");
    this.tickerEl = document.getElementById("modal-ticker");
    this.nameEl = document.getElementById("modal-company-name");
    this.marketCapEl = document.getElementById("modal-market-cap");
    this.cashEl = document.getElementById("modal-cash");
    this.burnEl = document.getElementById("modal-burn");
    this.runwayEl = document.getElementById("modal-runway");
    this.pipelineListEl = document.getElementById("modal-pipeline-list");
    this.catalystsListEl = document.getElementById("modal-catalysts-list");

    if (this.closeBtn) {
      this.closeBtn.addEventListener("click", () => this.close());
    }

    if (this.modal) {
      this.modal.addEventListener("click", (e) => {
        if (e.target === this.modal) this.close();
      });
    }
  }

  async open(ticker) {
    if (!this.modal) return;
    this.modal.classList.add("open");

    this.tickerEl.textContent = ticker;
    this.nameEl.textContent = "Loading institutional pipeline dossier...";
    this.pipelineListEl.innerHTML = `<div style="color: var(--text-muted); padding: 20px;">Retrieving pipeline records...</div>`;
    this.catalystsListEl.innerHTML = "";

    try {
      const res = await fetch(`/api/v1/company/${encodeURIComponent(ticker)}`);
      if (!res.ok) throw new Error("Failed to load dossier");
      const comp = await res.json();
      this.render(comp);

      // Render TradingView chart inside modal
      const tvContainer = document.getElementById("modal-tv-widget-container");
      if (tvContainer) {
        tvContainer.innerHTML = "";
        const iframe = document.createElement("iframe");
        iframe.style.width = "100%";
        iframe.style.height = "100%";
        iframe.style.border = "none";
        iframe.src = `https://s.tradingview.com/widgetembed/?frameElementId=tradingview_widget_modal&symbol=${encodeURIComponent(ticker)}&interval=D&hidesidetoolbar=1&symboledit=0&saveimage=0&toolbarbg=0a0e17&studies=%5B%5D&theme=dark&style=1&timezone=Etc%2FUTC&studies_overrides=%7B%7D&overrides=%7B%7D&enabled_features=%5B%5D&disabled_features=%5B%5D&locale=en&utm_source=localhost`;
        tvContainer.appendChild(iframe);
      }
    } catch (err) {
      this.nameEl.textContent = "Error loading company dossier";
      this.pipelineListEl.innerHTML = `<div style="color: var(--accent-crimson); padding: 20px;">${escapeHtml(err.message)}</div>`;
    }
  }

  close() {
    if (this.modal) this.modal.classList.remove("open");
    const tvContainer = document.getElementById("modal-tv-widget-container");
    if (tvContainer) tvContainer.innerHTML = "";
  }

  render(comp) {
    this.nameEl.textContent = `${comp.name || ''} (${comp.exchange || ''})`;
    this.marketCapEl.textContent = comp.market_cap ? `$${comp.market_cap.toLocaleString()}M` : "--";
    this.cashEl.textContent = comp.cash_and_equivalents ? `$${comp.cash_and_equivalents.toLocaleString()}M` : "--";
    this.burnEl.textContent = comp.quarterly_burn_rate ? `$${comp.quarterly_burn_rate.toLocaleString()}M/q` : "--";

    if (comp.cash_runway_months !== null && comp.cash_runway_months !== undefined) {
      if (comp.cash_runway_months < 6.0) {
        this.runwayEl.innerHTML = `<span style="color: var(--accent-crimson);">${escapeHtml(comp.cash_runway_months)} mos (HAZARD)</span>`;
      } else {
        this.runwayEl.innerHTML = `<span style="color: var(--accent-emerald);">${escapeHtml(comp.cash_runway_months)} mos</span>`;
      }
    } else {
      this.runwayEl.textContent = "--";
    }

    // Render Pipeline
    const stages = ["Preclinical", "Phase 1", "Phase 2", "Phase 3", "NDA/BLA", "Approved"];

    if (!comp.drugs || comp.drugs.length === 0) {
      this.pipelineListEl.innerHTML = `<div style="color: var(--text-muted);">No tracked pipeline candidates.</div>`;
    } else {
      this.pipelineListEl.innerHTML = comp.drugs.map(drug => {
        const currentPhase = (drug.highest_phase || "").toLowerCase();
        let activeIdx = 0;
        if (currentPhase.includes("phase 1")) activeIdx = 1;
        else if (currentPhase.includes("phase 2")) activeIdx = 2;
        else if (currentPhase.includes("phase 3")) activeIdx = 3;
        else if (currentPhase.includes("nda") || currentPhase.includes("bla") || currentPhase.includes("pdufa")) activeIdx = 4;
        else if (currentPhase.includes("approved")) activeIdx = 5;

        const trackHtml = stages.map((st, i) => `
          <div style="flex: 1; text-align: center;">
            <div class="pipeline-step ${i <= activeIdx ? 'active' : ''}"></div>
            <div style="font-size: 9px; color: ${i <= activeIdx ? 'var(--accent-cyan)' : 'var(--text-muted)'}; margin-top: 4px;">${st}</div>
          </div>
        `).join("");

        const trialsHtml = drug.trials && drug.trials.length > 0 ? `
          <div style="margin-top: 10px; font-size: 11px; background: var(--bg-base); padding: 8px 12px; border-radius: 4px;">
            <strong style="color: var(--text-secondary);">Clinical Trials:</strong>
            ${drug.trials.map(t => {
              const nctSafe = escapeHtml(t.nct_id);
              const nctUri = encodeURIComponent(t.nct_id || "");
              const phaseSafe = escapeHtml(t.phase);
              const statusSafe = escapeHtml(t.status);
              const enrollSafe = t.enrollment ? escapeHtml(t.enrollment) : '--';
              return `
              <div style="display: flex; justify-content: space-between; margin-top: 4px; color: var(--text-muted);">
                <a href="https://clinicaltrials.gov/study/${nctUri}" target="_blank" rel="noopener noreferrer" style="color: var(--accent-cyan); text-decoration: none; font-family: var(--font-mono);">
                  ${nctSafe} (${phaseSafe})
                </a>
                <span>Status: <strong style="color: var(--text-primary);">${statusSafe}</strong> | N=${enrollSafe}</span>
              </div>
              `;
            }).join("")}
          </div>
        ` : '';

        const codeNameSafe = escapeHtml(drug.code_name);
        const genericNameSafe = escapeHtml(drug.generic_name);
        const brandNameSafe = escapeHtml(drug.brand_name);
        const indicationSafe = escapeHtml(drug.indication);
        const therapeuticAreaSafe = escapeHtml(drug.therapeutic_area);
        const moaSafe = escapeHtml(drug.mechanism_of_action);

        return `
          <div class="kpi-card" style="margin-bottom: 8px;">
            <div style="display: flex; justify-content: space-between; align-items: flex-start;">
              <div>
                <strong style="font-size: 15px; color: var(--text-primary);">${codeNameSafe}</strong>
                ${drug.generic_name ? `<span style="color: var(--text-secondary); margin-left: 6px;">(${genericNameSafe})</span>` : ''}
                ${drug.brand_name ? `<span style="background: rgba(0, 245, 155, 0.15); color: var(--accent-emerald); padding: 1px 5px; border-radius: 2px; font-size: 10px; font-weight: 700; margin-left: 6px;">${brandNameSafe}</span>` : ''}
              </div>
              <div style="font-family: var(--font-mono); font-size: 11px; color: var(--accent-amber);">
                ${drug.target_tam ? 'TAM: $' + drug.target_tam.toLocaleString() + 'M' : ''}
              </div>
            </div>
            <div style="font-size: 12px; color: var(--text-secondary); margin-top: 4px;">
              <strong>Indication:</strong> ${indicationSafe} (${therapeuticAreaSafe})
            </div>
            ${drug.mechanism_of_action ? `<div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">MoA: ${moaSafe}</div>` : ''}
            
            <div class="pipeline-track" style="margin-top: 12px;">
              ${trackHtml}
            </div>
            ${trialsHtml}
          </div>
        `;
      }).join("");
    }

    // Render Catalysts
    if (!comp.catalysts || comp.catalysts.length === 0) {
      this.catalystsListEl.innerHTML = `<div style="color: var(--text-muted);">No upcoming catalysts recorded.</div>`;
    } else {
      this.catalystsListEl.innerHTML = comp.catalysts.map(cat => {
        let catCountdown;
        if (cat.days_to_event < 0) {
          catCountdown = `COMPLETED (${Math.abs(cat.days_to_event)}d ago)`;
        } else if (cat.days_to_event === 0) {
          catCountdown = 'TODAY';
        } else {
          catCountdown = `T-${cat.days_to_event}d`;
        }

        const catTypeSafe = escapeHtml(cat.catalyst_type);
        const catDrugSafe = escapeHtml(cat.drug_name);
        const catDateSafe = escapeHtml(cat.target_date);
        const catDetailsSafe = escapeHtml(cat.details);
        const breakdown = cat.score_breakdown || {};

        return `
        <div class="kpi-card" style="margin-bottom: 8px; border: 1px solid var(--border-medium); border-radius: var(--radius-xs);">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <strong style="font-size: 13px; color: var(--text-primary);">${catTypeSafe} — ${catDrugSafe}</strong>
            <span class="countdown-timer">${catCountdown} (${catDateSafe})</span>
          </div>
          ${cat.details ? `<div style="font-size: 12px; color: var(--text-secondary); margin-top: 4px;">${catDetailsSafe}</div>` : ''}
          <div style="display: flex; gap: 16px; margin-top: 8px; font-family: var(--font-mono); font-size: 11px; color: var(--text-muted);">
            <span>Bio-Alpha: <strong style="color: var(--accent-cyan);">${cat.bio_alpha_score !== null && cat.bio_alpha_score !== undefined ? cat.bio_alpha_score.toFixed(1) : '--'}</strong></span>
            <span>PoS: <strong>${breakdown.pos_score !== null && breakdown.pos_score !== undefined ? breakdown.pos_score.toFixed(1) : '--'}</strong></span>
            <span>Asymmetry: <strong>${breakdown.asymmetry_score !== null && breakdown.asymmetry_score !== undefined ? breakdown.asymmetry_score.toFixed(1) : '--'}</strong></span>
            <span>Proximity: <strong>${breakdown.proximity_score !== null && breakdown.proximity_score !== undefined ? breakdown.proximity_score.toFixed(1) : '--'}</strong></span>
          </div>
        </div>
        `;
      }).join("");
    }
  }
}

window.dossierManager = new DossierManager();
