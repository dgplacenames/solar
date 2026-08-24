/* Overview page: four views (Day / Month / Year / Lifetime). Month/Year
   always show every column (day-of-month, Jan-Dec) even with no data yet;
   missing days render as zero. Day/Month/Year page backwards/forwards;
   Lifetime is a fixed 2026-2035 span with no arrows.

   Day shows the matplotlib PNG posted to Mastodon. Month/Year/Lifetime
   are rendered live with Chart.js from summary.json, styled to match. */

const GRAD_START = [255, 255, 0];   // yellow
const GRAD_END = [255, 0, 0];       // red
const LIFETIME_START_YEAR = 2026;
const LIFETIME_END_YEAR = 2035;

// Matches INSTALL_DATE in backfill.py - nav can't scroll back past this.
const EARLIEST_DATE = "2026-08-12";

// Matches matplotlib's default font, for visual consistency with the PNG.
const CHART_FONT = "'DejaVu Sans', Verdana, Arial, sans-serif";

// Fixed y-axis ceilings so periods are comparable rather than each one
// auto-scaling to its own best value. Adjust as real data comes in.
const MONTH_MAX_KWH = 10;
const BEST_MONTH_KWH = 200;
const YEAR_MAX_KWH = 1400;

let rows = [];            // raw data from summary.json
let byDate = new Map();   // date string -> kwh
let byDateInfo = new Map(); // date string -> full row (kwh, first, last)
let period = "day";
let refDate = new Date(); // anchor date for whichever period is active
let chartInstance = null;

function pad(n) { return String(n).padStart(2, "0"); }
function formatDuration(totalMinutes) {
  const hours = Math.floor(totalMinutes / 60);
  const mins = totalMinutes % 60;
  const parts = [];
  if (hours) parts.push(`${hours} hour${hours !== 1 ? "s" : ""}`);
  parts.push(`${mins} min${mins !== 1 ? "s" : ""}`);
  return parts.join(" ");
}
function minutesBetween(hhmmStart, hhmmEnd) {
  const [h1, m1] = hhmmStart.split(":").map(Number);
  const [h2, m2] = hhmmEnd.split(":").map(Number);
  return (h2 * 60 + m2) - (h1 * 60 + m1);
}
function toISODate(d) { return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; }
function addDays(d, n) { const r = new Date(d); r.setDate(r.getDate() + n); return r; }
function addMonths(d, n) { return new Date(d.getFullYear(), d.getMonth() + n, 1); }
function addYears(d, n) { return new Date(d.getFullYear() + n, d.getMonth(), 1); }
function daysInMonth(year, monthIndex) { return new Date(year, monthIndex + 1, 0).getDate(); }
function lerpColour(t) {
  const clamped = Math.max(0, Math.min(1, t));
  const r = Math.round(GRAD_START[0] + (GRAD_END[0] - GRAD_START[0]) * clamped);
  const g = Math.round(GRAD_START[1] + (GRAD_END[1] - GRAD_START[1]) * clamped);
  const b = Math.round(GRAD_START[2] + (GRAD_END[2] - GRAD_START[2]) * clamped);
  return `rgb(${r},${g},${b})`;
}

const chartAreaBackgroundPlugin = {
  id: "chartAreaBackground",
  beforeDraw(chart) {
    const { ctx, chartArea } = chart;
    ctx.save();
    ctx.fillStyle = "#1f77b4";
    ctx.fillRect(
      chartArea.left, chartArea.top,
      chartArea.right - chartArea.left, chartArea.bottom - chartArea.top
    );
    ctx.restore();
  },
};
Chart.register(chartAreaBackgroundPlugin);

// Draws a box border around the plot area, matching matplotlib's spines.
const boxBorderPlugin = {
  id: "boxBorder",
  afterDraw(chart) {
    const { ctx, chartArea } = chart;
    ctx.save();
    ctx.strokeStyle = "rgba(0,0,0,0.9)";
    ctx.lineWidth = 1;
    ctx.strokeRect(
      chartArea.left, chartArea.top,
      chartArea.right - chartArea.left, chartArea.bottom - chartArea.top
    );
    ctx.restore();
  },
};
Chart.register(boxBorderPlugin);

function baseChartOptions(titleLines, yAxisLabel, yMax) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    plugins: {
      legend: { display: false },
      title: {
        display: true,
        text: titleLines,
        color: "#000000",
        font: { family: CHART_FONT, size: 12, weight: "normal" },
        padding: { top: 4, bottom: 8 },
      },
    },
    scales: {
      x: {
        ticks: { color: "#000000", font: { family: CHART_FONT, size: 11 } },
        grid: { display: true, drawOnChartArea: false, drawTicks: true,
                tickLength: 7, color: "rgba(0,0,0,0.9)" },
      },
      y: {
        min: 0, max: yMax,
        ticks: {
          color: "#000000", font: { family: CHART_FONT, size: 11 },
          callback: (value) => `${value}`,
        },
        grid: { color: "rgba(255,255,255,0.3)" },
        title: { display: true, text: yAxisLabel, color: "#000000",
                 font: { family: CHART_FONT, size: 12 } },
      },
    },
  };
}

function renderBarChart(labels, values, fixedMax, periodLabelForTitle, activeMinutesTotal) {
  document.getElementById("day-image").style.display = "none";
  document.getElementById("chart").style.display = "block";
  document.querySelector(".chart-card").classList.add("has-canvas");

  const scaleMax = fixedMax || Math.max(...values, 0.01);
  const colours = values.map((v) => lerpColour(v / scaleMax));
  const total = values.reduce((a, b) => a + b, 0);

  const ctx = document.getElementById("chart").getContext("2d");
  if (chartInstance) chartInstance.destroy();

  const titleLines = [`Five Solar Panels in Orkney Generated ${total.toFixed(1)} kWh`, periodLabelForTitle];
  chartInstance = new Chart(ctx, {
    type: "bar",
    data: { labels, datasets: [{ data: values, backgroundColor: colours, borderRadius: 3 }] },
    options: baseChartOptions(titleLines, "kWh", fixedMax || undefined),
  });

  document.getElementById("period-total").textContent =
    activeMinutesTotal ? `${formatDuration(activeMinutesTotal)} active` : "";
}

function renderDayView() {
  document.getElementById("chart").style.display = "none";
  document.querySelector(".chart-card").classList.remove("has-canvas");
  const img = document.getElementById("day-image");
  const dateStr = toISODate(refDate);
  const kwh = byDate.get(dateStr);

  if (kwh === undefined) {
    img.style.display = "none";
    document.getElementById("period-total").textContent = "No data for this day";
  } else {
    img.src = `images/pac_bars_${dateStr}.png`;
    img.style.display = "block";
    const info = byDateInfo.get(dateStr);
    let hoursText = "";
    if (info && info.first && info.last) {
      hoursText = `${formatDuration(minutesBetween(info.first, info.last))} active`;
    }
    document.getElementById("period-total").textContent = hoursText;
  }
  document.getElementById("period-label").textContent = dateStr;
}

function renderMonthView() {
  const year = refDate.getFullYear();
  const month = refDate.getMonth();
  const numDays = daysInMonth(year, month);
  const labels = Array.from({ length: numDays }, (_, i) => String(i + 1));
  const values = Array.from({ length: numDays }, (_, i) => {
    const d = new Date(year, month, i + 1);
    return byDate.get(toISODate(d)) || 0;
  });
  let activeMinutesTotal = 0;
  for (let i = 0; i < numDays; i++) {
    const info = byDateInfo.get(toISODate(new Date(year, month, i + 1)));
    if (info && info.first && info.last) activeMinutesTotal += minutesBetween(info.first, info.last);
  }
  const monthName = refDate.toLocaleString("en-GB", { month: "long", year: "numeric" });
  document.getElementById("period-label").textContent = monthName;
  renderBarChart(labels, values, MONTH_MAX_KWH, monthName, activeMinutesTotal);
}

function renderYearView() {
  const year = refDate.getFullYear();
  const monthLabels = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  const values = monthLabels.map((_, monthIndex) => {
    let sum = 0;
    rows.forEach(({ date, kwh }) => {
      const d = new Date(date + "T00:00:00");
      if (d.getFullYear() === year && d.getMonth() === monthIndex) sum += kwh;
    });
    return sum;
  });
  let activeMinutesTotal = 0;
  rows.forEach((r) => {
    if (new Date(r.date + "T00:00:00").getFullYear() === year && r.first && r.last) {
      activeMinutesTotal += minutesBetween(r.first, r.last);
    }
  });
  document.getElementById("period-label").textContent = String(year);
  renderBarChart(monthLabels, values, BEST_MONTH_KWH, String(year), activeMinutesTotal);
}

function renderLifetimeView() {
  const years = [];
  for (let y = LIFETIME_START_YEAR; y <= LIFETIME_END_YEAR; y++) years.push(y);
  const labels = years.map(String);
  const values = years.map((year) => {
    let sum = 0;
    rows.forEach(({ date, kwh }) => {
      if (new Date(date + "T00:00:00").getFullYear() === year) sum += kwh;
    });
    return sum;
  });
  let activeMinutesTotal = 0;
  rows.forEach((r) => {
    const y = new Date(r.date + "T00:00:00").getFullYear();
    if (years.includes(y) && r.first && r.last) {
      activeMinutesTotal += minutesBetween(r.first, r.last);
    }
  });
  const currentYear = Math.min(new Date().getFullYear(), LIFETIME_END_YEAR);
  const lifetimeLabel = currentYear <= LIFETIME_START_YEAR
    ? String(LIFETIME_START_YEAR)
    : `${LIFETIME_START_YEAR}\u2013${currentYear}`;
  document.getElementById("period-label").textContent = lifetimeLabel;
  renderBarChart(labels, values, YEAR_MAX_KWH, lifetimeLabel, activeMinutesTotal);
}

function updateNavVisibility() {
  const isLifetime = period === "lifetime";
  document.getElementById("nav-prev").style.visibility = isLifetime ? "hidden" : "visible";
  document.getElementById("nav-next").style.visibility = isLifetime ? "hidden" : "visible";
  if (isLifetime) return;

  const today = new Date();
  const earliest = new Date(EARLIEST_DATE + "T00:00:00");

  let atLatest = false;
  let atEarliest = false;
  if (period === "day") {
    atLatest = toISODate(refDate) >= toISODate(today);
    atEarliest = toISODate(refDate) <= EARLIEST_DATE;
  }
  if (period === "month") {
    atLatest = refDate.getFullYear() === today.getFullYear() && refDate.getMonth() === today.getMonth();
    atEarliest = refDate.getFullYear() === earliest.getFullYear() && refDate.getMonth() === earliest.getMonth();
  }
  if (period === "year") {
    atLatest = refDate.getFullYear() === today.getFullYear();
    atEarliest = refDate.getFullYear() === earliest.getFullYear();
  }
  document.getElementById("nav-next").disabled = atLatest;
  document.getElementById("nav-prev").disabled = atEarliest;
}

function render() {
  if (period === "day") renderDayView();
  else if (period === "month") renderMonthView();
  else if (period === "year") renderYearView();
  else renderLifetimeView();
  updateNavVisibility();
}

function navigate(delta) {
  const earliest = new Date(EARLIEST_DATE + "T00:00:00");
  let candidate;

  if (period === "day") candidate = addDays(refDate, delta);
  else if (period === "month") candidate = addMonths(refDate, delta);
  else if (period === "year") candidate = addYears(refDate, delta);
  else return;

  // Clamp Prev to never scroll back before install date (backstop -
  // the disabled button is the main guard).
  if (period === "day" && candidate < earliest) candidate = earliest;
  if (period === "month" &&
      (candidate.getFullYear() < earliest.getFullYear() ||
       (candidate.getFullYear() === earliest.getFullYear() && candidate.getMonth() < earliest.getMonth()))) {
    candidate = new Date(earliest.getFullYear(), earliest.getMonth(), 1);
  }
  if (period === "year" && candidate.getFullYear() < earliest.getFullYear()) {
    candidate = new Date(earliest.getFullYear(), 0, 1);
  }

  refDate = candidate;
  render();
}

document.querySelectorAll(".period-toggle button").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".period-toggle button").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    period = btn.dataset.period;
    render();
  });
});

document.getElementById("nav-prev").addEventListener("click", () => navigate(-1));
document.getElementById("nav-next").addEventListener("click", () => navigate(1));

async function init() {
  const res = await fetch("data/summary.json");
  rows = await res.json();
  rows.forEach((r) => byDate.set(r.date, r.kwh));
  rows.forEach((r) => byDateInfo.set(r.date, r));

  if (rows.length === 0) {
    return;
  }

  const latest = rows[rows.length - 1];

  refDate = new Date(latest.date + "T00:00:00");
  render();
}

init();
