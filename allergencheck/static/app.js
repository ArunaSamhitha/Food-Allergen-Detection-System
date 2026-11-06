const $ = (s) => document.querySelector(s);
const STORE = "allergencheck-profile";
let profile = { avoid: ["peanut", "tree_nut"], custom: [] };
let photo = null;

try { profile = JSON.parse(localStorage.getItem(STORE)) || profile; } catch { /* storage unavailable */ }
const save = () => { try { localStorage.setItem(STORE, JSON.stringify(profile)); } catch { /* ignore */ } };
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

async function loadCategories() {
  const cats = await (await fetch("/api/categories")).json();
  $("#cats").innerHTML = cats.map((c) =>
    `<button type="button" class="chip" data-key="${c.key}" aria-pressed="${profile.avoid.includes(c.key)}">${esc(c.label)}${c.kind === "diet" ? "<small>diet</small>" : ""}</button>`
  ).join("");
}

$("#cats").addEventListener("click", (e) => {
  const chip = e.target.closest(".chip");
  if (!chip) return;
  const key = chip.dataset.key;
  profile.avoid = profile.avoid.includes(key) ? profile.avoid.filter((k) => k !== key) : [...profile.avoid, key];
  chip.setAttribute("aria-pressed", profile.avoid.includes(key));
  save();
});
$("#custom").value = profile.custom.join(", ");
$("#custom").addEventListener("change", () => {
  profile.custom = $("#custom").value.split(",").map((s) => s.trim()).filter(Boolean);
  save();
});

document.querySelectorAll(".tabs button").forEach((btn) => btn.addEventListener("click", () => {
  document.querySelectorAll(".tabs button").forEach((b) => b.setAttribute("aria-selected", b === btn));
  document.querySelectorAll(".tabpanel").forEach((p) => { p.hidden = p.dataset.panel !== btn.dataset.tab; });
}));

$("#photo").addEventListener("change", () => {
  photo = $("#photo").files[0] || null;
  const img = $("#preview");
  if (photo) { img.src = URL.createObjectURL(photo); img.hidden = false; $("#drop-text").hidden = true; }
});

function setStatus(msg, error = false) { $("#status").textContent = msg; $("#status").className = "status" + (error ? " error" : ""); }

async function run(form, request) {
  const button = form.querySelector(".go");
  button.disabled = true;
  setStatus("Checking…");
  $("#result").hidden = true;
  try {
    const res = await request();
    const body = await res.json();
    if (!res.ok) throw new Error(typeof body.detail === "string" ? body.detail : "Something in the request wasn't valid.");
    render(body);
    setStatus("");
  } catch (e) {
    setStatus(e.message === "Failed to fetch" ? "Couldn't reach the server. Check your connection." : e.message, true);
  } finally {
    button.disabled = false;
  }
}

$("#form-photo").addEventListener("submit", (e) => {
  e.preventDefault();
  if (!photo) return setStatus("Choose a photo first.", true);
  const fd = new FormData();
  fd.append("image", photo);
  fd.append("profile", JSON.stringify(profile));
  run(e.target, () => fetch("/api/analyze/photo", { method: "POST", body: fd }));
});
$("#form-barcode").addEventListener("submit", (e) => {
  e.preventDefault();
  const q = new URLSearchParams({ avoid: profile.avoid.join(","), custom: profile.custom.join(",") });
  run(e.target, () => fetch(`/api/analyze/barcode/${encodeURIComponent($("#code").value.trim())}?${q}`));
});
$("#form-text").addEventListener("submit", (e) => {
  e.preventDefault();
  run(e.target, () => fetch("/api/analyze/text", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: $("#text").value, profile }),
  }));
});

const WORDS = { unsafe: "Don't eat", caution: "Check first", safe: "Looks OK", unreadable: "Can't tell" };
const SOURCE = { ingredients: "In the ingredients", contains_statement: "In the Contains statement", precaution: "Cross-contact warning" };

function render({ report: r, product, ocr_confidence, ms }) {
  const hits = new Set(r.findings.filter((f) => f.source === "ingredients").map((f) => f.text));
  const meta = [ocr_confidence != null ? `OCR confidence ${ocr_confidence.toFixed(0)}%` : null, `${ms.toFixed(0)} ms`].filter(Boolean).join(" · ");
  $("#result").innerHTML = `
    ${product ? `<div class="product">${product.image_url ? `<img src="${esc(product.image_url)}" alt="">` : ""}<div><b>${esc(product.name || "Unnamed product")}</b><br><span class="hint">${esc(product.brand || "")}</span></div></div>` : ""}
    <div class="verdict ${r.verdict}"><span class="word">${WORDS[r.verdict]}</span><span class="line">${esc(r.summary)}</span><span class="meta">${meta}</span></div>
    ${r.findings.length ? `<div class="panel"><h2>Why</h2><ul class="list">${r.findings.map((f) => `
      <li><span class="tag">${SOURCE[f.source]}</span><span><b>${esc(f.label)}</b>: “${esc(f.text)}”${f.ocr_corrected ? ` <span class="hint">(read as “${esc(f.term)}”)</span>` : ""}</span></li>`).join("")}</ul></div>` : ""}
    ${r.checks.length ? `<div class="panel"><h2>Worth confirming</h2><ul class="list">${r.checks.map((c) => `<li><span><b>${esc(c.ingredient)}</b>: ${esc(c.reason)}</span></li>`).join("")}</ul></div>` : ""}
    ${r.other_allergens.length ? `<p class="hint">Also contains: ${r.other_allergens.map(esc).join(", ")} (not in your profile).</p>` : ""}
    ${r.ingredients.length ? `<div class="panel"><h2>Ingredients we read</h2><div class="ingredients">${r.ingredients.map((i) => `<span class="${[...hits].some((h) => i.includes(h)) ? "hit" : ""}">${esc(i)}</span>`).join("")}</div></div>` : ""}`;
  $("#result").hidden = false;
  $("#result").scrollIntoView({ behavior: "smooth", block: "start" });
}

loadCategories().catch(() => setStatus("Couldn't load allergen list. Is the server running?", true));
