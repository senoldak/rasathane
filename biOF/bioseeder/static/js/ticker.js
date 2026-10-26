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

// BioSeeder Live Regulatory Ticker Tape & Feed Component
class TickerManager {
  constructor() {
    this.tickerContent = document.getElementById("ticker-content");
    this.feedContainer = document.getElementById("live-feed-cards");
    this.initClickHandlers();
  }

  initClickHandlers() {
    if (this.feedContainer) {
      this.feedContainer.addEventListener("click", (e) => {
        const cell = e.target.closest(".ticker-cell");
        if (cell && cell.dataset.ticker && window.dossierManager) {
          window.dossierManager.open(cell.dataset.ticker);
        }
      });
    }
  }

  async loadFeed() {
    try {
      const res = await fetch("/api/v1/approvals/live");
      if (!res.ok) return;
      const data = await res.json();
      this.renderTickerTape(data.feed || []);
      this.renderFeedTab(data.feed || []);
    } catch (err) {
      console.error("Failed to load live feed:", err);
    }
  }

  renderTickerTape(items) {
    if (!this.tickerContent || items.length === 0) return;

    const html = items.map(item => {
      let tagClass = "tag-trial";
      const cat = item.category || "";
      if (cat === "APPROVAL") tagClass = "tag-approval";
      if (cat === "CRL") tagClass = "tag-crl";
      if (cat === "ADCOM") tagClass = "tag-adcom";

      const catSafe = escapeHtml(cat);
      const tickerSafe = escapeHtml(item.ticker);
      const headlineSafe = escapeHtml(item.headline);

      return `
        <span class="ticker-item">
          <span class="ticker-tag ${tagClass}">${catSafe}</span>
          <strong>${item.ticker ? tickerSafe + ':' : ''}</strong> ${headlineSafe}
        </span>
      `;
    }).join("");

    // Duplicate content for smooth marquee looping
    this.tickerContent.innerHTML = html + html;
  }

  renderFeedTab(items) {
    if (!this.feedContainer) return;

    if (items.length === 0) {
      this.feedContainer.innerHTML = `<div style="color: var(--text-muted); text-align: center; padding: 40px;">No recent regulatory events.</div>`;
      return;
    }

    this.feedContainer.innerHTML = items.map(item => {
      let borderCol = "var(--border-subtle)";
      let tagClass = "tag-trial";
      const cat = item.category || "";
      if (cat === "APPROVAL") {
        tagClass = "tag-approval";
        borderCol = "var(--accent-emerald)";
      } else if (cat === "CRL") {
        tagClass = "tag-crl";
        borderCol = "var(--accent-crimson)";
      } else if (cat === "ADCOM") {
        tagClass = "tag-adcom";
        borderCol = "var(--accent-amber)";
      }

      const catSafe = escapeHtml(cat);
      const tickerSafe = escapeHtml(item.ticker);
      const headlineSafe = escapeHtml(item.headline);
      const detailsSafe = escapeHtml(item.details);
      const timeStr = item.timestamp ? new Date(item.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '--:--:--';

      return `
        <div class="kpi-card" style="border-left: 4px solid ${borderCol};">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
            <div style="display: flex; align-items: center; gap: 8px;">
              <span class="ticker-tag ${tagClass}">${catSafe}</span>
              ${item.ticker ? `<span class="ticker-cell" data-ticker="${tickerSafe}">${tickerSafe}</span>` : ''}
            </div>
            <span style="font-family: var(--font-mono); font-size: 11px; color: var(--text-muted);">${timeStr} UTC</span>
          </div>
          <div style="font-size: 14px; font-weight: 600; color: var(--text-primary); margin-bottom: 4px;">
            ${headlineSafe}
          </div>
          <div style="font-size: 12px; color: var(--text-secondary); line-height: 1.4;">
            ${detailsSafe}
          </div>
        </div>
      `;
    }).join("");
  }
}

window.tickerManager = new TickerManager();
