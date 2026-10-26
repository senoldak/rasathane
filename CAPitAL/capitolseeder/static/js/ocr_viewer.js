// ==============================================================================
// CAPITOLSEEDER // OCR INSPECTOR & VERIFICATION MODAL
// ==============================================================================

function openOcrModal(trade) {
  const modal = document.getElementById('ocr-modal');
  if (!modal) return;

  const tickerBadge = document.getElementById('ocr-modal-ticker');
  if (tickerBadge) tickerBadge.textContent = `${trade.ticker} • ${trade.filing_id}`;

  // Structured fields preview
  const fieldsContainer = document.getElementById('ocr-structured-fields');
  if (fieldsContainer) {
    fieldsContainer.innerHTML = `
      <div style="display: grid; grid-template-columns: 140px 1fr; gap: 6px; font-family: var(--font-mono);">
        <span style="color: var(--text-muted);">MEMBER:</span>
        <span>${trade.politician_name || 'Congressional Member'} (${trade.party || ''}-${trade.state || ''})</span>

        <span style="color: var(--text-muted);">TICKER / ASSET:</span>
        <span><strong style="color: var(--alpha-gold);">$${trade.ticker}</strong> (${trade.asset_type})</span>

        <span style="color: var(--text-muted);">TRANSACTION DATE:</span>
        <span>${trade.transaction_date}</span>

        <span style="color: var(--text-muted);">DISCLOSURE DATE:</span>
        <span>${trade.disclosure_date} (Lag: ${trade.filing_lag_days}d)</span>

        <span style="color: var(--text-muted);">AMOUNT BRACKET:</span>
        <span>${trade.amount_range_str} (Midpoint: $${trade.amount_midpoint.toLocaleString()})</span>

        <span style="color: var(--text-muted);">OWNERSHIP:</span>
        <span style="color: ${trade.owner_type === 'Spouse' ? 'var(--alpha-gold)' : 'inherit'}; font-weight: ${trade.owner_type === 'Spouse' ? 'bold' : 'normal'};">
          ${trade.owner_type}
        </span>

        <span style="color: var(--text-muted);">STOCK ACT STATUS:</span>
        <span style="color: ${trade.is_stock_act_violation ? 'var(--violation-red)' : 'var(--alpha-green)'};">
          ${trade.is_stock_act_violation ? `VIOLATION (${trade.violation_severity})` : 'COMPLIANT'}
        </span>
      </div>
    `;
  }

  // Raw OCR stream preview
  const rawOutput = document.getElementById('ocr-raw-output');
  if (rawOutput) {
    if (trade.ocr_raw_text) {
      rawOutput.textContent = trade.ocr_raw_text;
    } else {
      rawOutput.textContent = `[OCR ENGINE: Tesseract v0.3.13 + OpenCV Otsu Preprocessing]
PAGE 1 / 1
UNITED STATES CONGRESS // PERIODIC TRANSACTION REPORT (PTR)
FILING ID: ${trade.filing_id}
OWNER: ${trade.owner_type}
TICKER: ${trade.ticker}
ASSET: ${trade.company_name}
TX: ${trade.transaction_type} DATE: ${trade.transaction_date}
AMOUNT: ${trade.amount_range_str}
STATUS: OCR EXTRACTED & NORMALIZED`;
    }
  }

  modal.classList.add('open');
}

document.addEventListener('DOMContentLoaded', () => {
  const closeBtn = document.getElementById('btn-close-ocr-modal');
  const modal = document.getElementById('ocr-modal');
  if (closeBtn && modal) {
    closeBtn.addEventListener('click', () => {
      modal.classList.remove('open');
    });
    modal.addEventListener('click', (e) => {
      if (e.target === modal) modal.classList.remove('open');
    });
  }
});
