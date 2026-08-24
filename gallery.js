/* Gallery page: builds the thumbnail grid from data/summary.json
   (no server-side directory listing on GitHub Pages, so the list of
   dates doubles as the manifest of which images exist), then wires up
   a lightbox with click and arrow-key navigation between images. */

let entries = [];
let currentIndex = 0;

function imagePath(date) {
  return `images/pac_bars_${date}.png`;
}

function openLightbox(index) {
  currentIndex = index;
  const entry = entries[index];
  const img = document.getElementById("lightbox-img");
  img.src = imagePath(entry.date);
  img.alt = `Solar output ${entry.date}`;
  document.getElementById("lightbox-caption").textContent =
    `${entry.date} — ${entry.kwh.toFixed(1)} kWh`;
  document.getElementById("lightbox").classList.add("open");
}

function closeLightbox() {
  document.getElementById("lightbox").classList.remove("open");
}

function showNext(delta) {
  currentIndex = (currentIndex + delta + entries.length) % entries.length;
  openLightbox(currentIndex);
}

async function init() {
  const res = await fetch("data/summary.json");
  const rows = await res.json();

  // Most recent first
  entries = [...rows].sort((a, b) => b.date.localeCompare(a.date));

  const grid = document.getElementById("gallery-grid");
  entries.forEach((entry, i) => {
    const item = document.createElement("div");
    item.className = "gallery-item";
    item.innerHTML = `
      <img src="${imagePath(entry.date)}" alt="Solar output ${entry.date}" loading="lazy">
      <div class="caption"><span>${entry.date}</span><span>${entry.kwh.toFixed(1)} kWh</span></div>
    `;
    item.addEventListener("click", () => openLightbox(i));
    grid.appendChild(item);
  });
}

document.getElementById("lightbox-close").addEventListener("click", closeLightbox);
document.getElementById("lightbox-prev").addEventListener("click", () => showNext(-1));
document.getElementById("lightbox-next").addEventListener("click", () => showNext(1));
document.getElementById("lightbox").addEventListener("click", (e) => {
  if (e.target.id === "lightbox") closeLightbox();
});

document.addEventListener("keydown", (e) => {
  if (!document.getElementById("lightbox").classList.contains("open")) return;
  if (e.key === "Escape") closeLightbox();
  if (e.key === "ArrowLeft") showNext(-1);
  if (e.key === "ArrowRight") showNext(1);
});

init();
