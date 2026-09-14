const API_BASE_URL = "https://passthebot-api.fly.dev";
const GAUGE_CIRCUMFERENCE = 2 * Math.PI * 60;

const TRANSLATIONS = {
  de: {
    pageTitle: "Pass The Bot! — sieh deinen Lebenslauf wie ein ATS",
    tagline: "Sieh deinen Lebenslauf so, wie ihn ein Bewerbermanagementsystem (ATS) sieht.",
    desc1: 'Anzeige einfügen, Lebenslauf hochladen und sofort eine transparente Auswertung bekommen: welche geforderten Skills erkannt wurden, welche knapp danebenlagen (Tippfehler wie "Dockr" statt "Docker"), und welche wirklich fehlen.',
    desc2: "Keine KI-Blackbox, kein automatisches Umschreiben deines Lebenslaufs — nur eine deterministische, nachvollziehbare Diagnose, damit du genau weißt, warum ein Keyword-Filter dich durchlässt oder aussortiert, bevor ein Mensch deine Bewerbung überhaupt sieht.",
    badgeFree: "Kostenlos",
    badgeNoAccount: "Kein Account",
    badgeOpenSource: "Open Source",
    labelPosting: "Stellenanzeige",
    placeholderPosting: "Stellenanzeige hier einfügen...",
    labelCv: "Dein Lebenslauf",
    fileHint: "Datei auswählen oder hineinziehen",
    fileTypes: "PDF oder DOCX (max. 5MB)",
    analyzeBtn: "Lebenslauf analysieren",
    analyzing: "Analysiere...",
    progressText: "Dein Lebenslauf wird analysiert...",
    errorBoth: "Bitte sowohl den Anzeigentext als auch eine Lebenslauf-Datei angeben.",
    errorUnreachable: "Backend nicht erreichbar. Läuft es gerade?",
    atsResultHeading: "ATS-Ergebnis",
    scorePrompt: "Starte oben eine Prüfung, um hier dein Ergebnis zu sehen.",
    scoreSummary: (pct, matched, total) =>
      `Dein Lebenslauf erfüllt ${pct}% der geforderten Skills und Keywords aus dieser Anzeige (${matched}/${total} Pflicht-Skills).`,
    matchedLabel: "Gefunden",
    nearMissLabel: "Knapp daneben",
    missingLabel: "Fehlend",
    matchedHeading: "Gefundene Skills",
    nearMissHeading: "Knapp daneben",
    missingHeading: "Fehlende Skills",
    emptyMatched: "Noch nichts gefunden.",
    emptyNearMiss: "Keine Beinahe-Treffer.",
    emptyMissing: "Nichts fehlt — passt sehr gut.",
    foundLabel: (text) => `gefunden: "${text}"`,
    tipsHeading: "Bevor du diesen Lebenslauf abschickst",
    tipsEmpty: "Keine Änderungen nötig — dieser Lebenslauf deckt alles ab, was die Anzeige verlangt.",
    tipFix: (found, alias, name) =>
      `Schreibe "${found}" als exakten Begriff "${alias}", damit es als ${name} erkannt wird.`,
    tipRequired: (name) => `Ergänze Belege für ${name} — das ist laut Anzeige ein Pflicht-Skill.`,
    tipOptional: (name) => `Erwähne ${name}, falls vorhanden — laut Anzeige von Vorteil.`,
    privacyNote:
      "Wir speichern deine Daten nicht. Nichts wird gespeichert oder zum Trainieren eines Modells verwendet, diese Seite setzt keine Cookies — dein Lebenslauf und der Anzeigentext bleiben in deinem Browser und werden nur für diese eine Prüfung an die Analyse-Engine geschickt.",
  },
  en: {
    pageTitle: "Pass The Bot! — see your CV the way the machine sees it",
    tagline: "See your resume the way an Applicant Tracking System (ATS) sees it.",
    desc1: 'Paste a job posting, upload your CV, and get an instant, transparent breakdown: which required skills matched, which were near-misses caught by typos or phrasing (like "Dockr" vs "Docker"), and which are genuinely missing.',
    desc2: "No AI black box, no rewriting your resume for you — just a deterministic, explainable diagnostic so you know exactly why a keyword filter would pass or reject you, before a recruiter ever sees it.",
    badgeFree: "Free",
    badgeNoAccount: "No account",
    badgeOpenSource: "Open source",
    labelPosting: "Job posting",
    placeholderPosting: "Paste the job description here...",
    labelCv: "Your CV",
    fileHint: "Choose a file or drag and drop",
    fileTypes: "PDF or DOCX (max 5MB)",
    analyzeBtn: "Analyze Resume",
    analyzing: "Analyzing...",
    progressText: "Analyzing your resume...",
    errorBoth: "Please provide both the job posting text and a resume file.",
    errorUnreachable: "Could not reach the backend. Is it running?",
    atsResultHeading: "ATS Result",
    scorePrompt: "Run a check above to see your results here.",
    scoreSummary: (pct, matched, total) =>
      `Your resume matches ${pct}% of the required skills and keywords from this job posting (${matched}/${total} required).`,
    matchedLabel: "Matched",
    nearMissLabel: "Near Misses",
    missingLabel: "Missing",
    matchedHeading: "Matched Skills",
    nearMissHeading: "Near Misses",
    missingHeading: "Missing Skills",
    emptyMatched: "Nothing matched yet.",
    emptyNearMiss: "No near-misses found.",
    emptyMissing: "Nothing missing — great fit.",
    foundLabel: (text) => `found "${text}"`,
    tipsHeading: "Before you submit this resume",
    tipsEmpty: "No changes needed — this resume covers everything the posting asks for.",
    tipFix: (found, alias, name) =>
      `Fix "${found}" to the exact term "${alias}" so it's recognized as ${name}.`,
    tipRequired: (name) => `Add evidence of ${name} — this is listed as a required skill in the posting.`,
    tipOptional: (name) => `Consider mentioning ${name} if you have it — it's listed as a nice-to-have.`,
    privacyNote:
      "We don't keep your data. Nothing is stored, nothing is used to train any model, this page sets no cookies — your resume and the posting text stay in your browser and are only sent to the analysis engine for this one check.",
  },
};

let currentLang = "de";
let lastReport = null;

const form = document.getElementById("check-form");
const submitBtn = document.getElementById("submit-btn");
const progressWrap = document.getElementById("progress-wrap");
const errorBox = document.getElementById("error-box");
const resultsCard = document.getElementById("results-card");
const fileInput = document.getElementById("resume_file");
const fileNameDisplay = document.getElementById("file-name-display");
const langDeBtn = document.getElementById("lang-de");
const langEnBtn = document.getElementById("lang-en");

const gaugeCircle = document.getElementById("gauge-circle");
const gaugeText = document.getElementById("gauge-text");
const scoreSummary = document.getElementById("score-summary");
const countMatched = document.getElementById("count-matched");
const countNearMiss = document.getElementById("count-nearmiss");
const countMissing = document.getElementById("count-missing");
const matchedList = document.getElementById("matched-list");
const nearMissList = document.getElementById("nearmiss-list");
const missingList = document.getElementById("missing-list");
const tipsList = document.getElementById("tips-list");

function t(key) {
  return TRANSLATIONS[currentLang][key];
}

function applyStaticTranslations() {
  document.documentElement.lang = currentLang;
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    el.textContent = t(el.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
    el.placeholder = t(el.dataset.i18nPlaceholder);
  });
  document.title = t("pageTitle");
  langDeBtn.classList.toggle("bg-black", currentLang === "de");
  langDeBtn.classList.toggle("text-white", currentLang === "de");
  langDeBtn.classList.toggle("text-gray-400", currentLang !== "de");
  langEnBtn.classList.toggle("bg-black", currentLang === "en");
  langEnBtn.classList.toggle("text-white", currentLang === "en");
  langEnBtn.classList.toggle("text-gray-400", currentLang !== "en");
}

function setLang(lang) {
  currentLang = lang;
  applyStaticTranslations();
  if (lastReport) {
    renderResults(lastReport, { scroll: false });
  }
}

langDeBtn.addEventListener("click", () => setLang("de"));
langEnBtn.addEventListener("click", () => setLang("en"));

fileInput.addEventListener("change", () => {
  const file = fileInput.files[0];
  if (file) {
    fileNameDisplay.textContent = file.name;
  } else {
    fileNameDisplay.innerHTML = `<span>${t("fileHint")}</span><br><span class="text-gray-400">${t("fileTypes")}</span>`;
  }
});

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
    li.className = "bg-white/70 rounded px-3 py-2";
    if (item.status === "NEAR_MISS" && item.suggested_alias) {
      li.innerHTML = `<span class="font-medium">${item.display_name}</span><br><span class="text-gray-500">${t("foundLabel")(item.found_text)}</span>`;
    } else {
      li.textContent = item.display_name;
    }
    listEl.appendChild(li);
  }
}

function buildTips(report) {
  const tips = [];
  const nearMiss = report.results.filter((r) => r.status === "NEAR_MISS");
  const missingRequired = report.results.filter((r) => r.status === "MISSING" && r.required);
  const missingOptional = report.results.filter((r) => r.status === "MISSING" && !r.required);

  for (const item of nearMiss) {
    tips.push(t("tipFix")(item.found_text, item.suggested_alias, item.display_name));
  }
  for (const item of missingRequired) {
    tips.push(t("tipRequired")(item.display_name));
  }
  for (const item of missingOptional) {
    tips.push(t("tipOptional")(item.display_name));
  }
  return tips;
}

function easeOutBack(x) {
  const c1 = 1.15;
  const c3 = c1 + 1;
  return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2);
}

const GAUGE_COLOR_STOPS = [
  { pct: 0, rgb: [220, 38, 38] },   // red-600
  { pct: 33, rgb: [217, 119, 6] },  // amber-600 (orange)
  { pct: 66, rgb: [132, 204, 22] }, // lime-500 (light green)
  { pct: 100, rgb: [21, 128, 61] }, // green-700 (dark green)
];

function gaugeColorFor(pct) {
  const clamped = Math.max(0, Math.min(100, pct));
  for (let i = 0; i < GAUGE_COLOR_STOPS.length - 1; i++) {
    const a = GAUGE_COLOR_STOPS[i];
    const b = GAUGE_COLOR_STOPS[i + 1];
    if (clamped >= a.pct && clamped <= b.pct) {
      const t = (clamped - a.pct) / (b.pct - a.pct);
      const rgb = a.rgb.map((c, idx) => Math.round(c + (b.rgb[idx] - c) * t));
      return `rgb(${rgb.join(",")})`;
    }
  }
  const last = GAUGE_COLOR_STOPS[GAUGE_COLOR_STOPS.length - 1].rgb;
  return `rgb(${last.join(",")})`;
}

function animateGaugeTo(pct) {
  gaugeCircle.classList.remove("gauge-loading");
  const offset = GAUGE_CIRCUMFERENCE * (1 - pct / 100);
  gaugeCircle.setAttribute("stroke-dashoffset", offset);

  const duration = 1800;
  const start = performance.now();
  function tick(now) {
    const elapsed = Math.min(1, (now - start) / duration);
    const eased = Math.max(0, Math.min(1, easeOutBack(elapsed)));
    const value = Math.round(pct * eased);
    gaugeText.textContent = `${value}%`;
    gaugeCircle.setAttribute("stroke", gaugeColorFor(value));
    if (elapsed < 1) {
      requestAnimationFrame(tick);
    } else {
      gaugeText.textContent = `${Math.round(pct)}%`;
      gaugeCircle.setAttribute("stroke", gaugeColorFor(pct));
    }
  }
  requestAnimationFrame(tick);
}

function renderResults(report, { scroll = true } = {}) {
  lastReport = report;
  const pct = report.score.coverage_pct;
  animateGaugeTo(pct);

  scoreSummary.textContent = t("scoreSummary")(pct, report.score.required_matched, report.score.required_total);

  const matched = report.results.filter((r) => r.status === "MATCH");
  const nearMiss = report.results.filter((r) => r.status === "NEAR_MISS");
  const missing = report.results.filter((r) => r.status === "MISSING");

  countMatched.textContent = matched.length;
  countNearMiss.textContent = nearMiss.length;
  countMissing.textContent = missing.length;

  renderList(matchedList, matched, t("emptyMatched"));
  renderList(nearMissList, nearMiss, t("emptyNearMiss"));
  renderList(missingList, missing, t("emptyMissing"));

  const tips = buildTips(report);
  tipsList.innerHTML = "";
  if (tips.length === 0) {
    const li = document.createElement("li");
    li.className = "text-gray-400 italic";
    li.textContent = t("tipsEmpty");
    tipsList.appendChild(li);
  } else {
    for (const tip of tips) {
      const li = document.createElement("li");
      li.className = "flex gap-2";
      li.innerHTML = `<span>&bull;</span><span>${tip}</span>`;
      tipsList.appendChild(li);
    }
  }

  resultsCard.classList.remove("opacity-40");
  if (scroll) {
    resultsCard.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  hideError();

  const postingText = document.getElementById("posting_text").value;
  const resumeFile = fileInput.files[0];

  if (!postingText.trim() || !resumeFile) {
    showError(t("errorBoth"));
    return;
  }

  const formData = new FormData();
  formData.append("posting_text", postingText);
  formData.append("resume_file", resumeFile);
  formData.append("lang", currentLang);

  submitBtn.disabled = true;
  submitBtn.textContent = t("analyzing");
  progressWrap.classList.remove("hidden");
  gaugeCircle.classList.add("gauge-loading");
  gaugeText.textContent = "…";

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
    showError(t("errorUnreachable"));
  } finally {
    gaugeCircle.classList.remove("gauge-loading");
    submitBtn.disabled = false;
    submitBtn.textContent = t("analyzeBtn");
    progressWrap.classList.add("hidden");
  }
});

applyStaticTranslations();
