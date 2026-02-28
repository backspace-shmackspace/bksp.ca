/**
 * charts.js — Chart.js initialization for the LinkedIn Analytics dashboard.
 *
 * Exported functions (called from inline scripts in templates):
 *   initDashboard(config)   - Main dashboard charts
 *   initPostDetail(config)  - Post detail page charts
 *   initAudience(config)    - Audience demographics charts
 */

// ---------------------------------------------------------------------------
// Global Chart.js defaults (dark theme)
// ---------------------------------------------------------------------------

Chart.defaults.color = "#94a3b8";           // text-muted
Chart.defaults.borderColor = "rgba(255,255,255,0.05)";
Chart.defaults.font.family = "'Inter', system-ui, sans-serif";
Chart.defaults.font.size = 11;

const COLORS = {
  accent:  "#3b82f6",
  success: "#22c55e",
  warning: "#f59e0b",
  danger:  "#ef4444",
  muted:   "#475569",
  palette: [
    "#3b82f6", "#22c55e", "#f59e0b", "#ef4444",
    "#a855f7", "#06b6d4", "#f97316", "#84cc16",
  ],
};

function commonLineOptions(yLabel) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: "#111827",
        borderColor: "rgba(255,255,255,0.1)",
        borderWidth: 1,
        padding: 10,
        titleColor: "#f1f5f9",
        bodyColor: "#94a3b8",
      },
    },
    scales: {
      x: {
        grid: { color: "rgba(255,255,255,0.04)" },
        ticks: { maxTicksLimit: 8 },
      },
      y: {
        grid: { color: "rgba(255,255,255,0.04)" },
        beginAtZero: true,
        title: yLabel
          ? { display: true, text: yLabel, color: "#64748b", font: { size: 10 } }
          : { display: false },
      },
    },
  };
}

function commonBarOptions() {
  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: "#111827",
        borderColor: "rgba(255,255,255,0.1)",
        borderWidth: 1,
        padding: 10,
        titleColor: "#f1f5f9",
        bodyColor: "#94a3b8",
      },
    },
    scales: {
      x: { grid: { display: false }, ticks: { maxRotation: 30 } },
      y: {
        grid: { color: "rgba(255,255,255,0.04)" },
        beginAtZero: true,
      },
    },
  };
}

function commonDoughnutOptions() {
  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: "right",
        labels: {
          boxWidth: 12,
          padding: 12,
          color: "#94a3b8",
        },
      },
      tooltip: {
        backgroundColor: "#111827",
        borderColor: "rgba(255,255,255,0.1)",
        borderWidth: 1,
        padding: 10,
        titleColor: "#f1f5f9",
        bodyColor: "#94a3b8",
        callbacks: {
          label: (ctx) => ` ${ctx.parsed.toFixed(1)}%`,
        },
      },
    },
  };
}

// ---------------------------------------------------------------------------
// Dashboard page
// ---------------------------------------------------------------------------

let impressionsChartInstance = null;

async function fetchTimeseries(metric, days) {
  const resp = await fetch(`/api/metrics/timeseries?metric=${metric}&days=${days}`);
  if (!resp.ok) throw new Error(`API error: ${resp.status}`);
  return resp.json();
}

function renderImpressionsChart(labels, values) {
  const ctx = document.getElementById("impressionsChart");
  if (!ctx) return;

  if (impressionsChartInstance) {
    impressionsChartInstance.destroy();
  }

  impressionsChartInstance = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Impressions",
          data: values,
          borderColor: COLORS.accent,
          backgroundColor: "rgba(59,130,246,0.08)",
          borderWidth: 2,
          pointRadius: labels.length > 60 ? 0 : 3,
          pointHoverRadius: 5,
          fill: true,
          tension: 0.3,
        },
      ],
    },
    options: commonLineOptions(),
  });
}

function renderEngagementBarChart(labels, values) {
  const ctx = document.getElementById("engagementChart");
  if (!ctx) return;

  const pctValues = values.map((v) => parseFloat((v * 100).toFixed(2)));

  new Chart(ctx, {
    type: "bar",
    data: {
      labels: labels.map((l) => l ? l.substring(0, 30) + (l.length > 30 ? "…" : "") : "(no title)"),
      datasets: [
        {
          label: "Engagement Rate (%)",
          data: pctValues,
          backgroundColor: pctValues.map((v) =>
            v >= 5 ? COLORS.success : v >= 2 ? COLORS.warning : COLORS.muted
          ),
          borderRadius: 3,
        },
      ],
    },
    options: commonBarOptions(),
  });
}

async function initDashboard(config) {
  // Impressions time series chart with metric switcher
  const { days, postLabels, postEngagement } = config;

  async function loadMetric(metric) {
    try {
      const data = await fetchTimeseries(metric, days);
      renderImpressionsChart(data.labels, data.values);
    } catch (e) {
      console.error("Failed to load timeseries:", e);
    }
  }

  // Metric tab buttons
  document.querySelectorAll(".metric-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".metric-btn").forEach((b) => {
        b.classList.remove("bg-accent", "text-white");
        b.classList.add("bg-white/5", "text-text-muted");
      });
      btn.classList.add("bg-accent", "text-white");
      btn.classList.remove("bg-white/5", "text-text-muted");
      loadMetric(btn.dataset.metric);
    });
  });

  // Initial load
  await loadMetric("impressions");

  // Engagement bar chart (server-rendered data)
  renderEngagementBarChart(postLabels, postEngagement);
}

// ---------------------------------------------------------------------------
// Post detail page
// ---------------------------------------------------------------------------

function initPostDetail(config) {
  const { dailyLabels, dailyValues } = config;

  // Daily trend line (if available)
  if (dailyLabels && dailyLabels.length > 0) {
    const dailyCtx = document.getElementById("postDailyChart");
    if (dailyCtx) {
      new Chart(dailyCtx, {
        type: "line",
        data: {
          labels: dailyLabels,
          datasets: [
            {
              label: "Daily Impressions",
              data: dailyValues,
              borderColor: COLORS.accent,
              backgroundColor: "rgba(59,130,246,0.08)",
              borderWidth: 2,
              pointRadius: 3,
              fill: true,
              tension: 0.3,
            },
          ],
        },
        options: commonLineOptions("Impressions"),
      });
    }
  }
}

// ---------------------------------------------------------------------------
// Audience page
// ---------------------------------------------------------------------------

function makeDoughnutChart(canvasId, labels, values) {
  const ctx = document.getElementById(canvasId);
  if (!ctx || !labels || labels.length === 0) return;

  new Chart(ctx, {
    type: "doughnut",
    data: {
      labels,
      datasets: [
        {
          data: values,
          backgroundColor: COLORS.palette.slice(0, labels.length),
          borderWidth: 0,
          hoverOffset: 6,
        },
      ],
    },
    options: commonDoughnutOptions(),
  });
}

function initAudience(config) {
  const { followerLabels, followerTotals, industry, jobTitle, seniority, location } = config;

  // Follower growth line chart
  if (followerLabels && followerLabels.length > 0) {
    const followerCtx = document.getElementById("followerChart");
    if (followerCtx) {
      new Chart(followerCtx, {
        type: "line",
        data: {
          labels: followerLabels,
          datasets: [
            {
              label: "Total Followers",
              data: followerTotals,
              borderColor: COLORS.accent,
              backgroundColor: "rgba(59,130,246,0.08)",
              borderWidth: 2,
              pointRadius: followerLabels.length > 60 ? 0 : 3,
              fill: true,
              tension: 0.3,
            },
          ],
        },
        options: commonLineOptions("Followers"),
      });
    }
  }

  // Demographic doughnut charts
  makeDoughnutChart("industryChart", industry.labels, industry.values);
  makeDoughnutChart("jobTitleChart", jobTitle.labels, jobTitle.values);
  makeDoughnutChart("seniorityChart", seniority.labels, seniority.values);
  makeDoughnutChart("locationChart", location.labels, location.values);
}
