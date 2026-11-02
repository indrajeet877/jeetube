const $ = (id) => document.getElementById(id);

const SAVED_STORAGE_KEY = "jeetube-saved-ids";
const DONE_CHAPTERS_KEY = "jeetube-done-chapters";
const LAYOUT_STORAGE_KEY = "jeetube-layout";

const WEIGHTAGE_ORDER = { "Very High": 3, High: 2, Medium: 1 };

// Common JEE student acronyms so searching "RBD", "GOC", "SOT", "AOD", "YDSE", "P&C" works instantaneously
const ACRONYM_ALIASES = {
  1: "inequalities wavy curve log modulus",
  2: "functions domain range",
  3: "quadratic location of roots",
  6: "pnc p&c combinatorics",
  8: "matrices determinants",
  11: "itf inverse trig",
  12: "sot properties of triangle",
  18: "limits lhospital",
  19: "lcd continuity differentiability",
  20: "mod differentiation",
  21: "aod maxima minima monotonicity tangent normal",
  24: "auc area under curve",
  26: "gif floor fractional part functional equations",
  28: "3d skew lines planes",
  30: "units dimensions vernier errors",
  31: "1d 2d projectile relative motion",
  32: "nlm friction pulley constraint",
  33: "wpe circular motion work energy",
  34: "com center of mass collision momentum",
  35: "rbd rotational moment of inertia rolling torque",
  37: "fluids surface tension viscosity bernoulli",
  39: "shm oscillations",
  42: "ktg kinetic theory thermodynamics",
  46: "mec biot savart magnetic effect",
  48: "emi faraday lenz inductance",
  49: "ac lcr em waves",
  50: "ray optics lens mirror prism",
  51: "ydse wave optics interference diffraction",
  54: "semiconductors logic gates diodes experimental vernier screw gauge",
  55: "mole stoichiometry",
  56: "redox titration n factor equivalent",
  60: "kp kc le chatelier",
  61: "ph buffer ksp ionic",
  67: "vsepr mot hybridization fajan bonding",
  68: "cft coordination ligands",
  71: "salt analysis qualitative s block",
  72: "iupac naming",
  73: "optical geometrical stereoisomerism chirality",
  74: "goc inductive resonance hyperconjugation aromaticity",
  75: "orm sn1 sn2 e1 e2 alkanes alkenes alkynes",
  76: "grignard alkyl halide",
  78: "carbonyl aldol cannizzaro",
  80: "poc polymers biomolecules",
};

const state = {
  syllabus: [],
  educators: [],
  videos: [],
  saved: new Set(),
  doneChapters: new Set(),
  subject: "All",        // "All" | "Mathematics" | "Physics" | "Chemistry" | "Saved"
  unit: "",              // "" or exact unit name (e.g. "Organic Chemistry", "Calculus", "Mechanics")
  chapterNo: 0,          // 0 = all chapters, 1..80 = isolated chapter
  goal: "all",           // "all" | "playlists" | "oneshot" | "revision" | "advanced"
  resourceType: "all",   // "all" | "playlist" | "youtube"
  exam: "all",           // "all" | "JEE Advanced" | "JEE Main + Advanced" | "JEE Main"
  classLevel: "all",     // "all" | "Class 11" | "Class 12"
  language: "all",       // "all" | "Hinglish" | "English"
  educator: "",          // "" or exact educator label
  sort: "chapterwise",   // "chapterwise" | "relevance" | "views" | "lessons" | "duration_desc" | "duration_asc" | "weightage"
  layout: "grid",        // "grid" | "list"
  query: "",
};

let liveAnnounceTimer = null;

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

function subjectSlug(subject) {
  if (subject === "Mathematics") return "math";
  if (subject === "Physics") return "phys";
  if (subject === "Chemistry") return "chem";
  return "all";
}

function teacherInitials(name) {
  const clean = name.replace(/\(.*?\)/g, "").trim();
  const words = clean.split(/\s+/).filter(Boolean);
  if (words.length >= 2) return (words[0][0] + words[1][0]).toUpperCase();
  return clean.slice(0, 2).toUpperCase();
}

function loadLocalSets() {
  try {
    const rawSaved = localStorage.getItem(SAVED_STORAGE_KEY);
    if (rawSaved) {
      const parsed = JSON.parse(rawSaved);
      if (Array.isArray(parsed)) state.saved = new Set(parsed);
    }
    const rawDone = localStorage.getItem(DONE_CHAPTERS_KEY);
    if (rawDone) {
      const parsedDone = JSON.parse(rawDone);
      if (Array.isArray(parsedDone)) state.doneChapters = new Set(parsedDone.map(Number));
    }
    const savedLayout = localStorage.getItem(LAYOUT_STORAGE_KEY);
    if (savedLayout === "grid" || savedLayout === "list") {
      state.layout = savedLayout;
    }
  } catch {}
}

function persistSaved() {
  try {
    localStorage.setItem(SAVED_STORAGE_KEY, JSON.stringify([...state.saved]));
  } catch {}
}

function persistDoneChapters() {
  try {
    localStorage.setItem(DONE_CHAPTERS_KEY, JSON.stringify([...state.doneChapters]));
  } catch {}
}

function persistLayout() {
  try {
    localStorage.setItem(LAYOUT_STORAGE_KEY, state.layout);
  } catch {}
}

function prepareVideo(video) {
  video._key = `${video.provider}:${video.video_id}`;
  video._haystack = [
    video.title,
    video.educator,
    video.channel,
    video.subject,
    video.unit,
    video.chapter,
    `ch ${video.chapter_no}`,
    `chapter ${video.chapter_no}`,
    ACRONYM_ALIASES[video.chapter_no] || "",
    video.class_level,
    video.target_exam,
    video.format,
    video.language,
    ...(video.sample_lectures || []).map((s) => s.title),
  ]
    .join("\n")
    .toLowerCase();
  return video;
}

/* URL State Sync */
function readUrlState() {
  const params = new URLSearchParams(window.location.search);
  const subj = params.get("subject");
  const unit = params.get("unit");
  const ch = Number(params.get("ch"));
  const goal = params.get("goal");
  const rtype = params.get("type");
  const exam = params.get("exam");
  const cls = params.get("class");
  const lang = params.get("lang");
  const edu = params.get("educator");
  const sort = params.get("sort");
  const q = params.get("q");

  if (subj && ["All", "Mathematics", "Physics", "Chemistry", "Saved"].includes(subj)) {
    state.subject = subj;
  }
  if (unit) state.unit = unit;
  if (Number.isInteger(ch) && ch >= 1 && ch <= 80) state.chapterNo = ch;
  if (goal && ["all", "playlists", "oneshot", "revision", "advanced"].includes(goal)) {
    state.goal = goal;
  }
  if (rtype && ["all", "playlist", "youtube"].includes(rtype)) {
    state.resourceType = rtype;
  }
  if (exam && ["all", "JEE Advanced", "JEE Main + Advanced", "JEE Main"].includes(exam)) {
    state.exam = exam;
  }
  if (cls && ["all", "Class 11", "Class 12"].includes(cls)) state.classLevel = cls;
  if (lang && ["all", "Hinglish", "English"].includes(lang)) state.language = lang;
  if (edu) state.educator = edu;
  if (
    sort &&
    ["chapterwise", "relevance", "views", "lessons", "duration_desc", "duration_asc", "weightage"].includes(sort)
  ) {
    state.sort = sort;
  }
  if (q) state.query = q;
}

function syncUrlState() {
  const params = new URLSearchParams();
  if (state.subject !== "All") params.set("subject", state.subject);
  if (state.unit) params.set("unit", state.unit);
  if (state.chapterNo) params.set("ch", String(state.chapterNo));
  if (state.goal !== "all") params.set("goal", state.goal);
  if (state.resourceType !== "all") params.set("type", state.resourceType);
  if (state.exam !== "all") params.set("exam", state.exam);
  if (state.classLevel !== "all") params.set("class", state.classLevel);
  if (state.language !== "all") params.set("lang", state.language);
  if (state.educator) params.set("educator", state.educator);
  if (state.sort !== "chapterwise") params.set("sort", state.sort);
  if (state.query.trim()) params.set("q", state.query.trim());

  const qs = params.toString();
  const nextUrl = qs ? `${window.location.pathname}?${qs}` : window.location.pathname;
  window.history.replaceState(null, "", nextUrl);
}

function hasActiveFilters() {
  return (
    state.subject !== "All" ||
    Boolean(state.unit) ||
    state.chapterNo !== 0 ||
    state.goal !== "all" ||
    state.resourceType !== "all" ||
    state.exam !== "all" ||
    state.classLevel !== "all" ||
    state.language !== "all" ||
    Boolean(state.educator) ||
    Boolean(state.query.trim())
  );
}

function matchesGoal(video) {
  if (state.goal === "playlists") return video.provider === "playlist";
  if (state.goal === "oneshot") return video.format === "One-Shot";
  if (state.goal === "revision") return video.format === "Revision & PYQs";
  if (state.goal === "advanced") {
    return video.format === "Adv Problems" || video.target_exam === "JEE Advanced";
  }
  return true;
}

function matchesWithoutChapter(video) {
  if (state.subject === "Saved") {
    if (!state.saved.has(video._key)) return false;
  } else if (state.subject !== "All" && video.subject !== state.subject) {
    return false;
  }
  if (state.unit && video.unit !== state.unit) return false;
  if (!matchesGoal(video)) return false;
  if (state.resourceType !== "all" && video.provider !== state.resourceType) return false;
  if (state.exam !== "all" && video.target_exam !== state.exam) return false;
  if (state.classLevel !== "all" && video.class_level !== state.classLevel) return false;
  if (state.language !== "all" && video.language !== state.language) return false;
  if (state.educator && video.educator !== state.educator) return false;

  const needle = state.query.trim().toLowerCase();
  if (!needle) return true;
  const terms = needle.split(/\s+/).filter(Boolean);
  return terms.every((t) => video._haystack.includes(t));
}

function matches(video) {
  if (state.chapterNo && video.chapter_no !== state.chapterNo) return false;
  return matchesWithoutChapter(video);
}

function announcePolite(message) {
  clearTimeout(liveAnnounceTimer);
  liveAnnounceTimer = setTimeout(() => {
    const live = $("live-status");
    if (live) live.textContent = message;
  }, 280);
}

/* System-Aware Two-State Theme Toggle (modern-web-guidance: dark-mode-toggle) */
function initThemeToggle() {
  const meta = document.querySelector('meta[name="color-scheme"]');
  const btn = $("theme-toggle");
  if (!meta || !btn) return;

  const applyMeta = (stored) => {
    meta.content = stored === "light" || stored === "dark" ? stored : "light dark";
  };

  btn.addEventListener("click", () => {
    const osDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const osScheme = osDark ? "dark" : "light";
    let stored = null;
    try {
      stored = localStorage.getItem("color-scheme");
    } catch {}

    const currentRendered = stored === "light" || stored === "dark" ? stored : osScheme;
    const target = currentRendered === "dark" ? "light" : "dark";

    if (target === osScheme) {
      try {
        localStorage.removeItem("color-scheme");
      } catch {}
      applyMeta(null);
    } else {
      try {
        localStorage.setItem("color-scheme", target);
      } catch {}
      applyMeta(target);
    }
  });

  window.addEventListener("storage", (event) => {
    if (event.key === "color-scheme") {
      applyMeta(event.newValue);
    }
  });
}

/* Light-Dismiss Fallback Helper for Dialogs (modern-web-guidance: light-dismiss-a-dialog) */
function attachDialogLightDismissFallback(dialog) {
  if (!dialog || "closedBy" in HTMLDialogElement.prototype) return;
  dialog.addEventListener("click", (event) => {
    if (event.target !== dialog) return;
    const rect = dialog.getBoundingClientRect();
    const inside =
      rect.top <= event.clientY &&
      event.clientY <= rect.top + rect.height &&
      rect.left <= event.clientX &&
      event.clientX <= rect.left + rect.width;
    if (!inside) dialog.close();
  });
}

function initDialogs() {
  const playerDialog = $("player-dialog");
  const playerStage = $("player-stage");
  const syllabusDialog = $("syllabus-dialog");

  if (playerDialog && playerStage) {
    playerDialog.addEventListener("close", () => {
      playerStage.replaceChildren();
    });
    attachDialogLightDismissFallback(playerDialog);
  }

  if (syllabusDialog) {
    attachDialogLightDismissFallback(syllabusDialog);
    $("open-syllabus-drawer").addEventListener("click", () => {
      syllabusDialog.showModal();
    });
  }
}

function loadIframeIntoStage(video, specificVideoId = "") {
  const stage = $("player-stage");
  let src = "";
  if (specificVideoId) {
    const listParam = video.provider === "playlist" ? `&list=${encodeURIComponent(video.video_id)}` : "";
    src = `https://www.youtube-nocookie.com/embed/${encodeURIComponent(specificVideoId)}?autoplay=1&rel=0${listParam}`;
  } else if (video.provider === "playlist") {
    if (video.embed_video_id) {
      src = `https://www.youtube-nocookie.com/embed/${encodeURIComponent(video.embed_video_id)}?list=${encodeURIComponent(video.video_id)}&autoplay=1&rel=0`;
    } else {
      src = `https://www.youtube-nocookie.com/embed/videoseries?list=${encodeURIComponent(video.video_id)}&autoplay=1`;
    }
  } else {
    src = `https://www.youtube-nocookie.com/embed/${encodeURIComponent(video.video_id)}?autoplay=1&rel=0`;
  }

  stage.replaceChildren();
  const iframe = document.createElement("iframe");
  iframe.src = src;
  iframe.title = `${video.title} — ${video.educator}`;
  iframe.allow =
    "accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share";
  iframe.allowFullscreen = true;
  stage.appendChild(iframe);
}

function openPreview(video, specificVideoId = "") {
  const dialog = $("player-dialog");
  if (!dialog) {
    window.open(video.url, "_blank", "noopener,noreferrer");
    return;
  }

  $("player-badge").textContent =
    video.provider === "playlist"
      ? `Ch ${video.chapter_no} · Playlist (${video.lesson_count || "Full"} lecs)`
      : `Ch ${video.chapter_no} · ${video.format}`;
  $("player-channel").textContent = `${video.educator} · ${video.target_exam}`;
  $("player-title").textContent = video.title;
  $("player-ext").href = video.url;
  $("player-ext").innerHTML =
    video.provider === "playlist"
      ? 'Open Full Playlist on YouTube <span aria-hidden="true">↗</span>'
      : 'Watch on YouTube <span aria-hidden="true">↗</span>';

  loadIframeIntoStage(video, specificVideoId);

  const sampleWrap = $("player-samples");
  sampleWrap.replaceChildren();
  if (video.sample_lectures && video.sample_lectures.length > 0) {
    sampleWrap.hidden = false;
    sampleWrap.appendChild(el("span", "strip-kicker", "Jump to lecture:"));
    for (const lec of video.sample_lectures) {
      const sBtn = el("button", "player-sample-btn", `▶ ${lec.title}`);
      sBtn.type = "button";
      sBtn.addEventListener("click", () => loadIframeIntoStage(video, lec.video_id));
      sampleWrap.appendChild(sBtn);
    }
  } else {
    sampleWrap.hidden = true;
  }

  if (!dialog.open) dialog.showModal();
}

function updateProgressTelemetry() {
  const totalCh = state.syllabus.length || 80;
  const doneCnt = state.doneChapters.size;
  $("stat-progress").textContent = `${doneCnt} / ${totalCh} Done`;
  const prog = $("syllabus-progress");
  prog.max = totalCh;
  prog.value = doneCnt;
  $("cnt-saved").textContent = String(state.saved.size);
}

function renderUnitBar() {
  const bar = $("unit-bar");
  bar.replaceChildren();

  if (state.subject === "Saved") return;

  const unitsMap = new Map();
  for (const ch of state.syllabus) {
    if (state.subject !== "All" && ch.subject !== state.subject) continue;
    unitsMap.set(ch.unit, (unitsMap.get(ch.unit) || 0) + 1);
  }

  if (unitsMap.size <= 1) return;

  const allBtn = el(
    "button",
    "unit-chip",
    state.subject === "All" ? "All 13 Units" : `All ${state.subject}`
  );
  allBtn.type = "button";
  allBtn.setAttribute("aria-pressed", state.unit === "" ? "true" : "false");
  allBtn.addEventListener("click", () => {
    state.unit = "";
    renderUnitBar();
    renderAllTrees();
    renderStream();
    syncUrlState();
  });
  bar.appendChild(allBtn);

  for (const [unitName, chCnt] of unitsMap.entries()) {
    const btn = el("button", "unit-chip", `${unitName} (${chCnt})`);
    btn.type = "button";
    btn.setAttribute("aria-pressed", state.unit === unitName ? "true" : "false");
    btn.addEventListener("click", () => {
      state.unit = state.unit === unitName ? "" : unitName;
      if (state.chapterNo) {
        const chObj = state.syllabus.find((c) => c.chapter_no === state.chapterNo);
        if (chObj && state.unit && chObj.unit !== state.unit) {
          state.chapterNo = 0;
        }
      }
      updateControlsUI();
      renderUnitBar();
      renderAllTrees();
      renderStream();
      syncUrlState();
    });
    bar.appendChild(btn);
  }
}

function populateEducatorControls() {
  const sel = $("educator-select");
  sel.replaceChildren();
  const defaultOpt = document.createElement("option");
  defaultOpt.value = "";
  defaultOpt.textContent = `Teacher: All Faculty (${state.educators.length})`;
  sel.appendChild(defaultOpt);

  for (const edu of state.educators) {
    const opt = document.createElement("option");
    opt.value = edu.educator;
    opt.textContent = `${edu.educator} (${edu.playlists} PL · ${edu.total})`;
    sel.appendChild(opt);
  }
  sel.value = state.educator;

  renderTeacherChips();
}

function renderTeacherChips() {
  const strip = $("teacher-chips");
  strip.replaceChildren();

  const isUmbrellaChannel = (name) =>
    /^(JEE Wallah|Unacademy|Vedantu|ALLEN|Motion|eSaral|ATP STAR|JEE Nexus|JEEfinity|PW JEE|Lakshya JEE|Arjuna JEE|Let's Crack|Khan Academy)/i.test(
      name
    );

  // Prioritize renowned named teachers with strong playlist coverage for the active subject
  const filteredEdus = state.educators
    .filter((e) => {
      if (state.subject === "Mathematics" || state.subject === "Physics" || state.subject === "Chemistry") {
        return state.videos.some((v) => v.educator === e.educator && v.subject === state.subject);
      }
      return true;
    })
    .slice()
    .sort((a, b) => {
      const aNamed = isUmbrellaChannel(a.educator) ? 0 : 1;
      const bNamed = isUmbrellaChannel(b.educator) ? 0 : 1;
      if (bNamed !== aNamed) return bNamed - aNamed;
      return b.playlists * 2 + b.total - (a.playlists * 2 + a.total);
    })
    .slice(0, 16);

  for (const edu of filteredEdus) {
    const btn = el("button", "teacher-chip");
    btn.type = "button";
    const isPressed = state.educator === edu.educator;
    btn.setAttribute("aria-pressed", isPressed ? "true" : "false");

    const avatar = el("span", `t-avatar is-${subjectSlug(edu.subject)}`, teacherInitials(edu.educator));
    avatar.setAttribute("aria-hidden", "true");
    btn.appendChild(avatar);
    btn.appendChild(el("span", "", edu.educator));

    btn.addEventListener("click", () => {
      state.educator = state.educator === edu.educator ? "" : edu.educator;
      updateControlsUI();
      renderTeacherChips();
      renderAllTrees();
      renderStream();
      syncUrlState();
    });
    strip.appendChild(btn);
  }
}

function updateSubjectTabsUI() {
  document.querySelectorAll(".subj-tab").forEach((tab) => {
    const isSel = tab.dataset.subject === state.subject;
    tab.setAttribute("aria-checked", isSel ? "true" : "false");
    tab.tabIndex = isSel ? 0 : -1;
  });
  updateProgressTelemetry();
}

function updateControlsUI() {
  $("q").value = state.query;
  $("educator-select").value = state.educator;
  $("class-select").value = state.classLevel;
  $("lang-select").value = state.language;
  $("sort-select").value = state.sort;

  const hasText = $("q").value.length > 0;
  $("clear-q").hidden = !hasText;
  $("key-hint").hidden = hasText;

  document.querySelectorAll(".goal-chip").forEach((btn) => {
    btn.setAttribute("aria-pressed", btn.dataset.goal === state.goal ? "true" : "false");
  });

  document.querySelectorAll(".type-btn").forEach((btn) => {
    btn.setAttribute("aria-pressed", btn.dataset.type === state.resourceType ? "true" : "false");
  });

  document.querySelectorAll(".exam-btn").forEach((btn) => {
    btn.setAttribute("aria-pressed", btn.dataset.exam === state.exam ? "true" : "false");
  });

  document.querySelectorAll(".layout-btn").forEach((btn) => {
    btn.setAttribute("aria-pressed", btn.dataset.layout === state.layout ? "true" : "false");
  });

  $("clear-chapter-btn").hidden = state.chapterNo === 0;
  updateSubjectTabsUI();
}

function renderSyllabusTreeInto(container, filterNeedle) {
  container.replaceChildren();
  const chCounts = new Map();
  for (const v of state.videos) {
    if (matchesWithoutChapter(v)) {
      chCounts.set(v.chapter_no, (chCounts.get(v.chapter_no) || 0) + 1);
    }
  }

  const needle = (filterNeedle || "").trim().toLowerCase();
  const chapters = state.syllabus.filter((ch) => {
    if (state.subject === "Mathematics" || state.subject === "Physics" || state.subject === "Chemistry") {
      if (ch.subject !== state.subject) return false;
    }
    if (state.unit && ch.unit !== state.unit) return false;
    if (state.classLevel !== "all" && ch.class_level !== state.classLevel) return false;
    if (!needle) return true;
    const alias = ACRONYM_ALIASES[ch.chapter_no] || "";
    return (
      ch.chapter.toLowerCase().includes(needle) ||
      ch.unit.toLowerCase().includes(needle) ||
      alias.includes(needle) ||
      `ch ${ch.chapter_no}` === needle ||
      String(ch.chapter_no) === needle
    );
  });

  const unitGroups = [];
  const unitMap = new Map();
  for (const ch of chapters) {
    const uKey = `${ch.subject}::${ch.unit}`;
    if (!unitMap.has(uKey)) {
      const grp = { subject: ch.subject, unit: ch.unit, items: [] };
      unitMap.set(uKey, grp);
      unitGroups.push(grp);
    }
    unitMap.get(uKey).items.push(ch);
  }

  for (const grp of unitGroups) {
    const wrap = el("div", "unit-group");
    const heading = el("div", "unit-heading");
    heading.appendChild(el("span", "", grp.unit));
    if (state.subject === "All" || state.subject === "Saved") {
      const sTag = el(
        "span",
        `unit-subj-tag is-${subjectSlug(grp.subject)}`,
        grp.subject === "Mathematics" ? "Maths" : grp.subject === "Chemistry" ? "Chem" : "Phys"
      );
      heading.appendChild(sTag);
    }
    wrap.appendChild(heading);

    const ul = el("ul", "ch-nav-list");
    for (const ch of grp.items) {
      const li = document.createElement("li");
      const isDone = state.doneChapters.has(ch.chapter_no);
      const btn = el("button", isDone ? "ch-nav-btn is-done" : "ch-nav-btn");
      btn.type = "button";
      const isCurrent = state.chapterNo === ch.chapter_no;
      btn.setAttribute("aria-current", isCurrent ? "true" : "false");

      btn.appendChild(
        el("span", "ch-no", isDone ? "✓" : String(ch.chapter_no).padStart(2, "0"))
      );
      btn.appendChild(el("span", "ch-name", ch.chapter));
      const cnt = chCounts.get(ch.chapter_no) || 0;
      btn.appendChild(el("span", "ch-cnt", String(cnt)));

      btn.addEventListener("click", () => {
        state.chapterNo = state.chapterNo === ch.chapter_no ? 0 : ch.chapter_no;
        const drawer = $("syllabus-dialog");
        if (drawer && drawer.open) drawer.close();
        updateControlsUI();
        renderAllTrees();
        renderStream();
        syncUrlState();
      });

      li.appendChild(btn);
      ul.appendChild(li);
    }
    wrap.appendChild(ul);
    container.appendChild(wrap);
  }
}

function renderAllTrees() {
  renderSyllabusTreeInto($("syllabus-tree"), $("ch-filter").value);
  renderSyllabusTreeInto($("drawer-syllabus-tree"), $("drawer-ch-filter").value);

  if (state.chapterNo) {
    const chObj = state.syllabus.find((c) => c.chapter_no === state.chapterNo);
    $("mobile-ch-label").textContent = chObj ? `Ch ${chObj.chapter_no}` : "Chapters";
    $("sidebar-sub").textContent = chObj ? `Viewing Ch ${chObj.chapter_no} only` : "Isolated chapter";
  } else {
    $("mobile-ch-label").textContent = `Chapters (${state.syllabus.length || 80})`;
    $("sidebar-sub").textContent = "Click any chapter to isolate";
  }
}

function makeFilterPill(label, onClear) {
  const pill = el("button", "filter-pill", `${label} ×`);
  pill.type = "button";
  pill.addEventListener("click", onClear);
  return pill;
}

function renderActiveFilterPills() {
  const bar = $("active-filters");
  bar.replaceChildren();

  if (state.unit) {
    bar.appendChild(
      makeFilterPill(`Unit: ${state.unit}`, () => {
        state.unit = "";
        renderUnitBar();
        renderAllTrees();
        renderStream();
        syncUrlState();
      })
    );
  }

  if (state.chapterNo) {
    const chObj = state.syllabus.find((c) => c.chapter_no === state.chapterNo);
    bar.appendChild(
      makeFilterPill(chObj ? `Ch ${chObj.chapter_no}: ${chObj.chapter}` : `Ch ${state.chapterNo}`, () => {
        state.chapterNo = 0;
        updateControlsUI();
        renderAllTrees();
        renderStream();
        syncUrlState();
      })
    );
  }

  if (state.educator) {
    bar.appendChild(
      makeFilterPill(`Teacher: ${state.educator}`, () => {
        state.educator = "";
        updateControlsUI();
        renderTeacherChips();
        renderAllTrees();
        renderStream();
        syncUrlState();
      })
    );
  }

  if (state.goal !== "all") {
    bar.appendChild(
      makeFilterPill(`Mode: ${state.goal}`, () => {
        state.goal = "all";
        updateControlsUI();
        renderAllTrees();
        renderStream();
        syncUrlState();
      })
    );
  }

  $("reset-filters").hidden = !hasActiveFilters();
}

function createCardElement(video, globalRenderIdx, headingTag = "h3", deferCard = false) {
  const isPlaylist = video.provider === "playlist";
  const classes = ["card"];
  if (isPlaylist) classes.push("is-playlist-card");
  if (deferCard) classes.push("is-deferred");
  const card = el("article", classes.join(" "));

  /* 1. YouTube-Authentic 16:9 Media Stage */
  const mediaCol = el("div", "card-media");
  if (isPlaylist) {
    const stackLip = el("span", "playlist-stack-lip");
    stackLip.setAttribute("aria-hidden", "true");
    mediaCol.appendChild(stackLip);
  }

  const thumbBtn = el("button", "thumb-btn");
  thumbBtn.type = "button";
  thumbBtn.setAttribute(
    "aria-label",
    `Play ${isPlaylist ? "playlist" : "lecture"} preview: ${video.title} by ${video.educator}`
  );
  thumbBtn.addEventListener("click", () => openPreview(video));

  if (video.thumbnail) {
    const img = document.createElement("img");
    img.src = video.thumbnail;
    img.alt = "";
    img.width = 720;
    img.height = 404;

    // LCP prioritization (modern-web-guidance: optimize-image-priority)
    if (globalRenderIdx === 0) {
      img.fetchPriority = "high";
    } else if (globalRenderIdx >= 4) {
      img.loading = "lazy";
    }

    img.addEventListener("error", () => {
      img.replaceWith(el("span", "thumb-fallback", video.educator));
    });
    thumbBtn.appendChild(img);
  } else {
    thumbBtn.appendChild(el("span", "thumb-fallback", video.educator));
  }

  const playOverlay = el("span", "play-pill");
  playOverlay.setAttribute("aria-hidden", "true");
  const playCircle = el("span", "play-icon-circle");
  playCircle.innerHTML =
    '<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5.14v14l11-7-11-7z"/></svg>';
  playOverlay.appendChild(playCircle);
  thumbBtn.appendChild(playOverlay);

  const examBadge = el(
    "span",
    video.target_exam === "JEE Advanced" ? "exam-overlay-badge is-adv" : "exam-overlay-badge",
    video.target_exam === "JEE Main + Advanced" ? "Main + Adv" : video.target_exam
  );
  examBadge.setAttribute("aria-hidden", "true");
  thumbBtn.appendChild(examBadge);

  const brBadgeText = isPlaylist
    ? video.lesson_count
      ? `▤ ${video.lesson_count} lectures`
      : "▤ Full Playlist"
    : video.duration || "Lecture";
  const brBadge = el("span", isPlaylist ? "yt-badge-br is-pl" : "yt-badge-br", brBadgeText);
  brBadge.setAttribute("aria-hidden", "true");
  thumbBtn.appendChild(brBadge);

  mediaCol.appendChild(thumbBtn);
  card.appendChild(mediaCol);

  /* 2. Structured Syllabus Metadata & Title */
  const body = el("div", "card-body");
  const eyebrow = el("div", "card-eyebrow");

  const sSlug = subjectSlug(video.subject);
  if (state.sort !== "chapterwise" && state.sort !== "weightage") {
    eyebrow.appendChild(
      el("span", `subj-pill is-${sSlug}`, `Ch ${String(video.chapter_no).padStart(2, "0")} · ${video.chapter}`)
    );
  } else {
    eyebrow.appendChild(el("span", `subj-pill is-${sSlug}`, video.unit));
  }

  eyebrow.appendChild(el("span", "format-pill", isPlaylist ? "Playlist" : video.format));
  if (video.language === "English") {
    eyebrow.appendChild(el("span", "lang-pill", "English"));
  }
  body.appendChild(eyebrow);

  const uniqueCardContext = `${video.title} (${video.educator}${
    isPlaylist
      ? video.lesson_count
        ? `, ${video.lesson_count} lectures`
        : ", Playlist"
      : video.duration
        ? `, ${video.duration}`
        : ""
  })`;

  const titleEl = el(headingTag, "card-title");
  const titleLink = document.createElement("a");
  titleLink.href = video.url;
  titleLink.target = "_blank";
  titleLink.rel = "noopener noreferrer";
  titleLink.appendChild(document.createTextNode(video.title));
  titleLink.appendChild(
    el(
      "span",
      "visually-hidden",
      ` — ${video.educator}${
        isPlaylist && video.lesson_count ? `, ${video.lesson_count} lectures` : video.duration ? `, ${video.duration}` : ""
      }`
    )
  );
  titleEl.appendChild(titleLink);
  body.appendChild(titleEl);

  const byline = el("div", "card-byline");
  const eduBtn = el("button", "educator-btn", video.educator);
  eduBtn.type = "button";
  eduBtn.addEventListener("click", () => {
    state.educator = state.educator === video.educator ? "" : video.educator;
    updateControlsUI();
    renderTeacherChips();
    renderAllTrees();
    renderStream();
    syncUrlState();
  });
  byline.appendChild(eduBtn);

  if (!isPlaylist && video.view_count >= 1000) {
    byline.appendChild(el("span", "meta-sep", "·"));
    byline.appendChild(
      el(
        "span",
        "",
        `${Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(video.view_count)} views`
      )
    );
  } else if (isPlaylist && video.channel && video.channel !== video.educator) {
    byline.appendChild(el("span", "meta-sep", "·"));
    byline.appendChild(el("span", "", video.channel));
  }

  byline.appendChild(el("span", "meta-sep", "·"));
  byline.appendChild(el("span", "", video.class_level));
  body.appendChild(byline);

  if (video.sample_lectures && video.sample_lectures.length > 0) {
    const details = el("details", "sample-details");
    const summary = document.createElement("summary");
    summary.appendChild(document.createTextNode(`${video.sample_lectures.length} sample syllabus lectures`));
    summary.appendChild(el("span", "visually-hidden", ` from ${uniqueCardContext}`));
    details.appendChild(summary);

    const ul = el("ul", "sample-list");
    ul.setAttribute("role", "list");
    for (const lec of video.sample_lectures) {
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = lec.url;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      const lecIcon = el("span", "", "▶ ");
      lecIcon.setAttribute("aria-hidden", "true");
      a.appendChild(lecIcon);
      a.appendChild(document.createTextNode(lec.title));
      a.appendChild(el("span", "visually-hidden", ` (in ${uniqueCardContext})`));
      a.addEventListener("click", (ev) => {
        if (!ev.metaKey && !ev.ctrlKey && !ev.shiftKey) {
          ev.preventDefault();
          openPreview(video, lec.video_id);
        }
      });
      li.appendChild(a);
      ul.appendChild(li);
    }
    details.appendChild(ul);
    body.appendChild(details);
  }

  /* 3. Direct YouTube Landing CTA + Inline Preview + Save Deck */
  const actions = el("div", "card-actions");

  const ytLink = el("a", "yt-land-btn");
  ytLink.href = video.url;
  ytLink.target = "_blank";
  ytLink.rel = "noopener noreferrer";
  ytLink.appendChild(
    document.createTextNode(isPlaylist ? "Open Playlist on YouTube" : "Watch on YouTube")
  );
  const ytArrow = el("span", "", "↗");
  ytArrow.setAttribute("aria-hidden", "true");
  ytLink.appendChild(ytArrow);
  ytLink.appendChild(el("span", "visually-hidden", ` — ${uniqueCardContext}`));
  actions.appendChild(ytLink);

  const prevBtn = el("button", "preview-btn");
  prevBtn.type = "button";
  const playGlyph = el("span", "", "▶");
  playGlyph.setAttribute("aria-hidden", "true");
  prevBtn.appendChild(playGlyph);
  prevBtn.appendChild(document.createTextNode(" Preview"));
  prevBtn.appendChild(el("span", "visually-hidden", ` — ${uniqueCardContext}`));
  prevBtn.addEventListener("click", () => openPreview(video));
  actions.appendChild(prevBtn);

  const saveBtn = el("button", "save-btn");
  saveBtn.type = "button";
  const isSaved = state.saved.has(video._key);
  saveBtn.setAttribute("aria-pressed", isSaved ? "true" : "false");
  const starSpan = el("span", "", isSaved ? "★" : "☆");
  starSpan.setAttribute("aria-hidden", "true");
  saveBtn.appendChild(starSpan);
  saveBtn.appendChild(document.createTextNode(" Save"));
  saveBtn.appendChild(el("span", "visually-hidden", ` — ${uniqueCardContext}`));

  saveBtn.addEventListener("click", () => {
    if (state.saved.has(video._key)) {
      state.saved.delete(video._key);
    } else {
      state.saved.add(video._key);
    }
    persistSaved();
    updateSubjectTabsUI();
    if (state.subject === "Saved") {
      renderAllTrees();
      renderStream();
    } else {
      const nowSaved = state.saved.has(video._key);
      saveBtn.setAttribute("aria-pressed", nowSaved ? "true" : "false");
      starSpan.textContent = nowSaved ? "★" : "☆";
    }
  });
  actions.appendChild(saveBtn);

  body.appendChild(actions);
  card.appendChild(body);
  return card;
}

function getFlatComparator() {
  const qLow = state.query.trim().toLowerCase();
  if (state.sort === "views") {
    return (a, b) => b.view_count - a.view_count || b.score - a.score;
  }
  if (state.sort === "lessons") {
    return (a, b) => b.lesson_count - a.lesson_count || (b.provider === "playlist") - (a.provider === "playlist") || b.score - a.score;
  }
  if (state.sort === "duration_desc") {
    return (a, b) => b.duration_sec - a.duration_sec || b.lesson_count - a.lesson_count || b.score - a.score;
  }
  if (state.sort === "duration_asc") {
    return (a, b) => {
      const da = a.duration_sec > 0 ? a.duration_sec : 999999;
      const db = b.duration_sec > 0 ? b.duration_sec : 999999;
      return da - db || b.score - a.score;
    };
  }
  // "relevance": boost exact title/chapter match when searching, otherwise score + views
  return (a, b) => {
    if (qLow) {
      const aTitleHit = a.title.toLowerCase().includes(qLow) ? 1 : 0;
      const bTitleHit = b.title.toLowerCase().includes(qLow) ? 1 : 0;
      if (bTitleHit !== aTitleHit) return bTitleHit - aTitleHit;
    }
    return b.score - a.score || b.view_count - a.view_count;
  };
}

function renderStream() {
  const container = $("list");
  const shown = state.videos.filter(matches);
  renderActiveFilterPills();
  container.replaceChildren();

  if (!shown.length) {
    const emptyMsg = "0 matching JEE resources";
    $("count").textContent = emptyMsg;
    announcePolite(emptyMsg);

    const empty = el("div", "empty-state");
    empty.appendChild(
      el(
        "h2",
        "",
        state.subject === "Saved" && state.saved.size === 0
          ? "Your Personal JEE Study Deck is empty"
          : "No JEE playlists or lectures match this exact filter combination"
      )
    );
    empty.appendChild(
      el(
        "p",
        "",
        state.subject === "Saved" && state.saved.size === 0
          ? "Click “☆ Save” on any teacher playlist, one-shot marathon, or PYQ session to build your custom chapterwise revision deck."
          : "Try setting Teacher or Study Mode back to All, clearing the search query, or resetting all filters."
      )
    );
    const rBtn = el("button", "empty-reset-btn", "Reset all filters");
    rBtn.type = "button";
    rBtn.addEventListener("click", resetAllFilters);
    empty.appendChild(rBtn);
    container.appendChild(empty);
    return;
  }

  const fragment = document.createDocumentFragment();
  let globalCardIdx = 0;
  const gridClass = state.layout === "list" ? "cards-grid is-list" : "cards-grid";

  if (state.sort === "chapterwise" || state.sort === "weightage") {
    const byChapter = new Map();
    for (const v of shown) {
      if (!byChapter.has(v.chapter_no)) byChapter.set(v.chapter_no, []);
      byChapter.get(v.chapter_no).push(v);
    }

    let activeChapters = state.syllabus.filter((c) => byChapter.has(c.chapter_no));
    if (state.sort === "weightage") {
      activeChapters = activeChapters
        .slice()
        .sort(
          (a, b) =>
            (WEIGHTAGE_ORDER[b.weightage] || 0) - (WEIGHTAGE_ORDER[a.weightage] || 0) ||
            a.chapter_no - b.chapter_no
        );
    }

    const plShown = shown.filter((v) => v.provider === "playlist").length;
    const summaryText = `Showing ${shown.length.toLocaleString("en-US")} JEE resources (${plShown} playlists, ${shown.length - plShown} lectures) across ${activeChapters.length} ${activeChapters.length === 1 ? "chapter" : "chapters"}`;
    $("count").textContent = summaryText;
    announcePolite(summaryText);

    activeChapters.forEach((chMeta, secIdx) => {
      const secClasses = ["chapter-section"];
      // Defer rendering strictly below initial fold (modern-web-guidance: defer-rendering-heavy-content)
      if (secIdx >= 2) secClasses.push("is-deferred");

      const section = el("section", secClasses.join(" "));
      const banner = el("div", `chapter-banner is-${subjectSlug(chMeta.subject)}`);

      const topRow = el("div", "chapter-banner-top");
      const bannerMain = el("div", "chapter-banner-main");
      bannerMain.appendChild(
        el("span", "ch-badge-num", `CH ${String(chMeta.chapter_no).padStart(2, "0")}`)
      );
      bannerMain.appendChild(el("h2", "chapter-heading", chMeta.chapter));
      topRow.appendChild(bannerMain);

      const doneBtn = el("button", "done-btn");
      doneBtn.type = "button";
      const isDone = state.doneChapters.has(chMeta.chapter_no);
      doneBtn.setAttribute("aria-pressed", isDone ? "true" : "false");
      const doneGlyph = el("span", "", isDone ? "✓" : "○");
      doneGlyph.setAttribute("aria-hidden", "true");
      doneBtn.appendChild(doneGlyph);
      doneBtn.appendChild(document.createTextNode(" Completed"));
      doneBtn.appendChild(el("span", "visually-hidden", ` — Chapter ${chMeta.chapter_no}: ${chMeta.chapter}`));
      doneBtn.addEventListener("click", () => {
        if (state.doneChapters.has(chMeta.chapter_no)) {
          state.doneChapters.delete(chMeta.chapter_no);
        } else {
          state.doneChapters.add(chMeta.chapter_no);
        }
        persistDoneChapters();
        const nowDone = state.doneChapters.has(chMeta.chapter_no);
        doneBtn.setAttribute("aria-pressed", nowDone ? "true" : "false");
        doneGlyph.textContent = nowDone ? "✓" : "○";
        updateProgressTelemetry();
        renderAllTrees();
      });
      topRow.appendChild(doneBtn);
      banner.appendChild(topRow);

      const bottomRow = el("div", "chapter-banner-bottom");
      const bannerMeta = el("div", "chapter-banner-meta");
      bannerMeta.appendChild(
        el("span", "", `${chMeta.subject} · ${chMeta.unit} · ${chMeta.class_level}`)
      );
      bannerMeta.appendChild(
        el(
          "span",
          chMeta.weightage === "Very High" ? "weight-pill is-very-high" : "weight-pill",
          `${chMeta.weightage} Weightage`
        )
      );
      if (chMeta.syllabus_scope && chMeta.syllabus_scope !== "Main + Adv") {
        bannerMeta.appendChild(el("span", "scope-pill is-special", chMeta.syllabus_scope));
      }
      bottomRow.appendChild(bannerMeta);

      // Direct YouTube Search Fallbacks for unlimited exploration on YouTube
      const ytLinks = el("div", "chapter-yt-links");
      if (chMeta.yt_playlists_url) {
        const plChip = el("a", "yt-deep-chip");
        plChip.href = chMeta.yt_playlists_url;
        plChip.target = "_blank";
        plChip.rel = "noopener noreferrer";
        plChip.appendChild(document.createTextNode("More Playlists on YouTube "));
        const arr1 = el("span", "", "↗");
        arr1.setAttribute("aria-hidden", "true");
        plChip.appendChild(arr1);
        plChip.appendChild(el("span", "visually-hidden", ` for ${chMeta.chapter}`));
        ytLinks.appendChild(plChip);
      }
      if (chMeta.yt_oneshots_url) {
        const osChip = el("a", "yt-deep-chip");
        osChip.href = chMeta.yt_oneshots_url;
        osChip.target = "_blank";
        osChip.rel = "noopener noreferrer";
        osChip.appendChild(document.createTextNode("More One-Shots on YouTube "));
        const arr2 = el("span", "", "↗");
        arr2.setAttribute("aria-hidden", "true");
        osChip.appendChild(arr2);
        osChip.appendChild(el("span", "visually-hidden", ` for ${chMeta.chapter}`));
        ytLinks.appendChild(osChip);
      }
      bottomRow.appendChild(ytLinks);
      banner.appendChild(bottomRow);
      section.appendChild(banner);

      const grid = el("div", gridClass);
      const chVideos = byChapter.get(chMeta.chapter_no);
      for (const video of chVideos) {
        grid.appendChild(createCardElement(video, globalCardIdx, "h3", false));
        globalCardIdx += 1;
      }
      section.appendChild(grid);
      fragment.appendChild(section);
    });
  } else {
    const sorted = shown.slice().sort(getFlatComparator());
    const plShown = sorted.filter((v) => v.provider === "playlist").length;
    const summaryText = `Showing ${sorted.length.toLocaleString("en-US")} sorted JEE resources (${plShown} playlists, ${sorted.length - plShown} lectures)`;
    $("count").textContent = summaryText;
    announcePolite(summaryText);

    const flatSection = el("section", "chapter-section");
    const flatHeading = el("h2", "visually-hidden", "Sorted IIT-JEE YouTube Resources");
    flatSection.appendChild(flatHeading);

    const grid = el("div", gridClass);
    sorted.forEach((video, idx) => {
      grid.appendChild(createCardElement(video, globalCardIdx, "h3", idx >= 8));
      globalCardIdx += 1;
    });
    flatSection.appendChild(grid);
    fragment.appendChild(flatSection);
  }

  container.appendChild(fragment);
}

function resetAllFilters() {
  state.subject = "All";
  state.unit = "";
  state.chapterNo = 0;
  state.goal = "all";
  state.resourceType = "all";
  state.exam = "all";
  state.classLevel = "all";
  state.language = "all";
  state.educator = "";
  state.query = "";
  $("ch-filter").value = "";
  $("drawer-ch-filter").value = "";
  updateControlsUI();
  renderUnitBar();
  renderTeacherChips();
  renderAllTrees();
  renderStream();
  syncUrlState();
}

function showError(msg) {
  const sub = $("subline");
  sub.textContent = msg;
  sub.hidden = false;
  $("count").textContent = "Corpus unavailable";
}

function initSubjectTabs() {
  const tabs = [...document.querySelectorAll(".subj-tab")];
  tabs.forEach((tab, idx) => {
    tab.addEventListener("click", () => {
      state.subject = tab.dataset.subject;
      state.unit = "";
      if (state.chapterNo) {
        const chObj = state.syllabus.find((c) => c.chapter_no === state.chapterNo);
        if (
          chObj &&
          state.subject !== "All" &&
          state.subject !== "Saved" &&
          chObj.subject !== state.subject
        ) {
          state.chapterNo = 0;
        }
      }
      updateControlsUI();
      renderUnitBar();
      renderTeacherChips();
      renderAllTrees();
      renderStream();
      syncUrlState();
    });

    tab.addEventListener("keydown", (ev) => {
      let nextIdx = null;
      if (ev.key === "ArrowRight" || ev.key === "ArrowDown") nextIdx = (idx + 1) % tabs.length;
      if (ev.key === "ArrowLeft" || ev.key === "ArrowUp") nextIdx = (idx - 1 + tabs.length) % tabs.length;
      if (ev.key === "Home") nextIdx = 0;
      if (ev.key === "End") nextIdx = tabs.length - 1;
      if (nextIdx !== null) {
        ev.preventDefault();
        tabs[nextIdx].click();
        tabs[nextIdx].focus();
      }
    });
  });
}

async function main() {
  loadLocalSets();
  initThemeToggle();
  initDialogs();
  initSubjectTabs();
  readUrlState();

  let data;
  try {
    const resp = await fetch("data/videos.json");
    if (!resp.ok) {
      showError(`Could not load data/videos.json (HTTP ${resp.status}).`);
      return;
    }
    data = await resp.json();
  } catch {
    showError("Could not load data/videos.json. Serve this folder over HTTP (python3 -m http.server).");
    return;
  }

  state.syllabus = Array.isArray(data.syllabus) ? data.syllabus : [];
  state.educators = Array.isArray(data.educators) ? data.educators : [];
  state.videos = Array.isArray(data.videos) ? data.videos.map(prepareVideo) : [];

  const meta = data.meta || {};
  $("stat-chapters").textContent = `${meta.chapters_populated || state.syllabus.length} / ${meta.chapters_total || 80} Chapters`;
  $("stat-pl-coverage").textContent = `${meta.chapters_with_playlists || 80}/${meta.chapters_total || 80} Chapters w/ Playlists`;
  $("stat-playlists").textContent = `${(meta.playlists_published || 0).toLocaleString("en-US")} Playlists`;
  $("stat-videos").textContent = `${(meta.videos_published || 0).toLocaleString("en-US")} Lectures`;
  $("stat-educators").textContent = `Across ${meta.distinct_educators || state.educators.length} JEE Faculty`;

  const mathCount = state.videos.filter((v) => v.subject === "Mathematics").length;
  const physCount = state.videos.filter((v) => v.subject === "Physics").length;
  const chemCount = state.videos.filter((v) => v.subject === "Chemistry").length;
  $("cnt-all").textContent = `${state.videos.length.toLocaleString("en-US")}`;
  $("cnt-math").textContent = `${mathCount}`;
  $("cnt-phys").textContent = `${physCount}`;
  $("cnt-chem").textContent = `${chemCount}`;

  populateEducatorControls();
  renderUnitBar();

  /* Event Bindings */
  $("q").addEventListener("input", (ev) => {
    state.query = ev.target.value;
    updateControlsUI();
    renderAllTrees();
    renderStream();
    syncUrlState();
  });

  $("clear-q").addEventListener("click", () => {
    state.query = "";
    updateControlsUI();
    renderAllTrees();
    renderStream();
    syncUrlState();
    $("q").focus();
  });

  document.querySelectorAll(".goal-chip").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.goal = btn.dataset.goal;
      if (state.goal === "playlists") {
        state.resourceType = "playlist";
      } else if (state.goal === "oneshot") {
        state.resourceType = "youtube";
      } else if (state.resourceType !== "all") {
        state.resourceType = "all";
      }
      updateControlsUI();
      renderAllTrees();
      renderStream();
      syncUrlState();
    });
  });

  document.querySelectorAll(".type-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.resourceType = btn.dataset.type;
      if (state.goal === "playlists" && state.resourceType !== "playlist") state.goal = "all";
      if (state.goal === "oneshot" && state.resourceType === "playlist") state.goal = "all";
      updateControlsUI();
      renderAllTrees();
      renderStream();
      syncUrlState();
    });
  });

  document.querySelectorAll(".exam-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.exam = btn.dataset.exam;
      updateControlsUI();
      renderAllTrees();
      renderStream();
      syncUrlState();
    });
  });

  document.querySelectorAll(".layout-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.layout = btn.dataset.layout;
      persistLayout();
      updateControlsUI();
      renderStream();
    });
  });

  $("educator-select").addEventListener("change", (ev) => {
    state.educator = ev.target.value;
    renderTeacherChips();
    renderAllTrees();
    renderStream();
    syncUrlState();
  });

  $("class-select").addEventListener("change", (ev) => {
    state.classLevel = ev.target.value;
    renderAllTrees();
    renderStream();
    syncUrlState();
  });

  $("lang-select").addEventListener("change", (ev) => {
    state.language = ev.target.value;
    renderAllTrees();
    renderStream();
    syncUrlState();
  });

  $("sort-select").addEventListener("change", (ev) => {
    state.sort = ev.target.value;
    renderStream();
    syncUrlState();
  });

  $("ch-filter").addEventListener("input", () => renderAllTrees());
  $("drawer-ch-filter").addEventListener("input", () => renderAllTrees());

  $("clear-chapter-btn").addEventListener("click", () => {
    state.chapterNo = 0;
    updateControlsUI();
    renderAllTrees();
    renderStream();
    syncUrlState();
  });

  $("reset-filters").addEventListener("click", resetAllFilters);

  document.addEventListener("keydown", (ev) => {
    if (ev.metaKey || ev.ctrlKey || ev.altKey) return;
    const active = document.activeElement;
    const isEditable =
      active &&
      (active.tagName === "INPUT" ||
        active.tagName === "TEXTAREA" ||
        active.tagName === "SELECT" ||
        active.isContentEditable);

    if (ev.key === "/" && !isEditable) {
      ev.preventDefault();
      $("q").focus();
      $("q").select();
    } else if (ev.key === "Escape" && active === $("q")) {
      if ($("q").value) {
        state.query = "";
        updateControlsUI();
        renderAllTrees();
        renderStream();
        syncUrlState();
      } else {
        $("q").blur();
      }
    }
  });

  window.addEventListener("popstate", () => {
    state.subject = "All";
    state.unit = "";
    state.chapterNo = 0;
    state.goal = "all";
    state.resourceType = "all";
    state.exam = "all";
    state.classLevel = "all";
    state.language = "all";
    state.educator = "";
    state.sort = "chapterwise";
    state.query = "";
    readUrlState();
    updateControlsUI();
    renderUnitBar();
    renderTeacherChips();
    renderAllTrees();
    renderStream();
  });

  updateControlsUI();
  renderAllTrees();
  renderStream();
}

main();
