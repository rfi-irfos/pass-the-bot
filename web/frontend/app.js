const API_BASE_URL = "https://passthebot-api.fly.dev";

const form = document.getElementById("check-form");
const submitBtn = document.getElementById("submit-btn");
const errorBox = document.getElementById("error-box");
const results = document.getElementById("results");
const scoreHeadline = document.getElementById("score-headline");
const matchedList = document.getElementById("matched-list");
const nearMissList = document.getElementById("nearmiss-list");
const missingList = document.getElementById("missing-list");

function showError(message) {
  errorBox.textContent = message;
  errorBox.classList.remove("hidden");
}

function hideError() {
  errorBox.classList.add("hidden");
  errorBox.textContent = "";
}

function renderList(listEl, items, emptyText) {
  listEl.innerHTML = "";
  if (items.length === 0) {
    const li = document.createElement("li");
    li.textContent = emptyText;
    li.className = "text-gray-400 italic";
    listEl.appendChild(li);
    return;
  }
  for (const item of items) {
    const li = document.createElement("li");
    li.className = "bg-gray-50 rounded px-3 py-2";
    if (item.status === "NEAR_MISS" && item.suggested_alias) {
      li.textContent = `${item.display_name} — found "${item.found_text}", did you mean "${item.suggested_alias}"?`;
    } else {
      li.textContent = item.display_name;
    }
    listEl.appendChild(li);
  }
}

function renderResults(report) {
  scoreHeadline.textContent = `Score: ${report.score.coverage_pct}% (${report.score.required_matched}/${report.score.required_total} required skills)`;
  const matched = report.results.filter((r) => r.status === "MATCH");
  const nearMiss = report.results.filter((r) => r.status === "NEAR_MISS");
  const missing = report.results.filter((r) => r.status === "MISSING");
  renderList(matchedList, matched, "Nothing matched yet.");
  renderList(nearMissList, nearMiss, "No near-misses found.");
  renderList(missingList, missing, "Nothing missing — great fit.");
  results.classList.remove("hidden");
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  hideError();
  results.classList.add("hidden");

  const postingText = document.getElementById("posting_text").value;
  const resumeFile = document.getElementById("resume_file").files[0];

  if (!postingText.trim() || !resumeFile) {
    showError("Please provide both the job posting text and a resume file.");
    return;
  }

  const formData = new FormData();
  formData.append("posting_text", postingText);
  formData.append("resume_file", resumeFile);

  submitBtn.disabled = true;
  submitBtn.textContent = "Checking...";

  try {
    const response = await fetch(`${API_BASE_URL}/api/check`, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      showError(body.detail || `Request failed (${response.status}).`);
      return;
    }

    const report = await response.json();
    renderResults(report);
  } catch (err) {
    showError("Could not reach the backend. Is it running?");
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Check my CV";
  }
});
