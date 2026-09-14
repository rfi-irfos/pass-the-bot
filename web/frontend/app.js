const API_BASE_URL = "https://passthebot-api.fly.dev";
const GAUGE_CIRCUMFERENCE = 2 * Math.PI * 60;

const TRANSLATIONS = {
  de: {
    pageTitle: "Pass The Bot! Sieh deinen Lebenslauf wie ein ATS",
    tagline: "Sieh deinen Lebenslauf so, wie ihn ein Bewerbermanagementsystem (ATS) sieht.",
    desc1: 'Anzeige einfügen, Lebenslauf hochladen und sofort eine transparente Auswertung bekommen: welche geforderten Skills erkannt wurden, welche knapp danebenlagen (Tippfehler wie "Dockr" statt "Docker"), und welche wirklich fehlen.',
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
    progressSteps: [
      { title: "Lebenslauf-Datei geöffnet", subtitle: "PDF oder DOCX wird eingelesen" },
      { title: "Text extrahiert", subtitle: "Rohtext aus der Datei gewonnen" },
      { title: "Anzeige gelesen", subtitle: "Text der Stellenanzeige übernommen" },
      { title: "Skills in der Anzeige erkannt", subtitle: "Bekannte Begriffe aus dem Skill-Graph abgeglichen" },
      { title: "Soft Skills in der Anzeige erkannt", subtitle: "Ähnlichkeitsvergleich per Embedding" },
      { title: "Skills im Lebenslauf erkannt", subtitle: "Bekannte Begriffe aus dem Skill-Graph abgeglichen" },
      { title: "Soft Skills im Lebenslauf erkannt", subtitle: "Ähnlichkeitsvergleich per Embedding" },
      { title: "Pflichtanforderungen erkannt", subtitle: 'Signalwörter wie "erforderlich" oder "must have" gesucht' },
      { title: "Wunschkenntnisse erkannt", subtitle: 'Signalwörter wie "von Vorteil" oder "nice to have" gesucht' },
      { title: "Direkter Abgleich", subtitle: "Skill-IDs aus Anzeige und Lebenslauf verglichen" },
      { title: "Tippfehler geprüft", subtitle: 'Ähnliche Schreibweisen im Lebenslauf gesucht, z. B. "Dockr"' },
      { title: "Score berechnet", subtitle: "Pflicht-Abdeckung in Prozent ermittelt" },
      { title: "Ergebnis aufbereitet", subtitle: "Bericht für die Anzeige vorbereitet" },
    ],
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
    emptyMissing: "Nichts fehlt: passt sehr gut.",
    foundLabel: (text) => `gefunden: "${text}"`,
    tipsHeading: "Bevor du diesen Lebenslauf abschickst",
    tipsEmpty: "Keine Änderungen nötig: dieser Lebenslauf deckt alles ab, was die Anzeige verlangt.",
    tipFix: (found, alias, name) =>
      `Schreibe "${found}" als exakten Begriff "${alias}", damit es als ${name} erkannt wird.`,
    tipRequired: (name) => `Ergänze Belege für ${name}: das ist laut Anzeige ein Pflicht-Skill.`,
    tipOptional: (name) => `Erwähne ${name}, falls vorhanden: laut Anzeige von Vorteil.`,
    infoTitle: "Was ist ein ATS, und warum gibt's Pass The Bot?",
    infoBody1:
      "Ein Applicant Tracking System (ATS) ist die Software, die heute fast jede große Firma vor die eigentliche Bewerbung schaltet. Bevor ein Mensch deinen Lebenslauf überhaupt sieht, durchsucht das System ihn nach Keywords aus der Stellenanzeige: automatisiert, in Sekunden, für hunderte Bewerbungen gleichzeitig.",
    infoBodyPipeline:
      "Auch wenn sich einzelne Systeme unterscheiden, folgen die meisten ATS-Lösungen einem ähnlichen Ablauf: Der Lebenslauf wird als Datei eingelesen und der reine Text daraus extrahiert. Das System erkennt typische Abschnitte wie Berufserfahrung, Ausbildung und Skills, normalisiert den Text (Groß-/Kleinschreibung, Sonderzeichen, Schreibvarianten) und zerlegt ihn in einzelne Begriffe. Parallel dazu werden aus der Stellenanzeige die Anforderungen extrahiert und in Pflicht- und Kür-Kriterien getrennt. Danach vergleicht das System beide Seiten Begriff für Begriff, oft ergänzt um einen Fuzzy-Abgleich für Tippfehler und Schreibvarianten. Am Ende steht ein Score oder Ranking, das mitentscheidet, ob eine Bewerbung überhaupt bei einem Menschen landet.",
    infoBody2:
      'Das Problem: Diese Systeme sind oft gnadenlos wörtlich. Schreibst du "JS" statt "JavaScript", "Python" statt "python" oder hast einen simplen Tippfehler wie "Dockr" statt "Docker", dann zählt das für viele ATS-Filter als "nicht vorhanden". Qualifizierte Bewerber:innen fliegen raus, nicht weil ihnen die Skills fehlen, sondern weil die Formulierung nicht exakt passt.',
    infoBody3:
      "Gleichzeitig nutzen immer mehr Bewerber:innen KI, um Lebensläufe zu schreiben, und Firmen nutzen KI, um sie auszusortieren. Am Ende entscheiden zwei Blackboxen übereinander, ohne dass irgendjemand genau weiß, warum.",
    infoBody4:
      "Pass The Bot dreht das um: Lass deine Bewerbung hier durchlaufen, bevor du sie irgendwo hochlädst, mit der gleichen nachvollziehbaren Logik, die viele echte ATS-Systeme verwenden. Schwarz auf weiß, welche Skills erkannt wurden, welche knapp danebenlagen und welche fehlen. Keine Blackbox, keine Überraschung.",
    privacyNote:
      "Diagnose statt KI-Blackbox: Das System entscheidet deterministisch und nachvollziehbar, warum ein Keyword-Filter dich durchlässt oder aussortiert, ohne deinen Lebenslauf umzuschreiben. Deine Daten werden dabei nicht gespeichert, nicht zum Trainieren eines Modells verwendet, und diese Seite setzt keine Cookies: alles bleibt in deinem Browser und wird nur für diese eine Prüfung an die Analyse-Engine geschickt.",
  },
  en: {
    pageTitle: "Pass The Bot! See your CV the way the machine sees it",
    tagline: "See your resume the way an Applicant Tracking System (ATS) sees it.",
    desc1: 'Paste a job posting, upload your CV, and get an instant, transparent breakdown: which required skills matched, which were near-misses caught by typos or phrasing (like "Dockr" vs "Docker"), and which are genuinely missing.',
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
    progressSteps: [
      { title: "Resume file opened", subtitle: "Reading the PDF or DOCX" },
      { title: "Text extracted", subtitle: "Raw text pulled from the file" },
      { title: "Job posting read", subtitle: "Posting text loaded" },
      { title: "Skills detected in the posting", subtitle: "Matched against the skill graph" },
      { title: "Soft skills detected in the posting", subtitle: "Compared by embedding similarity" },
      { title: "Skills detected in your resume", subtitle: "Matched against the skill graph" },
      { title: "Soft skills detected in your resume", subtitle: "Compared by embedding similarity" },
      { title: "Required skills identified", subtitle: 'Signal phrases like "required" or "must have"' },
      { title: "Nice-to-haves identified", subtitle: 'Signal phrases like "nice to have" or "a plus"' },
      { title: "Direct matching", subtitle: "Skill IDs from posting and resume compared" },
      { title: "Typos checked", subtitle: 'Similar spellings searched for, e.g. "Dockr"' },
      { title: "Score calculated", subtitle: "Required-skill coverage computed as a percentage" },
      { title: "Report assembled", subtitle: "Result prepared for display" },
    ],
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
    emptyMissing: "Nothing missing, great fit.",
    foundLabel: (text) => `found "${text}"`,
    tipsHeading: "Before you submit this resume",
    tipsEmpty: "No changes needed: this resume covers everything the posting asks for.",
    tipFix: (found, alias, name) =>
      `Fix "${found}" to the exact term "${alias}" so it's recognized as ${name}.`,
    tipRequired: (name) => `Add evidence of ${name}: this is listed as a required skill in the posting.`,
    tipOptional: (name) => `Consider mentioning ${name} if you have it: it's listed as a nice-to-have.`,
    infoTitle: "What is an ATS, and why does Pass The Bot exist?",
    infoBody1:
      "An Applicant Tracking System (ATS) is the software almost every large company runs your application through before a human ever sees it. It scans your resume for keywords from the job posting: automatically, in seconds, across hundreds of applications at once.",
    infoBodyPipeline:
      "While individual systems differ, most ATS solutions follow a similar flow: your resume is read as a file and the raw text is extracted from it. The system detects typical sections like work experience, education, and skills, normalizes the text (casing, special characters, spelling variants), and breaks it down into individual terms. In parallel, requirements are extracted from the job posting and split into required and nice-to-have criteria. It then compares both sides term by term, often with fuzzy matching for typos and spelling variants layered on top. The result is a score or ranking that helps decide whether an application ever reaches a human at all.",
    infoBody2:
      'The problem: these systems are often ruthlessly literal. Write "JS" instead of "JavaScript", "Python" instead of "python", or make a simple typo like "Dockr" instead of "Docker", and many ATS filters will count that skill as missing. Qualified candidates get filtered out, not because they lack the skill, but because the wording didn\'t match exactly.',
    infoBody3:
      "Meanwhile, more and more candidates use AI to write their resumes, and more and more companies use AI to filter them out. In the end, two black boxes are deciding against each other, and nobody really knows why.",
    infoBody4:
      "Pass The Bot flips that around: run your application through here before you submit it anywhere, using the same kind of deterministic, explainable logic many real ATS systems use. See in plain sight which skills were recognized, which were close misses, and which are missing. No black box, no surprises.",
    privacyNote:
      "A diagnosis, not an AI black box: the system decides deterministically and transparently why a keyword filter would pass or reject you, without rewriting your resume for you. None of your data is stored or used to train anything, and this page sets no cookies: everything stays in your browser and is sent to the analysis engine only for this one check.",
  },
};

let currentLang = "de";
let lastReport = null;

const form = document.getElementById("check-form");
const submitBtn = document.getElementById("submit-btn");
const submitBtnLabel = document.getElementById("submit-btn-label");
const progressWrap = document.getElementById("progress-wrap");
const progressStepEl = document.getElementById("progress-step");
const progressStepTitleEl = document.getElementById("progress-step-title");
const progressStepSubtitleEl = document.getElementById("progress-step-subtitle");
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
  if (lang === currentLang) return;
  const fadeTargets = document.querySelectorAll("[data-i18n], [data-i18n-placeholder]");
  fadeTargets.forEach((el) => el.classList.add("lang-fading"));
  setTimeout(() => {
    currentLang = lang;
    applyStaticTranslations();
    if (lastReport) {
      renderResults(lastReport, { scroll: false });
    }
    fadeTargets.forEach((el) => el.classList.remove("lang-fading"));
  }, 250);
}

langDeBtn.addEventListener("click", () => setLang("de"));
langEnBtn.addEventListener("click", () => setLang("en"));

const infoBtn = document.getElementById("info-btn");
const infoModal = document.getElementById("info-modal");
const infoModalClose = document.getElementById("info-modal-close");
const infoModalBackdrop = document.getElementById("info-modal-backdrop");

function openInfoModal() {
  infoModal.classList.remove("hidden");
}

function closeInfoModal() {
  infoModal.classList.add("hidden");
}

infoBtn.addEventListener("click", openInfoModal);
infoModalClose.addEventListener("click", closeInfoModal);
infoModalBackdrop.addEventListener("click", closeInfoModal);
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeInfoModal();
});

const postingTextarea = document.getElementById("posting_text");
const postingPlaceholder = document.getElementById("posting-placeholder");

function syncPostingPlaceholder() {
  postingPlaceholder.classList.toggle("hidden", postingTextarea.value.length > 0);
}

postingTextarea.addEventListener("input", syncPostingPlaceholder);

const FILE_UPLOAD_ICON = `<svg width="28" height="28" viewBox="0 0 28 28" class="mb-1">
  <circle cx="14" cy="14" r="13" fill="none" stroke="#9ca3af" stroke-width="1.5"></circle>
  <path d="M14 8 V20 M8 14 H20" stroke="#9ca3af" stroke-width="1.5" stroke-linecap="round"></path>
</svg>`;

function resetFileNameDisplay() {
  fileNameDisplay.innerHTML = `${FILE_UPLOAD_ICON}<span>${t("fileHint")}</span><span class="text-gray-400">${t("fileTypes")}</span>`;
}

fileInput.addEventListener("change", () => {
  const file = fileInput.files[0];
  if (file) {
    fileNameDisplay.textContent = file.name;
  } else {
    resetFileNameDisplay();
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

let loadingAnimationActive = false;

function startGaugeLoadingAnimation() {
  loadingAnimationActive = true;
  gaugeCircle.classList.add("gauge-loading");
  const start = performance.now();
  function loop(now) {
    if (!loadingAnimationActive) return;
    const elapsed = (now - start) / 1000;
    const fakePct = 50 + 45 * Math.sin(elapsed * 1.4);
    const offset = GAUGE_CIRCUMFERENCE * (1 - fakePct / 100);
    gaugeCircle.setAttribute("stroke-dashoffset", offset);
    gaugeCircle.setAttribute("stroke", gaugeColorFor(fakePct));
    requestAnimationFrame(loop);
  }
  requestAnimationFrame(loop);
}

function stopGaugeLoadingAnimation() {
  loadingAnimationActive = false;
  gaugeCircle.classList.remove("gauge-loading");
}

function animateGaugeTo(pct) {
  stopGaugeLoadingAnimation();
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
  submitBtnLabel.textContent = t("analyzing");
  progressWrap.classList.remove("hidden");
  gaugeText.textContent = "…";
  startGaugeLoadingAnimation();

  let stepIndex = 0;
  const steps = t("progressSteps");

  function renderStep(index) {
    const step = steps[index];
    const number = String(index + 1).padStart(2, "0");
    progressStepTitleEl.textContent = `${number} · ${step.title}`;
    progressStepSubtitleEl.textContent = step.subtitle;
  }

  renderStep(0);
  const stepInterval = setInterval(() => {
    if (stepIndex >= steps.length - 1) {
      clearInterval(stepInterval);
      return;
    }
    stepIndex += 1;
    progressStepEl.classList.add("fading");
    setTimeout(() => {
      renderStep(stepIndex);
      progressStepEl.classList.remove("fading");
    }, 500);
  }, 5000);

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
    clearInterval(stepInterval);
    stopGaugeLoadingAnimation();
    submitBtn.disabled = false;
    submitBtnLabel.textContent = t("analyzeBtn");
    progressWrap.classList.add("hidden");
  }
});

applyStaticTranslations();
