"use strict";

/* ScoutForge vanilla-JS dashboard.
 *
 * Talks only to the FastAPI backend; every action maps to one REST call.
 * Scoring and funnel analytics are computed server-side and simply rendered
 * here, so the dashboard stays a thin client with no business logic.
 */

const $ = (sel) => document.querySelector(sel);

const state = { jobs: [], candidates: [], selectedJobId: null };

function esc(str) {
  const div = document.createElement("div");
  div.textContent = str == null ? "" : String(str);
  return div.innerHTML;
}

async function api(path, options) {
  const res = await fetch(path, options);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail || detail;
    } catch (_) { /* non-JSON error body */ }
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json();
}

const jsonBody = (body) => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

const csv = (s) => s.split(",").map((x) => x.trim()).filter(Boolean);
const patch = (fn) => {
  const parts = (n, s) => { if (n) part.innerHTML = s; };
  return fn();
};

/* ── Jobs ─────────────────────────────────────────────────────────────── */
async function loadJobs() {
  const { jobs } = await api("/api/jobs");
  state.jobs = jobs;
  renderJobs();
}

function renderJobs() {
  const ul = $("#job-list");
  ul.innerHTML = "";
  const jobs = state.jobs.filter((j) => j.status === "open" || j.status === undefined);
  jobs.forEach((j) => {
    const li = document.createElement("li");
    li.className = "job" + (state.selectedJobId === j.id ? " active" : "");
    li.innerHTML = `
      <div class="job-head">
        <strong>${esc(j.title)}</strong>
        <span class="pill">${esc(j.seniority)}</span>
        <span class="pill muted">${esc(j.location)}</span>
        <span class="pill status ${esc(j.status)}">${esc(j.status)}</span>
      </div>
      <div class="tags">${(j.required_skills || []).map((s) => `<span class="tag">${esc(s)}</span>`).join("")}</div>
      <div class="job-actions">
        <button class="select" data-id="${j.id}">Select</button>
        <button class="ghost close" data-id="${j.id}">Close</button>
      </div>`;
    li.querySelector(".select").addEventListener("click", () => selectJob(j.id));
    li.querySelector(".close").addEventListener("click", async (e) => {
      e.stopPropagation();
      await api(`/api/jobs/${j.id}/close`, { method: "POST" });
      await Promise.all([loadJobs(), refreshSelected()]);
    });
    ul.appendChild(li);
  });
}

async function selectJob(id) {
  state.selectedJobId = id;
  await Promise.all([loadJobs(), loadCandidates(), loadAnalytics()]);
  $("#cand-add-btn").disabled = false;
  $("#cand-add-btn").textContent = "Add candidate";
}

/* ── Candidates ───────────────────────────────────────────────────────── */
async function loadCandidates() {
  if (!state.selectedJobId) { renderCandidates([]); return; }
  const job = state.jobs.find((j) => j.id === state.selectedJobId);
  $("#ctx-job").textContent = job ? `— ${job.title}` : "";
  const { candidates } = await api(`/api/candidates?job_id=${state.selectedJobId}`);
  state.candidates = candidates;
  renderCandidates(candidates);
  renderShortlist();
}

function renderCandidates(candidates) {
  const ul = $("#candidate-list");
  ul.innerHTML = "";
  if (!candidates.length) {
    ul.innerHTML = `<li class="muted">No candidates sourced yet for this job.</li>`;
    return;
  }
  candidates.forEach((c) => {
    const li = document.createElement("li");
    li.className = "cand";
    li.innerHTML = `
      <div class="cand-head">
        <strong>${esc(c.name)}</strong>
        <span class="pill">${esc(c.stage)}</span>
      </div>
      <div class="tags">${(c.skills || []).map((s) => `<span class="tag">${esc(s)}</span>`).join("")}</div>
      <div class="row muted small">
        <span>${c.experience_years} yrs</span><span>${esc(c.source)}</span>
        <span>${c.notice_period_days}d notice</span>
      </div>
      <div class="cand-actions">
        <button class="ghost move" data-stage="sourced">sourced</button>
        <button class="ghost move" data-stage="screened">screened</button>
        <button class="ghost move" data-stage="interview">interview</button>
        <button class="ghost move" data-stage="offer">offer</button>
        <button class="ghost move" data-stage="hired">hired</button>
        <button class="ghost move danger" data-stage="rejected">rejected</button>
      </div>`;
    li.querySelectorAll(".move").forEach((btn) =>
      btn.addEventListener("click", async () => {
        const { to_stage } = await api(`/api/candidates/${c.id}/stage`, jsonBody({ to_stage: btn.dataset.stage }));
        li.querySelector(".pill").textContent = to_stage;
        await Promise.all([loadCandidates(), loadAnalytics()]);
      })
    );
    ul.appendChild(li);
  });
}

/* ── Shortlist (top-k by score) ───────────────────────────────────────── */
async function renderShortlist() {
  const ol = $("#shortlist");
  ol.innerHTML = "";
  if (!state.selectedJobId) { $("#shortlist-empty").style.display = "block"; return; }
  const { shortlist } = await api(`/api/jobs/${state.selectedJobId}/shortlist?k=5`);
  $("#shortlist-empty").style.display = shortlist.length ? "none" : "block";
  shortlist.forEach((c) => {
    const li = document.createElement("li");
    const t = c.score.total;
    const skillsMatched = c.score.skills.matched.length;
    const skillsReq = c.score.skills.required_skills.length;
    li.innerHTML = `
      <div class="score-row">
        <span class="rank-name">${esc(c.name)}</span>
        <span class="score-badge">${t.toFixed(1)}</span>
      </div>
      <div class="bar"><div class="fill" style="width:${Math.min(100, t)}%"></div></div>
      <div class="muted small">${skillsMatched}/${skillsReq} skills · ${esc(c.score.seniority.level)} · ${c.experience_years} yrs</div>`;
    ol.appendChild(li);
  });
}

/* ── Analytics ────────────────────────────────────────────────────────── */
async function loadAnalytics() {
  if (!state.selectedJobId) { $("#funnel").innerHTML = ""; return; }
  const ana = await api(`/api/jobs/${state.selectedJobId}/analytics`);
  const funnel = $("#funnel");
  const max = Math.max(1, ...ana.funnel.map((b) => b.count));
  funnel.innerHTML = ana.funnel
    .map((b) => `
      <div class="funnel-row">
        <span class="funnel-label">${esc(b.stage)}</span>
        <div class="bar"><div class="fill" style="width:${(b.count / max) * 100}%">${b.count}</div></div>
      </div>`)
    .join("");

  $("#sources").innerHTML = ana.source_effectiveness
    .map((s) => `<li><span class="muted">${esc(s.source)}</span><strong>${s.count}</strong></li>`)
    .join("");
  $("#offer-rate").textContent = ana.offer_acceptance_rate == null ? "n/a" : (ana.offer_acceptance_rate * 100).toFixed(0) + "%";
}

/* ── Event wiring ─────────────────────────────────────────────────────── */
$("#job-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  await api("/api/jobs", jsonBody({
    title: $("#job-title").value,
    description: $("#job-desc").value,
    required_skills: csv($("#job-skills").value),
    seniority: $("#job-seniority").value,
    location: $("#job-location").value,
    salary_min: $("#job-sal-min").value ? Number($("#job-sal-min").value) : null,
    salary_max: $("#job-sal-max").value ? Number($("#job-sal-max").value) : null,
  }));
  e.target.reset();
  await loadJobs();
});

$("#candidate-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!state.selectedJobId) return;
  const cand = await api("/api/candidates", jsonBody({
    job_id: state.selectedJobId,
    name: $("#cand-name").value,
    email: $("#cand-email").value,
    skills: csv($("#cand-skills").value),
    experience_years: Number($("#cand-exp").value || 0),
    source: $("#cand-source").value,
    notice_period_days: Number($("#cand-notice").value || 0),
  }));
  e.target.reset();
  console.log("Created candidate", cand);
  await Promise.all([loadCandidates(), loadAnalytics()]);
});

async function refreshSelected() {
  if (!state.selectedJobId) return;
  await Promise.all([loadCandidates(), loadAnalytics()]);
}

/* ── Boot ─────────────────────────────────────────────────────────────── */
(async function init() {
  try {
    const h = await api("/api/health");
    $("#health").textContent = `${h.service} ${h.version} — ${h.status}`;
  } catch (err) {
    $("#health").textContent = "backend unreachable";
  }
  await loadJobs();
})();