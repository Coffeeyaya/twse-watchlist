// No build step by design (plan.md) — plain fetch + DOM, served directly by GitHub Pages.

// ?branch=<name> previews a feature branch's data straight from GitHub — no clone, no login
// (raw.githubusercontent.com serves public-repo content unauthenticated). Lets you check a
// branch's actual output without merging it first. See routine.html for the branch list.
const GITHUB_REPO = "Coffeeyaya/twse-watchlist";
const PREVIEW_BRANCH = new URLSearchParams(window.location.search).get("branch");
const RAW_BASE = PREVIEW_BRANCH
  ? `https://raw.githubusercontent.com/${GITHUB_REPO}/${encodeURIComponent(PREVIEW_BRANCH)}`
  : null;

const DATA_URL = RAW_BASE ? `${RAW_BASE}/data/dashboard.json` : "../data/dashboard.json";
const HISTORY_URL = (code) =>
  RAW_BASE ? `${RAW_BASE}/data/history/${code}.json` : `../data/history/${code}.json`;

let allStocks = [];
let sortKey = "code";
let sortDir = 1;
let chart = null;

const els = {
  disclaimer: document.getElementById("disclaimer"),
  updated: document.getElementById("updated"),
  search: document.getElementById("search"),
  resultCount: document.getElementById("result-count"),
  tbody: document.getElementById("stock-table-body"),
  table: document.getElementById("stock-table"),
  branchBanner: document.getElementById("branch-banner"),
  overlay: document.getElementById("detail-overlay"),
  detailClose: document.getElementById("detail-close"),
  detailTitle: document.getElementById("detail-title"),
  detailSub: document.getElementById("detail-sub"),
  detailChart: document.getElementById("detail-chart"),
  detailLabels: document.getElementById("detail-labels"),
  filters: {
    goldenCross: document.getElementById("filter-golden-cross"),
    deathCross: document.getElementById("filter-death-cross"),
    oversold: document.getElementById("filter-oversold"),
    overbought: document.getElementById("filter-overbought"),
    cheap: document.getElementById("filter-cheap"),
  },
};

async function init() {
  if (PREVIEW_BRANCH) {
    els.branchBanner.textContent = `正在看 branch「${PREVIEW_BRANCH}」的資料，不是 main（正式版）— 回 index.html 看正式資料`;
    els.branchBanner.classList.remove("hidden");
  }
  try {
    const res = await fetch(DATA_URL);
    const data = await res.json();
    allStocks = data.stocks;
    els.disclaimer.textContent = data.disclaimer;
    els.updated.textContent = `最後更新：${formatDateTime(data.generated_at)}（共 ${data.stock_count} 檔）`;
    render();
  } catch (err) {
    els.disclaimer.textContent = "資料載入失敗，請稍後再試。";
    console.error(err);
  }
}

function formatDateTime(iso) {
  const d = new Date(iso);
  return d.toLocaleString("zh-TW", { hour12: false });
}

function matchesFilters(stock) {
  const q = els.search.value.trim().toLowerCase();
  if (q && !stock.code.toLowerCase().includes(q) && !(stock.name || "").toLowerCase().includes(q)) {
    return false;
  }
  const f = els.filters;
  const cross = stock.indicators?.ma_cross?.state;
  const rsi = stock.indicators?.rsi14;
  if (f.goldenCross.checked && cross !== "golden_cross") return false;
  if (f.deathCross.checked && cross !== "death_cross") return false;
  if (f.oversold.checked && !(rsi !== null && rsi !== undefined && rsi <= 30)) return false;
  if (f.overbought.checked && !(rsi !== null && rsi !== undefined && rsi >= 70)) return false;
  if (f.cheap.checked) {
    const pe = stock.labels?.pe_percentile;
    const pb = stock.labels?.pb_percentile;
    const isCheap = (pe !== null && pe !== undefined && pe <= 20) ||
                     (pb !== null && pb !== undefined && pb <= 20);
    if (!isCheap) return false;
  }
  return true;
}

function sortedFiltered() {
  const filtered = allStocks.filter(matchesFilters);
  filtered.sort((a, b) => {
    const av = valueForSort(a, sortKey);
    const bv = valueForSort(b, sortKey);
    if (av === null || av === undefined) return 1;
    if (bv === null || bv === undefined) return -1;
    if (typeof av === "string") return sortDir * av.localeCompare(bv, "zh-Hant");
    return sortDir * (av - bv);
  });
  return filtered;
}

function valueForSort(stock, key) {
  if (key === "rsi14") return stock.indicators?.rsi14;
  return stock[key];
}

function render() {
  const rows = sortedFiltered();
  els.resultCount.textContent = `顯示 ${rows.length} / ${allStocks.length} 檔`;
  els.tbody.innerHTML = rows.map(rowHtml).join("");
  [...els.tbody.children].forEach((tr, i) => {
    tr.addEventListener("click", () => openDetail(rows[i]));
  });
}

function rowHtml(s) {
  const changeClass = s.change > 0 ? "up" : s.change < 0 ? "down" : "";
  const changeStr = s.change === null || s.change === undefined ? "—" : (s.change > 0 ? "+" : "") + s.change;
  const rsi = s.indicators?.rsi14;
  const tags = [];
  const cross = s.indicators?.ma_cross?.state;
  if (cross === "golden_cross") tags.push('<span class="tag">黃金交叉</span>');
  if (cross === "death_cross") tags.push('<span class="tag">死亡交叉</span>');
  const valuationTags = [s.labels?.pe_label, s.labels?.pb_label]
    .filter((t) => t && t !== "相對自身歷史中等水準")
    .map((t) => `<span class="tag">${t}</span>`);

  return `<tr>
    <td>${s.code}</td>
    <td>${s.name ?? ""}</td>
    <td>${fmt(s.close)}</td>
    <td class="${changeClass}">${changeStr}</td>
    <td>${fmt(s.pe)}</td>
    <td>${fmt(s.pb)}</td>
    <td>${fmt(s.dividend_yield, "%")}</td>
    <td>${fmt(rsi)}</td>
    <td>${tags.join("") || "—"}</td>
    <td>${valuationTags.join("") || "—"}</td>
  </tr>`;
}

function fmt(v, suffix = "") {
  if (v === null || v === undefined) return "—";
  return v + suffix;
}

async function openDetail(stock) {
  els.overlay.classList.remove("hidden");
  els.detailTitle.textContent = `${stock.code} ${stock.name ?? ""}`;
  els.detailSub.textContent = `資料日期：${stock.date ?? "—"}｜歷史資料 ${stock.labels?.lookback_days ?? 0} 天（自 ${stock.labels?.lookback_start_date ?? "—"}）`;

  const labelLines = [
    stock.labels?.ma_cross_label,
    stock.labels?.rsi_label,
    stock.labels?.pe_label && `本益比：${stock.labels.pe_label}（百分位 ${stock.labels.pe_percentile}）`,
    stock.labels?.pb_label && `股價淨值比：${stock.labels.pb_label}（百分位 ${stock.labels.pb_percentile}）`,
    stock.labels?.dividend_yield_label && `殖利率：${stock.labels.dividend_yield_label}（百分位 ${stock.labels.dividend_yield_percentile}）`,
  ].filter(Boolean);
  els.detailLabels.innerHTML = labelLines.map((l) => `<div>${l}</div>`).join("");

  try {
    const res = await fetch(HISTORY_URL(stock.code));
    const history = await res.json();
    drawChart(history);
  } catch (err) {
    console.error("history fetch failed", err);
  }
}

function drawChart(history) {
  const ctx = els.detailChart.getContext("2d");
  if (chart) chart.destroy();
  chart = new Chart(ctx, {
    type: "line",
    data: {
      labels: history.map((r) => r.date),
      datasets: [
        {
          label: "收盤價",
          data: history.map((r) => r.close),
          borderColor: "#4f9dde",
          backgroundColor: "transparent",
          pointRadius: 0,
          tension: 0.1,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { maxTicksLimit: 8, color: "#8b98a5" }, grid: { color: "#2a333b" } },
        y: { ticks: { color: "#8b98a5" }, grid: { color: "#2a333b" } },
      },
    },
  });
}

function closeDetail() {
  els.overlay.classList.add("hidden");
}

els.detailClose.addEventListener("click", closeDetail);
els.overlay.addEventListener("click", (e) => {
  if (e.target === els.overlay) closeDetail();
});
els.search.addEventListener("input", render);
Object.values(els.filters).forEach((el) => el.addEventListener("change", render));
els.table.querySelectorAll("th[data-sort]").forEach((th) => {
  th.addEventListener("click", () => {
    const key = th.dataset.sort;
    if (sortKey === key) sortDir *= -1;
    else { sortKey = key; sortDir = 1; }
    render();
  });
});

init();
