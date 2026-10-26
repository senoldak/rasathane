// ==============================================================================
// CAPITOLSEEDER // CHART.JS VISUALIZATION ENGINE
// ==============================================================================

let portfolioChart = null;

function renderPortfolioChart(portfolioCurve, benchmarkCurve) {
  const canvas = document.getElementById('portfolio-chart');
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  if (portfolioChart) {
    portfolioChart.destroy();
  }

  const labels = portfolioCurve.map(pt => pt.date);
  const portData = portfolioCurve.map(pt => pt.value);
  const benchData = benchmarkCurve.map(pt => pt.value);

  portfolioChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [
        {
          label: 'Shadow Portfolio (Copycat on Disclosure)',
          data: portData,
          borderColor: '#f59e0b', // Alpha Gold
          backgroundColor: 'rgba(245, 158, 11, 0.08)',
          borderWidth: 2.5,
          tension: 0.3,
          fill: true,
          pointBackgroundColor: '#f59e0b',
          pointRadius: 4
        },
        {
          label: 'S&P 500 Benchmark ($SPY)',
          data: benchData,
          borderColor: '#64748b', // Slate Gray
          backgroundColor: 'transparent',
          borderWidth: 1.8,
          borderDash: [5, 5],
          tension: 0.3,
          fill: false,
          pointBackgroundColor: '#64748b',
          pointRadius: 3
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: 'index',
        intersect: false
      },
      plugins: {
        legend: {
          position: 'top',
          labels: {
            color: '#94a3b8',
            font: { family: 'JetBrains Mono', size: 11 }
          }
        },
        tooltip: {
          backgroundColor: '#131b2e',
          borderColor: '#1e293b',
          borderWidth: 1,
          titleColor: '#f8fafc',
          bodyColor: '#94a3b8',
          titleFont: { family: 'JetBrains Mono' },
          bodyFont: { family: 'JetBrains Mono' },
          callbacks: {
            label: function(context) {
              let label = context.dataset.label || '';
              if (label) label += ': ';
              if (context.parsed.y !== null) {
                label += new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(context.parsed.y);
              }
              return label;
            }
          }
        }
      },
      scales: {
        x: {
          grid: { color: 'rgba(30, 41, 59, 0.4)' },
          ticks: { color: '#64748b', font: { family: 'JetBrains Mono', size: 10 } }
        },
        y: {
          grid: { color: 'rgba(30, 41, 59, 0.4)' },
          ticks: {
            color: '#64748b',
            font: { family: 'JetBrains Mono', size: 10 },
            callback: function(value) {
              return '$' + (value / 1000) + 'k';
            }
          }
        }
      }
    }
  });
}
