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

// ---------------------------------------------------------------------------
// Analytics page
// ---------------------------------------------------------------------------

async function initAnalytics(config) {
  const { defaultDays = 365 } = config;

  // -------------------------------------------------------------------------
  // Load engagement data and render charts
  // -------------------------------------------------------------------------

  let engagementData = null;

  try {
    const resp = await fetch(`/api/analytics/engagement?days=${defaultDays}`);
    if (!resp.ok) throw new Error(`API error: ${resp.status}`);
    engagementData = await resp.json();
  } catch (e) {
    console.error("Failed to load engagement analytics:", e);
    return;
  }

  const { posts, monthly_medians, top_10pct_threshold, baseline, last_30d } = engagementData;

  // -------------------------------------------------------------------------
  // KPI cards: baseline vs last 30 days
  // -------------------------------------------------------------------------

  function deltaIndicator(current, baseline) {
    if (baseline === 0) return "";
    const diff = current - baseline;
    const pct = ((diff / baseline) * 100).toFixed(1);
    if (diff > 0) {
      return `<span class="text-success text-xs ml-1">&#9650; ${pct}%</span>`;
    } else if (diff < 0) {
      return `<span class="text-danger text-xs ml-1">&#9660; ${Math.abs(pct)}%</span>`;
    }
    return `<span class="text-text-dim text-xs ml-1">=</span>`;
  }

  function kpiCard(label, baselineVal, last30Val, formatter) {
    return `
      <div class="bg-card rounded-xl border border-white/5 p-4">
        <div class="text-xs text-text-dim mb-2">${label}</div>
        <div class="flex items-end gap-2 mb-2">
          <span class="text-xl font-mono font-semibold text-text">${formatter(last30Val)}</span>
          ${deltaIndicator(last30Val, baselineVal)}
        </div>
        <div class="text-xs text-text-dim">
          All-time avg: <span class="text-text-muted font-mono">${formatter(baselineVal)}</span>
        </div>
      </div>
    `;
  }

  const kpiEl = document.getElementById("kpiCards");
  if (kpiEl) {
    const pct = (v) => (v * 100).toFixed(2) + "%";
    const ws  = (v) => v.toFixed(4);
    kpiEl.innerHTML =
      kpiCard("Engagement Rate (last 30d)", baseline.avg_engagement_rate, last_30d.avg_engagement_rate, pct) +
      kpiCard("Weighted Score (last 30d)", baseline.avg_weighted_score, last_30d.avg_weighted_score, ws) +
      kpiCard("Posts (last 30d)", baseline.post_count, last_30d.post_count, (v) => String(v)) +
      `<div class="bg-card rounded-xl border border-white/5 p-4">
        <div class="text-xs text-text-dim mb-2">Top 10% Threshold</div>
        <div class="text-xl font-mono font-semibold text-warning">${(top_10pct_threshold * 100).toFixed(2)}%</div>
        <div class="text-xs text-text-dim mt-2">Engagement rate to reach top 10%</div>
      </div>`;
  }

  // -------------------------------------------------------------------------
  // Engagement rate over time + rolling avg + threshold line
  // -------------------------------------------------------------------------

  const timeCtx = document.getElementById("engagementTimeChart");
  if (timeCtx && posts.length > 0) {
    const labels = posts.map((p) => p.post_date);
    const erValues = posts.map((p) => parseFloat((p.engagement_rate * 100).toFixed(4)));
    const rollingValues = posts.map((p) => parseFloat((p.rolling_avg_5 * 100).toFixed(4)));
    const thresholdValues = labels.map(() => parseFloat((top_10pct_threshold * 100).toFixed(4)));

    new Chart(timeCtx, {
      type: "line",
      data: {
        labels,
        datasets: [
          {
            label: "Engagement Rate (%)",
            data: erValues,
            borderColor: COLORS.accent,
            backgroundColor: "rgba(59,130,246,0.06)",
            borderWidth: 2,
            pointRadius: 4,
            pointHoverRadius: 6,
            fill: true,
            tension: 0.3,
            order: 1,
          },
          {
            label: "5-Post Rolling Avg (%)",
            data: rollingValues,
            borderColor: COLORS.success,
            backgroundColor: "transparent",
            borderWidth: 2,
            pointRadius: 0,
            pointHoverRadius: 4,
            fill: false,
            tension: 0.4,
            order: 2,
          },
          {
            label: "Top 10% Threshold (%)",
            data: thresholdValues,
            borderColor: COLORS.warning,
            borderDash: [6, 4],
            borderWidth: 1,
            pointRadius: 0,
            fill: false,
            tension: 0,
            order: 3,
          },
        ],
      },
      options: {
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
            callbacks: {
              label: (ctx) => ` ${ctx.dataset.label}: ${ctx.parsed.y.toFixed(2)}%`,
            },
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
            title: { display: true, text: "Engagement Rate (%)", color: "#64748b", font: { size: 10 } },
          },
        },
      },
    });
  } else if (timeCtx) {
    timeCtx.parentElement.innerHTML =
      '<p class="text-center text-text-dim text-xs py-16">Not enough data to render chart.</p>';
  }

  // -------------------------------------------------------------------------
  // Monthly median bar chart
  // -------------------------------------------------------------------------

  const monthCtx = document.getElementById("monthlyMedianChart");
  if (monthCtx && monthly_medians.length > 0) {
    const mLabels = monthly_medians.map((m) => m.month);
    const mValues = monthly_medians.map((m) => parseFloat((m.median_engagement_rate * 100).toFixed(4)));
    const mCounts = monthly_medians.map((m) => m.post_count);

    new Chart(monthCtx, {
      type: "bar",
      data: {
        labels: mLabels,
        datasets: [
          {
            label: "Median Engagement Rate (%)",
            data: mValues,
            backgroundColor: "rgba(59,130,246,0.6)",
            borderColor: COLORS.accent,
            borderWidth: 1,
            borderRadius: 3,
          },
        ],
      },
      options: {
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
            callbacks: {
              label: (ctx) => ` Median: ${ctx.parsed.y.toFixed(2)}%`,
              afterLabel: (ctx) => ` Posts: ${mCounts[ctx.dataIndex]}`,
            },
          },
        },
        scales: {
          x: { grid: { display: false }, ticks: { maxRotation: 30 } },
          y: {
            grid: { color: "rgba(255,255,255,0.04)" },
            beginAtZero: true,
            title: { display: true, text: "Median Engagement (%)", color: "#64748b", font: { size: 10 } },
          },
        },
      },
    });
  } else if (monthCtx) {
    monthCtx.parentElement.innerHTML =
      '<p class="text-center text-text-dim text-xs py-12">Not enough data to render chart.</p>';
  }

  // -------------------------------------------------------------------------
  // Cohort breakdown table
  // -------------------------------------------------------------------------

  async function loadCohorts(dimension) {
    const tbody = document.getElementById("cohortTableBody");
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="6" class="py-6 text-center text-text-dim text-xs">Loading...</td></tr>';
    try {
      const resp = await fetch(`/api/analytics/cohorts?dimension=${dimension}`);
      if (!resp.ok) throw new Error(`API error: ${resp.status}`);
      const data = await resp.json();
      if (data.cohorts.length === 0) {
        tbody.innerHTML =
          '<tr><td colspan="6" class="py-6 text-center text-text-dim text-xs">No tagged posts for this dimension yet.</td></tr>';
        return;
      }
      tbody.innerHTML = data.cohorts
        .map(
          (c) => `
          <tr class="text-sm">
            <td class="py-2.5 pr-4 font-mono text-xs text-text">${c.value}</td>
            <td class="py-2.5 pr-4 text-right text-text-muted">${c.post_count}</td>
            <td class="py-2.5 pr-4 text-right font-mono text-xs
                       ${c.avg_engagement_rate >= 0.05 ? "text-success" : c.avg_engagement_rate >= 0.02 ? "text-warning" : "text-text-muted"}">
              ${(c.avg_engagement_rate * 100).toFixed(2)}%
            </td>
            <td class="py-2.5 pr-4 text-right font-mono text-xs text-text-muted">
              ${c.avg_weighted_score.toFixed(4)}
            </td>
            <td class="py-2.5 pr-4 text-right font-mono text-xs text-text-muted">
              ${(c.median_engagement_rate * 100).toFixed(2)}%
            </td>
            <td class="py-2.5 text-xs text-text-muted truncate max-w-xs">
              <a href="/dashboard/posts/${c.best_post_id}" class="hover:text-accent transition-colors">
                ${c.best_post_title}
              </a>
            </td>
          </tr>`
        )
        .join("");
    } catch (e) {
      tbody.innerHTML =
        '<tr><td colspan="6" class="py-6 text-center text-danger text-xs">Failed to load cohort data.</td></tr>';
      console.error("Failed to load cohorts:", e);
    }
  }

  const dimensionSelect = document.getElementById("cohortDimension");
  if (dimensionSelect) {
    dimensionSelect.addEventListener("change", () => {
      loadCohorts(dimensionSelect.value);
    });
    await loadCohorts(dimensionSelect.value);
  }
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
