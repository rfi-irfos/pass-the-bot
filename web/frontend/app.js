const API_BASE_URL = "https://passthebot-api.fly.dev";
const GAUGE_CIRCUMFERENCE = 2 * Math.PI * 60;

const TRANSLATIONS = {
  de: {
    pageTitle: "Pass The Bot! Sieh deinen Lebenslauf wie ein Bewerbermanagementsystem (ATS)",
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
    analyzing: "Dein Lebenslauf wird analysiert",
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
    postingNotUnderstood:
      "Wir konnten aus dieser Stellenanzeige keine klaren Anforderungen erkennen. Die Prozentzahl unten ist daher nicht aussagekräftig.",
    downloadFailed: "Der Bericht konnte nicht erstellt werden. Bitte versuche es erneut.",
    atsResultHeading: "ATS-Ergebnis",
    downloadReportBtn: "Herunterladen",
    scorePrompt: "Starte oben eine Prüfung, um hier dein Ergebnis zu sehen.",
    scoreSummary: (pct, matched, total) =>
      `Dein Lebenslauf erfüllt ${pct}% der geforderten Skills und Keywords aus dieser Anzeige (${matched}/${total} Pflicht-Skills).`,
    matchedHeading: "Gefundene Skills",
    nearMissHeading: "Knapp daneben",
    missingHeading: "Fehlende Skills",
    emptyMatched: "Noch nichts gefunden.",
    emptyNearMiss: "Keine Beinahe-Treffer.",
    emptyMissing: "Nichts fehlt: passt sehr gut.",
    foundLabel: (text) => `gefunden: "${text}"`,
    openMatchTooltip: "Ähnlichkeitsbasiert erkannt, nicht aus dem kuratierten Katalog",
    tipsHeading: "Bevor du diesen Lebenslauf abschickst",
    tipsEmpty: "Keine Änderungen nötig: dieser Lebenslauf deckt alles ab, was die Anzeige verlangt.",
    tipFix: (found, alias, name) =>
      `Schreibe "${found}" als exakten Begriff "${alias}", damit es als ${name} erkannt wird.`,
    tipFixOpen: (name) =>
      `Dein Lebenslauf deckt "${name}" vielleicht schon ab, aber nicht eindeutig genug: die Anzeige verlangt das explizit und es wurde nicht sicher erkannt.`,
    tipRequired: (name) => `Ergänze Belege für ${name}: das ist laut Anzeige ein Pflicht-Skill.`,
    tipOptional: (name) => `Erwähne ${name}, falls vorhanden: laut Anzeige von Vorteil.`,
    tipMissingSection: (name) =>
      `Ergänze einen "${name}"-Abschnitt: dein Lebenslauf enthält aktuell keine erkennbare "${name}"-Überschrift.`,
    tipMissingContact:
      "Kein Kontaktbereich erkannt: entweder fehlt er wirklich, oder er ist im PDF nicht als durchsuchbarer Text gespeichert (z. B. wenn der Kopfbereich als Bild oder mit einer Sonderschrift ohne Textzuordnung exportiert wurde). In letzterem Fall übersehen viele echte ATS-Systeme deinen Namen, Ort oder deine E-Mail auf dieselbe Weise. Prüfe, ob du den Text im Kopfbereich deiner PDF markieren und kopieren kannst.",
    pipelineStep1: "1. Stellenanzeige",
    pipelineStep2: "2. Bewerbung",
    pipelineStep3: "3. Parsing",
    pipelineStep4: "4. Keyword-Match",
    pipelineStep5: "5. Recruiter-Review",
    pipelineStep6: "6. Entscheidung",
    infoTitle: "Was ist ein ATS, und warum gibt's Pass The Bot?",
    infoBody1:
      "Ein <strong>Applicant Tracking System (ATS)</strong> ist die Software, die heute fast jede große Firma vor die eigentliche Bewerbung schaltet. Bevor ein Mensch deinen Lebenslauf überhaupt sieht, durchsucht das System ihn nach Keywords aus der Stellenanzeige: <strong>automatisiert, in Sekunden</strong>, für hunderte Bewerbungen gleichzeitig.",
    infoBodyPipeline:
      "Auch wenn sich einzelne Systeme unterscheiden, folgen die meisten ATS-Lösungen einem ähnlichen Ablauf: Der Lebenslauf wird als Datei eingelesen und der reine Text daraus extrahiert. Das System erkennt typische Abschnitte wie Berufserfahrung, Ausbildung und Skills, normalisiert den Text (Groß-/Kleinschreibung, Sonderzeichen, Schreibvarianten) und zerlegt ihn in einzelne Begriffe. Parallel dazu werden aus der Stellenanzeige die Anforderungen extrahiert und in Pflicht- und Kür-Kriterien getrennt. Danach vergleicht das System beide Seiten Begriff für Begriff, oft ergänzt um einen Fuzzy-Abgleich für Tippfehler und Schreibvarianten. Am Ende steht ein <strong>Score oder Ranking</strong>, das mitentscheidet, ob eine Bewerbung überhaupt bei einem Menschen landet.",
    infoBody2:
      'Das Problem: Diese Systeme sind oft gnadenlos wörtlich. Schreibst du "JS" statt "JavaScript", "Python" statt "python" oder hast einen simplen Tippfehler wie "Dockr" statt "Docker", dann zählt das für viele ATS-Filter als "nicht vorhanden". Qualifizierte Bewerber:innen fliegen raus, <strong>nicht weil ihnen die Skills fehlen, sondern weil die Formulierung nicht exakt passt</strong>.',
    infoBody3:
      "Gleichzeitig nutzen immer mehr Bewerber:innen KI, um Lebensläufe zu schreiben, und Firmen nutzen KI, um sie auszusortieren. Am Ende entscheiden <strong>zwei Blackboxen übereinander</strong>, ohne dass irgendjemand genau weiß, warum.",
    infoBody4:
      "Pass The Bot dreht das um: Lass deine Bewerbung hier durchlaufen, bevor du sie irgendwo hochlädst, mit der gleichen nachvollziehbaren Logik, die viele echte ATS-Systeme verwenden. Schwarz auf weiß, welche Skills erkannt wurden, welche knapp danebenlagen und welche fehlen. <strong>Keine Blackbox, keine Überraschung.</strong>",
    privacyNote:
      "Diagnose statt KI-Blackbox: Das System entscheidet deterministisch und nachvollziehbar, warum ein Keyword-Filter dich durchlässt oder aussortiert, ohne deinen Lebenslauf umzuschreiben. Deine Daten werden dabei nicht gespeichert, nicht zum Trainieren eines Modells verwendet, und diese Seite setzt keine Cookies: alles bleibt in deinem Browser und wird nur für diese eine Prüfung an die Analyse-Engine geschickt.",
    coffeeLink: "Kauf uns einen Glückskeks",
    keywordCoverageHeading: "Keyword-Abdeckung",
    exactMatchLabel: "Exakte Treffer",
    semanticMatchLabel: "Sinngemäße Treffer",
    openMatchLabel: "Branchenübergreifend erkannt",
    totalKeywordsLabel: "Insgesamt abgedeckt",
    sectionAnalysisHeading: "Abschnitts-Analyse",
    sectionNames: {
      contact: "Kontakt",
      experience: "Erfahrung",
      education: "Ausbildung",
      skills: "Skills",
    },
    sectionFound: "vorhanden",
    sectionMissing: "nicht gefunden",
    sectionWordsUnit: "Wörter",
    radarHeading: "ATS-Radar",
    radarRequiredSkills: "Pflicht-Skills",
    radarSoftSkills: "Soft Skills",
    radarWordingAccuracy: "Formulierungsgenauigkeit",
    radarReadability: "Lesbarkeit",
    radarSectionCompleteness: "Abschnitts-Vollständigkeit",
  },
  en: {
    pageTitle: "Pass The Bot! See your CV the way an Applicant Tracking System (ATS) sees it",
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
    analyzing: "Analyzing your resume",
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
    postingNotUnderstood:
      "We couldn't identify any clear requirements in this job posting. The percentage below isn't meaningful as a result.",
    downloadFailed: "Could not generate the report. Please try again.",
    atsResultHeading: "ATS Result",
    downloadReportBtn: "Download",
    scorePrompt: "Run a check above to see your results here.",
    scoreSummary: (pct, matched, total) =>
      `Your resume matches ${pct}% of the required skills and keywords from this job posting (${matched}/${total} required).`,
    matchedHeading: "Matched Skills",
    nearMissHeading: "Near Misses",
    missingHeading: "Missing Skills",
    emptyMatched: "Nothing matched yet.",
    emptyNearMiss: "No near-misses found.",
    emptyMissing: "Nothing missing, great fit.",
    foundLabel: (text) => `found "${text}"`,
    openMatchTooltip: "Detected by similarity, not from the curated catalog",
    tipsHeading: "Before you submit this resume",
    tipsEmpty: "No changes needed: this resume covers everything the posting asks for.",
    tipFix: (found, alias, name) =>
      `Fix "${found}" to the exact term "${alias}" so it's recognized as ${name}.`,
    tipFixOpen: (name) =>
      `Your resume may already cover "${name}", but not clearly enough: the posting is looking for this and it wasn't confidently matched.`,
    tipRequired: (name) => `Add evidence of ${name}: this is listed as a required skill in the posting.`,
    tipOptional: (name) => `Consider mentioning ${name} if you have it: it's listed as a nice-to-have.`,
    tipMissingSection: (name) =>
      `Add a "${name}" section: your resume doesn't have a recognizable "${name}" heading right now.`,
    tipMissingContact:
      "No contact section detected: either it's genuinely missing, or it isn't stored as searchable text in the PDF (e.g. if the header was exported as an image or with a custom font that has no text mapping). In the latter case, many real ATS systems miss your name, location, or email the same way. Try selecting and copying the text in your PDF's header to check.",
    pipelineStep1: "1. Job Posting",
    pipelineStep2: "2. Application",
    pipelineStep3: "3. Parsing",
    pipelineStep4: "4. Keyword Match",
    pipelineStep5: "5. Recruiter Review",
    pipelineStep6: "6. Decision",
    infoTitle: "What is an ATS, and why does Pass The Bot exist?",
    infoBody1:
      "An <strong>Applicant Tracking System (ATS)</strong> is the software almost every large company runs your application through before a human ever sees it. It scans your resume for keywords from the job posting: <strong>automatically, in seconds</strong>, across hundreds of applications at once.",
    infoBodyPipeline:
      "While individual systems differ, most ATS solutions follow a similar flow: your resume is read as a file and the raw text is extracted from it. The system detects typical sections like work experience, education, and skills, normalizes the text (casing, special characters, spelling variants), and breaks it down into individual terms. In parallel, requirements are extracted from the job posting and split into required and nice-to-have criteria. It then compares both sides term by term, often with fuzzy matching for typos and spelling variants layered on top. The result is a <strong>score or ranking</strong> that helps decide whether an application ever reaches a human at all.",
    infoBody2:
      'The problem: these systems are often ruthlessly literal. Write "JS" instead of "JavaScript", "Python" instead of "python", or make a simple typo like "Dockr" instead of "Docker", and many ATS filters will count that skill as missing. Qualified candidates get filtered out, <strong>not because they lack the skill, but because the wording didn\'t match exactly</strong>.',
    infoBody3:
      "Meanwhile, more and more candidates use AI to write their resumes, and more and more companies use AI to filter them out. In the end, <strong>two black boxes are deciding against each other</strong>, and nobody really knows why.",
    infoBody4:
      "Pass The Bot flips that around: run your application through here before you submit it anywhere, using the same kind of deterministic, explainable logic many real ATS systems use. See in plain sight which skills were recognized, which were close misses, and which are missing. <strong>No black box, no surprises.</strong>",
    privacyNote:
      "A diagnosis, not an AI black box: the system decides deterministically and transparently why a keyword filter would pass or reject you, without rewriting your resume for you. None of your data is stored or used to train anything, and this page sets no cookies: everything stays in your browser and is sent to the analysis engine only for this one check.",
    coffeeLink: "Buy us a fortune cookie",
    keywordCoverageHeading: "Keyword Coverage",
    exactMatchLabel: "Exact Matches",
    semanticMatchLabel: "Semantic Matches",
    openMatchLabel: "Detected Across Industries",
    totalKeywordsLabel: "Total Covered",
    sectionAnalysisHeading: "Resume Section Analysis",
    sectionNames: {
      contact: "Contact",
      experience: "Experience",
      education: "Education",
      skills: "Skills",
    },
    sectionFound: "found",
    sectionMissing: "not found",
    sectionWordsUnit: "words",
    radarHeading: "ATS Radar",
    radarRequiredSkills: "Required Skills",
    radarSoftSkills: "Soft Skills",
    radarWordingAccuracy: "Wording Accuracy",
    radarReadability: "Readability",
    radarSectionCompleteness: "Section Completeness",
  },
};

let currentLang = "de";
let lastReport = null;

const form = document.getElementById("check-form");
const submitBtn = document.getElementById("submit-btn");
const submitBtnLabel = document.getElementById("submit-btn-label");
const submitBtnDots = document.getElementById("submit-btn-dots");
const progressWrap = document.getElementById("progress-wrap");
const progressBarEl = document.getElementById("progress-bar");
const progressStepEl = document.getElementById("progress-step");
const progressStepTitleEl = document.getElementById("progress-step-title");
const progressStepSubtitleEl = document.getElementById("progress-step-subtitle");
const errorBox = document.getElementById("error-box");
const resultsCard = document.getElementById("results-card");
const downloadReportBtn = document.getElementById("download-report-btn");
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
const exactMatchCount = document.getElementById("exact-match-count");
const exactMatchBar = document.getElementById("exact-match-bar");
const semanticMatchCount = document.getElementById("semantic-match-count");
const semanticMatchBar = document.getElementById("semantic-match-bar");
const openMatchRow = document.getElementById("open-match-row");
const openMatchCount = document.getElementById("open-match-count");
const openMatchBar = document.getElementById("open-match-bar");
const totalKeywordCount = document.getElementById("total-keyword-count");
const sectionAnalysisList = document.getElementById("section-analysis-list");

const radarPolygon = document.getElementById("radar-polygon");
const radarRingsEl = document.getElementById("radar-rings");
const radarSpokesEl = document.getElementById("radar-spokes");
const radarDotsEl = document.getElementById("radar-dots");
const radarLabelsEl = document.getElementById("radar-labels");

const SECTION_COLORS = {
  contact: { dot: "bg-blue-500", bar: "bg-blue-500", badge: "bg-blue-100 text-blue-800" },
  experience: { dot: "bg-purple-500", bar: "bg-purple-500", badge: "bg-purple-100 text-purple-800" },
  education: { dot: "bg-amber-500", bar: "bg-amber-500", badge: "bg-amber-100 text-amber-800" },
  skills: { dot: "bg-cyan-600", bar: "bg-cyan-600", badge: "bg-cyan-100 text-cyan-800" },
};

const RADAR_AXES = [
  { key: "required_skills_pct", labelKey: "radarRequiredSkills", color: "#16a34a" },
  { key: "soft_skills_pct", labelKey: "radarSoftSkills", color: "#2563eb" },
  { key: "wording_accuracy_pct", labelKey: "radarWordingAccuracy", color: "#9333ea" },
  { key: "readability_pct", labelKey: "radarReadability", color: "#f59e0b" },
  { key: "section_completeness_pct", labelKey: "radarSectionCompleteness", color: "#0891b2" },
];

function t(key) {
  return TRANSLATIONS[currentLang][key];
}

function applyStaticTranslations() {
  document.documentElement.lang = currentLang;
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    el.textContent = t(el.dataset.i18n);
  });
  // [data-i18n-html] is only used for a handful of static, hardcoded info-
  // modal paragraphs (never user-supplied text) that need inline <strong>
  // emphasis -- everything else stays on the safe textContent path above.
  document.querySelectorAll("[data-i18n-html]").forEach((el) => {
    el.innerHTML = t(el.dataset.i18nHtml);
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
  const fadeTargets = document.querySelectorAll("[data-i18n], [data-i18n-html], [data-i18n-placeholder]");
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

    const label = document.createElement("span");
    label.className = "font-medium";
    label.textContent = item.display_name;
    li.appendChild(label);

    if (item.origin === "open") {
      const marker = document.createElement("span");
      marker.className = "text-gray-400 ml-1";
      marker.title = t("openMatchTooltip");
      marker.textContent = "~";
      li.appendChild(marker);
    }

    if (item.status === "NEAR_MISS" && item.suggested_alias) {
      li.appendChild(document.createElement("br"));
      const foundSpan = document.createElement("span");
      foundSpan.className = "text-gray-500";
      foundSpan.textContent = t("foundLabel")(item.found_text);
      li.appendChild(foundSpan);
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
    if (item.origin === "open") {
      tips.push(t("tipFixOpen")(item.display_name));
    } else {
      tips.push(t("tipFix")(item.found_text, item.suggested_alias, item.display_name));
    }
  }
  for (const item of missingRequired) {
    tips.push(t("tipRequired")(item.display_name));
  }
  for (const item of missingOptional) {
    tips.push(t("tipOptional")(item.display_name));
  }
  if (report.metrics && report.metrics.sections) {
    for (const section of report.metrics.sections) {
      if (!section.found) {
        if (section.id === "contact") {
          tips.push(t("tipMissingContact"));
        } else {
          const name = t("sectionNames")[section.id] || section.id;
          tips.push(t("tipMissingSection")(name));
        }
      }
    }
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

const SVG_NS = "http://www.w3.org/2000/svg";

function radarValueColor(pct) {
  if (pct >= 80) return "#16a34a";
  if (pct >= 50) return "#f59e0b";
  return "#dc2626";
}

function renderRadar(radar) {
  const axes = RADAR_AXES.filter((a) => radar[a.key] !== null && radar[a.key] !== undefined);
  const centerX = 115;
  const centerY = 115;
  const maxRadius = 62;
  const labelRadius = maxRadius + 26;
  const angleStep = (2 * Math.PI) / axes.length;

  function pointAt(index, valuePct, radius = maxRadius) {
    const angle = -Math.PI / 2 + index * angleStep;
    const r = (valuePct / 100) * radius;
    return [centerX + r * Math.cos(angle), centerY + r * Math.sin(angle)];
  }

  // Concentric rings at 100/75/50/25% give the chart real depth instead of
  // a single flat backdrop polygon. Drawn outer-to-inner so each smaller
  // polygon paints over the larger one beneath it, leaving a visible
  // alternating band between each pair of levels.
  radarRingsEl.innerHTML = "";
  [100, 75, 50, 25].forEach((ringPct, ringIndex) => {
    const ring = document.createElementNS(SVG_NS, "polygon");
    ring.setAttribute(
      "points",
      axes.map((axis, i) => pointAt(i, ringPct, maxRadius).join(",")).join(" ")
    );
    ring.setAttribute("fill", ringIndex % 2 === 0 ? "#eef2f7" : "#ffffff");
    ring.setAttribute("stroke", "#cbd5e1");
    ring.setAttribute("stroke-width", "1");
    radarRingsEl.appendChild(ring);
  });

  // Spokes from center to each axis's 100% vertex.
  radarSpokesEl.innerHTML = "";
  axes.forEach((axis, i) => {
    const [x, y] = pointAt(i, 100, maxRadius);
    const spoke = document.createElementNS(SVG_NS, "line");
    spoke.setAttribute("x1", centerX);
    spoke.setAttribute("y1", centerY);
    spoke.setAttribute("x2", x);
    spoke.setAttribute("y2", y);
    spoke.setAttribute("stroke", "#cbd5e1");
    spoke.setAttribute("stroke-width", "1");
    radarSpokesEl.appendChild(spoke);
  });

  radarPolygon.setAttribute(
    "points",
    axes.map((axis, i) => pointAt(i, radar[axis.key]).join(",")).join(" ")
  );

  // One colored dot per axis at its real data point, tinted by that axis's
  // own value (red/amber/green) so a weak axis is visible at a glance, not
  // just legible in the label text.
  radarDotsEl.innerHTML = "";
  axes.forEach((axis, i) => {
    const [x, y] = pointAt(i, radar[axis.key]);
    const dot = document.createElementNS(SVG_NS, "circle");
    dot.setAttribute("cx", x);
    dot.setAttribute("cy", y);
    dot.setAttribute("r", "4");
    dot.setAttribute("fill", radarValueColor(radar[axis.key]));
    dot.setAttribute("stroke", "#ffffff");
    dot.setAttribute("stroke-width", "1.5");
    radarDotsEl.appendChild(dot);
  });

  radarLabelsEl.innerHTML = "";
  axes.forEach((axis, i) => {
    const [x, y] = pointAt(i, 100, labelRadius);
    const angle = -Math.PI / 2 + i * angleStep;
    const cos = Math.cos(angle);
    let alignClass = "-translate-x-1/2 text-center";
    if (cos > 0.35) alignClass = "text-left";
    else if (cos < -0.35) alignClass = "-translate-x-full text-right";

    const label = document.createElement("div");
    label.className = `absolute -translate-y-1/2 leading-tight w-20 break-words ${alignClass}`;
    label.style.left = `${x}px`;
    label.style.top = `${y}px`;
    const value = Math.round(radar[axis.key]);
    label.innerHTML = `
      <div class="text-[10px] font-semibold text-gray-700">${t(axis.labelKey)}</div>
      <div class="text-[10px] font-bold" style="color: ${radarValueColor(value)}">${value}%</div>
    `;
    radarLabelsEl.appendChild(label);
  });
}

function revealResultSections() {
  const sections = resultsCard.querySelectorAll("[data-reveal]");
  sections.forEach((el) => el.classList.remove("revealed"));
  sections.forEach((el, i) => {
    setTimeout(() => el.classList.add("revealed"), i * 130);
  });
}

function renderResults(report, { scroll = true } = {}) {
  lastReport = report;
  const pct = report.score.coverage_pct;
  animateGaugeTo(pct);

  const postingUnderstood = !report.metrics || report.metrics.posting_understood !== false;
  scoreSummary.textContent = postingUnderstood
    ? t("scoreSummary")(pct, report.score.required_matched, report.score.required_total)
    : `${t("postingNotUnderstood")} ${t("scoreSummary")(pct, report.score.required_matched, report.score.required_total)}`;

  const matched = report.results.filter((r) => r.status === "MATCH");
  const nearMiss = report.results.filter((r) => r.status === "NEAR_MISS");
  const missing = report.results.filter((r) => r.status === "MISSING");

  countMatched.textContent = matched.length;
  countNearMiss.textContent = nearMiss.length;
  countMissing.textContent = missing.length;

  // report.metrics is a newer field the frontend may be serving ahead of a
  // matching backend deploy (web/frontend deploys automatically on merge,
  // the Fly backend deploys separately/manually). If it's missing, skip
  // these three metrics-driven cards gracefully instead of throwing, so a
  // deploy-timing mismatch doesn't get mistaken for a network failure.
  if (report.metrics) {
    const breakdown = report.metrics.match_breakdown;
    const exactPct = breakdown.exact_total ? Math.round((breakdown.exact_matched / breakdown.exact_total) * 100) : 0;
    const semanticPct = breakdown.semantic_total ? Math.round((breakdown.semantic_matched / breakdown.semantic_total) * 100) : 0;
    exactMatchCount.textContent = `${breakdown.exact_matched} / ${breakdown.exact_total}`;
    exactMatchBar.style.width = `${exactPct}%`;
    semanticMatchCount.textContent = `${breakdown.semantic_matched} / ${breakdown.semantic_total}`;
    semanticMatchBar.style.width = `${semanticPct}%`;

    const openResults = report.results.filter((r) => r.origin === "open");
    if (openResults.length > 0) {
      const openMatched = openResults.filter((r) => r.status === "MATCH").length;
      const openPct = Math.round((openMatched / openResults.length) * 100);
      openMatchRow.classList.remove("hidden");
      openMatchCount.textContent = `${openMatched} / ${openResults.length}`;
      openMatchBar.style.width = `${openPct}%`;
    } else {
      openMatchRow.classList.add("hidden");
    }

    const openMatchedForTotal = openResults.filter((r) => r.status === "MATCH").length;
    const totalMatched = breakdown.exact_matched + breakdown.semantic_matched + openMatchedForTotal;
    const totalCount = breakdown.exact_total + breakdown.semantic_total + openResults.length;
    totalKeywordCount.textContent = `${totalMatched} / ${totalCount}`;

    sectionAnalysisList.innerHTML = "";
    for (const section of report.metrics.sections) {
      const li = document.createElement("li");
      const name = t("sectionNames")[section.id] || section.id;
      if (!section.found) {
        li.className = "flex items-center justify-between text-gray-400";
        li.innerHTML = `
          <span class="flex items-center gap-2"><span class="w-2 h-2 rounded-full bg-gray-300"></span>${name}</span>
          <span class="text-xs">${t("sectionMissing")}</span>
        `;
      } else {
        const pct = Math.min(100, Math.round((section.word_count / 15) * 100));
        const colors = SECTION_COLORS[section.id] || SECTION_COLORS.contact;
        const opacityClass = section.filled ? "" : "opacity-50";
        li.className = "space-y-1";
        li.innerHTML = `
          <div class="flex items-center justify-between flex-wrap gap-x-2 gap-y-1">
            <span class="flex items-center gap-2"><span class="w-2 h-2 rounded-full flex-shrink-0 ${colors.dot} ${opacityClass}"></span>${name}</span>
            <span class="text-xs font-medium px-2 py-0.5 rounded-full whitespace-nowrap ${colors.badge} ${opacityClass}">${section.word_count} ${t("sectionWordsUnit")}</span>
          </div>
          <div class="w-full bg-gray-100 rounded-full h-1.5"><div class="${colors.bar} ${opacityClass} h-1.5 rounded-full" style="width: ${pct}%"></div></div>
        `;
      }
      sectionAnalysisList.appendChild(li);
    }

    renderRadar(report.metrics.radar);
  }

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

      const bullet = document.createElement("span");
      bullet.textContent = "•";
      li.appendChild(bullet);

      const tipText = document.createElement("span");
      tipText.textContent = tip;
      li.appendChild(tipText);

      tipsList.appendChild(li);
    }
  }

  resultsCard.classList.remove("opacity-40");
  if (scroll) {
    resultsCard.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  downloadReportBtn.classList.remove("hidden");
  downloadReportBtn.classList.add("flex");

  revealResultSections();
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
  submitBtnDots.classList.remove("hidden");
  progressWrap.classList.remove("hidden");
  gaugeText.textContent = "…";
  startGaugeLoadingAnimation();

  let groupIndex = 0;
  const steps = t("progressSteps");

  function chunk(array, size) {
    const chunks = [];
    for (let i = 0; i < array.length; i += size) {
      chunks.push(array.slice(i, i + size));
    }
    return chunks;
  }

  // The backend now answers in well under a second (see the perf fix in
  // embeddings.py), far faster than a human can read even one of these
  // step labels. Pairing steps into groups and holding each group for a
  // fixed duration keeps the full sequence readable and visibly fills the
  // progress bar left-to-right, instead of either flashing by in one frame
  // or crawling through 13 separate single-line steps.
  const STEP_GROUP_MS = 3000;
  const stepGroups = chunk(steps, 2);
  const MIN_ANIMATE_MS = stepGroups.length * STEP_GROUP_MS;
  const startedAt = performance.now();

  function renderStepGroup(index) {
    const group = stepGroups[index];
    const [first, second] = group;
    const number = String(index * 2 + 1).padStart(2, "0");

    if (second) {
      progressStepTitleEl.textContent = `${number} · ${first.title} & ${second.title}`;
      progressStepSubtitleEl.textContent = `${first.subtitle} · ${second.subtitle}`;
    } else {
      progressStepTitleEl.textContent = `${number} · ${first.title}`;
      progressStepSubtitleEl.textContent = first.subtitle;
    }

    progressBarEl.style.width = `${((index + 1) / stepGroups.length) * 100}%`;
  }

  renderStepGroup(0);
  const stepInterval = setInterval(() => {
    if (groupIndex >= stepGroups.length - 1) {
      clearInterval(stepInterval);
      return;
    }
    groupIndex += 1;
    progressStepEl.classList.add("fading");
    setTimeout(() => {
      renderStepGroup(groupIndex);
      progressStepEl.classList.remove("fading");
    }, 150);
  }, STEP_GROUP_MS);

  // /api/check runs CPU-bound sentence-embedding inference on a small
  // shared-cpu-1x Fly machine; a realistic multi-paragraph resume can take
  // 10-20s+ to process, not just a transient network hiccup. The timeout
  // must comfortably clear that, or every real (non-toy) resume aborts
  // before the backend ever gets to respond. Bound each attempt and retry
  // once before surfacing an error, instead of waiting on the browser's own
  // (much longer) default timeout and showing a false "backend unreachable".
  async function fetchCheck() {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 45000);
    try {
      return await fetch(`${API_BASE_URL}/api/check`, {
        method: "POST",
        body: formData,
        signal: controller.signal,
      });
    } finally {
      clearTimeout(timeoutId);
    }
  }

  try {
    let response;
    try {
      response = await fetchCheck();
    } catch (networkErr) {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      response = await fetchCheck();
    }

    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      showError(body.detail || `Request failed (${response.status}).`);
      return;
    }

    const report = await response.json();

    const elapsed = performance.now() - startedAt;
    if (elapsed < MIN_ANIMATE_MS) {
      await new Promise((resolve) => setTimeout(resolve, MIN_ANIMATE_MS - elapsed));
    }

    renderResults(report);
  } catch (err) {
    showError(t("errorUnreachable"));
  } finally {
    clearInterval(stepInterval);
    stopGaugeLoadingAnimation();
    submitBtn.disabled = false;
    submitBtnLabel.textContent = t("analyzeBtn");
    submitBtnDots.classList.add("hidden");
    progressWrap.classList.add("hidden");
  }
});

downloadReportBtn.addEventListener("click", () => {
  // If the html2pdf CDN script failed to load (blocked by an ad-blocker or
  // corporate proxy), html2pdf() would throw synchronously with zero
  // feedback to the user. Check for it up front and surface an error
  // instead of silently doing nothing.
  if (typeof html2pdf === "undefined") {
    showError(t("downloadFailed"));
    return;
  }

  // html2canvas (bundled inside html2pdf.js) mis-locates the target element
  // inside its offscreen clone when the real page is scrolled away from the
  // top, producing a blank capture. Passing scrollX/scrollY compensation to
  // html2canvas alone does not reliably fix this in the bundled version, so
  // scroll the real window to the top before capture and restore the user's
  // scroll position afterward (including on failure).
  //
  // The page sets `scroll-behavior: smooth` globally (see <style> in
  // index.html), so a plain `window.scrollTo(0, 0)` animates over several
  // hundred ms instead of jumping instantly -- if the user had scrolled
  // down before clicking, html2canvas could start capturing mid-animation,
  // photographing a half-scrolled page and producing a blank/misaligned
  // PDF. Passing `behavior: "instant"` explicitly overrides the CSS
  // default for this one call.
  const { scrollX, scrollY } = window;
  window.scrollTo({ top: 0, left: 0, behavior: "instant" });

  // The button lives inside the captured element; hide it for the snapshot
  // so it doesn't show up inside the exported PDF, then restore it.
  downloadReportBtn.classList.add("hidden");
  downloadReportBtn.classList.remove("flex");
  function restoreButton() {
    downloadReportBtn.classList.remove("hidden");
    downloadReportBtn.classList.add("flex");
  }

  function restoreScroll() {
    window.scrollTo({ top: scrollY, left: scrollX, behavior: "instant" });
  }

  // Wait a frame after the instant scroll before measuring/capturing, so
  // the browser has actually applied the new scroll position and any
  // resulting layout reflow before html2canvas reads element geometry.
  requestAnimationFrame(() => {
    html2pdf()
      .set({
        html2canvas: {
          useCORS: true,
          scrollX: 0,
          scrollY: 0,
          windowWidth: document.documentElement.clientWidth,
          windowHeight: document.documentElement.clientHeight,
        },
      })
      .from(resultsCard)
      .save("pass-the-bot-report.pdf")
      .then(() => {
        restoreButton();
        restoreScroll();
      })
      .catch(() => {
        restoreButton();
        restoreScroll();
        showError(t("downloadFailed"));
      });
  });
});

applyStaticTranslations();

// Friendly fade/slide-in welcome on first paint, staggered so the icon
// settles in a beat after the text instead of both popping in at once.
requestAnimationFrame(() => {
  requestAnimationFrame(() => {
    document.getElementById("hero-text")?.classList.add("revealed");
    setTimeout(() => {
      document.getElementById("hero-icon")?.classList.add("revealed");
    }, 150);
  });
});
