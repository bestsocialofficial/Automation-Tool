/* Keyword Ranking Dashboard frontend. Fetches /api/dashboard and renders. */

const state = {
  data: null,
  sort: { key: "position", dir: "asc" },
  filters: { search: "", intent: "", bucket: "" },
  charts: {},
};

// Instant paint; also avoids requestAnimationFrame stalls in background tabs.
Chart.defaults.animation = false;

const ACCENT = "#4f5df0";
const GREEN = "#14893c";
const RED = "#cc3340";
const PALETTE = ["#4f5df0", "#14893c", "#e8a13c", "#cc3340", "#7a5df0", "#2aa8b8"];

const $ = (sel) => document.querySelector(sel);

async function load(domain) {
  const url = domain
    ? `/api/dashboard?domain=${encodeURIComponent(domain)}`
    : "/api/dashboard";
  const res = await fetch(url);
  if (res.status === 401) {
    window.location = "/login";
    return;
  }
  const data = await res.json();
  state.data = data;

  if (data.empty || !data.keywords || data.keywords.length === 0) {
    $("#app").classList.add("hidden");
    $("#empty-state").classList.remove("hidden");
    return;
  }
  $("#empty-state").classList.add("hidden");
  $("#app").classList.remove("hidden");
  renderAll();
}

function renderAll() {
  const d = state.data;
  renderHeader(d);
  renderKpis(d.kpis);
  renderTrendCharts(d.trend);
  renderMovers(d.winners, d.losers);
  renderBuckets(d.buckets);
  renderIntents(d.intents);
  populateFilters(d);
  renderTable();
}

/* ---------- header ---------- */

function renderHeader(d) {
  const select = $("#domain-select");
  select.innerHTML = "";
  d.domains.forEach((dom) => {
    const opt = document.createElement("option");
    opt.value = dom;
    opt.textContent = dom;
    if (dom === d.domain) opt.selected = true;
    select.appendChild(opt);
  });

  $("#last-updated").textContent = d.last_updated
    ? `Last updated: ${d.last_updated}`
    : "";

  const badge = $("#market-badge");
  if (d.database) {
    badge.textContent = `Google ${d.database.toUpperCase()}`;
    badge.classList.remove("hidden");
  } else {
    badge.classList.add("hidden");
  }
}

/* ---------- KPI cards ---------- */

function deltaChip(value, { suffix = "", flatText = "no change" } = {}) {
  if (value === null || value === undefined) return "";
  const cls = value > 0 ? "up" : value < 0 ? "down" : "flat";
  const arrow = value > 0 ? "▲" : value < 0 ? "▼" : "";
  const text =
    value === 0 ? flatText : `${arrow} ${Math.abs(value)}${suffix} vs last fetch`;
  return `<span class="delta ${cls}">${text}</span>`;
}

function renderKpis(k) {
  const cards = [
    { label: "Keywords in top 3", value: k.top3, delta: deltaChip(k.deltas.top3) },
    { label: "Keywords in top 10", value: k.top10, delta: deltaChip(k.deltas.top10) },
    {
      label: "Average position",
      value: k.avg_position ?? "—",
      delta: deltaChip(k.deltas.avg_position),
    },
    {
      label: "Keywords tracked",
      value: `${k.ranking}/${k.total_keywords}`,
      sub: "ranking / tracked",
    },
    {
      label: "Total search volume",
      value: k.total_volume.toLocaleString("en-IN"),
      sub: "monthly searches targeted",
    },
  ];
  $("#kpi-grid").innerHTML = cards
    .map(
      (c) => `
      <div class="kpi">
        <div class="label">${c.label}</div>
        <div class="value">${c.value}</div>
        ${c.delta || (c.sub ? `<span class="delta flat">${c.sub}</span>` : "")}
      </div>`
    )
    .join("");
}

/* ---------- charts ---------- */

function destroyChart(name) {
  if (state.charts[name]) {
    state.charts[name].destroy();
    delete state.charts[name];
  }
}

function renderTrendCharts(trend) {
  const labels = trend.map((t) => t.date);

  destroyChart("avg");
  state.charts.avg = new Chart($("#chart-avg"), {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Avg position",
          data: trend.map((t) => t.avg_position),
          borderColor: ACCENT,
          backgroundColor: ACCENT + "22",
          fill: true,
          tension: 0.3,
          spanGaps: true,
        },
      ],
    },
    options: {
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        y: { reverse: true, title: { display: true, text: "Position (lower is better)" } },
      },
    },
  });

  destroyChart("top10");
  state.charts.top10 = new Chart($("#chart-top10"), {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "Top 10",
          data: trend.map((t) => t.top10),
          backgroundColor: GREEN + "cc",
          borderRadius: 4,
        },
        {
          label: "Top 3",
          data: trend.map((t) => t.top3),
          backgroundColor: ACCENT + "cc",
          borderRadius: 4,
        },
      ],
    },
    options: {
      maintainAspectRatio: false,
      scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
    },
  });
}

function renderBuckets(buckets) {
  destroyChart("buckets");
  state.charts.buckets = new Chart($("#chart-buckets"), {
    type: "bar",
    data: {
      labels: Object.keys(buckets),
      datasets: [
        {
          data: Object.values(buckets),
          backgroundColor: [ACCENT, "#7a5df0", "#e8a13c", "#e07b39", RED, "#9aa4b8"],
          borderRadius: 4,
        },
      ],
    },
    options: {
      indexAxis: "y",
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { x: { beginAtZero: true, ticks: { precision: 0 } } },
    },
  });
}

function renderIntents(intents) {
  destroyChart("intents");
  state.charts.intents = new Chart($("#chart-intents"), {
    type: "doughnut",
    data: {
      labels: Object.keys(intents),
      datasets: [{ data: Object.values(intents), backgroundColor: PALETTE }],
    },
    options: {
      maintainAspectRatio: false,
      plugins: { legend: { position: "right" } },
    },
  });
}

/* ---------- movers ---------- */

function moverChip(m) {
  if (m.is_new) return `<span class="chip new">New</span>`;
  if (m.change > 0) return `<span class="chip up">▲ ${m.change}</span>`;
  return `<span class="chip down">▼ ${Math.abs(m.change)}</span>`;
}

function renderMovers(winners, losers) {
  const render = (list, el, emptyText) => {
    el.innerHTML = list.length
      ? list
          .map(
            (m) => `
        <li>
          <span>${escapeHtml(m.keyword)}</span>
          <span class="mover-pos">#${m.position ?? "—"} ${moverChip(m)}</span>
        </li>`
          )
          .join("")
      : `<li class="none">${emptyText}</li>`;
  };
  render(winners, $("#winners"), "No improvements since last fetch");
  render(losers, $("#losers"), "No declines since last fetch — nice!");
}

/* ---------- table ---------- */

function populateFilters(d) {
  const intents = new Set();
  d.keywords.forEach((k) => {
    const val = k.search_intent;
    (Array.isArray(val) ? val : [val]).forEach((i) => i && intents.add(i));
  });
  const intentSel = $("#intent-filter");
  intentSel.innerHTML = '<option value="">All intents</option>';
  [...intents].sort().forEach((i) => {
    intentSel.insertAdjacentHTML("beforeend", `<option value="${i}">${i}</option>`);
  });

  const bucketSel = $("#bucket-filter");
  bucketSel.innerHTML = '<option value="">All positions</option>';
  Object.keys(d.buckets).forEach((b) => {
    bucketSel.insertAdjacentHTML("beforeend", `<option value="${b}">${b}</option>`);
  });
}

function visibleKeywords() {
  const { search, intent, bucket } = state.filters;
  let rows = state.data.keywords.filter((k) => {
    if (search && !k.keyword.toLowerCase().includes(search)) return false;
    if (bucket && k.bucket !== bucket) return false;
    if (intent) {
      const val = Array.isArray(k.search_intent) ? k.search_intent : [k.search_intent];
      if (!val.includes(intent)) return false;
    }
    return true;
  });

  const { key, dir } = state.sort;
  const mul = dir === "asc" ? 1 : -1;
  rows.sort((a, b) => {
    let av = a[key], bv = b[key];
    if (Array.isArray(av)) av = av.join(",");
    if (Array.isArray(bv)) bv = bv.join(",");
    // Nulls always sink to the bottom regardless of direction.
    if (av === null || av === undefined) return 1;
    if (bv === null || bv === undefined) return -1;
    if (typeof av === "string") return av.localeCompare(bv) * mul;
    return (av - bv) * mul;
  });
  return rows;
}

function changeCell(k) {
  if (k.is_new) return `<span class="chip new">New</span>`;
  if (k.change === null || k.change === undefined)
    return `<span class="chip na">—</span>`;
  if (k.change > 0) return `<span class="chip up">▲ ${k.change}</span>`;
  if (k.change < 0) return `<span class="chip down">▼ ${Math.abs(k.change)}</span>`;
  return `<span class="chip na">0</span>`;
}

function renderTable() {
  const rows = visibleKeywords();
  const tbody = $("#kw-table tbody");
  tbody.innerHTML = rows
    .map(
      (k, i) => `
    <tr data-kw="${escapeHtml(k.keyword)}">
      <td>${escapeHtml(k.keyword)}</td>
      <td class="num">${
        k.position !== null
          ? `<span class="pos-strong">${k.position}</span>`
          : `<span class="chip na">Not in top 100</span>`
      }</td>
      <td class="num">${changeCell(k)}</td>
      <td class="num">${k.search_volume?.toLocaleString("en-IN") ?? "—"}</td>
      <td class="num">${k.traffic ?? "—"}</td>
      <td class="num">${k.keyword_difficulty ?? "—"}</td>
      <td>${
        Array.isArray(k.search_intent)
          ? k.search_intent.join(", ")
          : k.search_intent ?? "—"
      }</td>
      <td class="num">${k.vi ?? "—"}</td>
    </tr>`
    )
    .join("");

  document.querySelectorAll("#kw-table th").forEach((th) => {
    th.classList.remove("sorted-asc", "sorted-desc");
    if (th.dataset.sort === state.sort.key) {
      th.classList.add(state.sort.dir === "asc" ? "sorted-asc" : "sorted-desc");
    }
  });
}

/* ---------- keyword history modal ---------- */

function openModal(keyword) {
  const k = state.data.keywords.find((x) => x.keyword === keyword);
  if (!k) return;
  $("#modal-title").textContent = `"${k.keyword}" — position history`;
  $("#modal").classList.remove("hidden");

  destroyChart("history");
  state.charts.history = new Chart($("#chart-history"), {
    type: "line",
    data: {
      labels: k.history.map((h) => h.date),
      datasets: [
        {
          label: "Position",
          data: k.history.map((h) => h.position),
          borderColor: ACCENT,
          backgroundColor: ACCENT + "22",
          fill: true,
          tension: 0.25,
          spanGaps: false,
          pointRadius: 4,
        },
      ],
    },
    options: {
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        y: {
          reverse: true,
          suggestedMin: 1,
          ticks: { precision: 0 },
          title: { display: true, text: "Position (lower is better)" },
        },
      },
    },
  });
}

function closeModal() {
  $("#modal").classList.add("hidden");
  destroyChart("history");
}

/* ---------- utils / events ---------- */

function escapeHtml(str) {
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

async function loadMe() {
  const res = await fetch("/api/me");
  if (!res.ok) return;
  const me = await res.json();
  $("#user-chip").textContent = `Signed in: ${me.username}`;
}

document.addEventListener("DOMContentLoaded", () => {
  $("#domain-select").addEventListener("change", (e) => load(e.target.value));

  $("#btn-excel").addEventListener("click", () => {
    const domain = state.data ? state.data.domain : "";
    window.location = `/api/export.xlsx?domain=${encodeURIComponent(domain)}`;
  });

  $("#btn-print").addEventListener("click", () => window.print());

  $("#btn-logout").addEventListener("click", async () => {
    await fetch("/api/logout", { method: "POST" });
    window.location = "/login";
  });

  loadMe();

  $("#kw-search").addEventListener("input", (e) => {
    state.filters.search = e.target.value.trim().toLowerCase();
    renderTable();
  });
  $("#intent-filter").addEventListener("change", (e) => {
    state.filters.intent = e.target.value;
    renderTable();
  });
  $("#bucket-filter").addEventListener("change", (e) => {
    state.filters.bucket = e.target.value;
    renderTable();
  });

  document.querySelectorAll("#kw-table th").forEach((th) => {
    th.addEventListener("click", () => {
      const key = th.dataset.sort;
      if (state.sort.key === key) {
        state.sort.dir = state.sort.dir === "asc" ? "desc" : "asc";
      } else {
        state.sort = { key, dir: "asc" };
      }
      renderTable();
    });
  });

  $("#kw-table tbody").addEventListener("click", (e) => {
    const tr = e.target.closest("tr");
    if (tr) openModal(tr.dataset.kw);
  });

  $("#modal-close").addEventListener("click", closeModal);
  $("#modal").addEventListener("click", (e) => {
    if (e.target === $("#modal")) closeModal();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeModal();
  });

  load();
});
