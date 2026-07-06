const UI = {
  body: document.body,
  input: document.getElementById("search-input"),
  results: document.getElementById("search-results"),
  clearBtn: document.getElementById("clear-btn"),
  loader: document.getElementById("loader"),
  statusDot: document.querySelector(".status-dot"),
  statusText: document.getElementById("status-text"),
  versionText: document.getElementById("version-text")
};

const State = {
  files: [],
  records: [],
  selectedIndex: -1,
  isLoading: true
};

const QUICK_ACTIONS = [
  { label: "曲绘", query: "illustration" },
  { label: "音频", query: "music" },
  { label: "谱面", query: "chart" },
  { label: "信息", query: "info" }
];

const RESOURCE_TYPES = [
  ["illustration", "ill"],
  ["music", "music"],
  ["chart", "chart"],
  ["avatar", "avatar"],
  ["phira", "phira"],
  ["chap", "chap"],
  ["info", "info"],
  ["lilith", "lilith"]
];

function getViewportHeight() {
  return window.visualViewport ? window.visualViewport.height : window.innerHeight;
}

function positionResults() {
  if (!UI.results.classList.contains("show")) return;

  const inputRect = UI.input.getBoundingClientRect();
  const footerRect = document.querySelector(".footer-info")?.getBoundingClientRect();
  const viewportHeight = getViewportHeight();
  const gap = 10;
  const preferredMax = Math.floor(viewportHeight * 0.55);
  const safeBottom = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--safe-area-bottom")) || 0;
  const footerTop = footerRect && footerRect.height > 0 ? footerRect.top : viewportHeight - safeBottom;
  const spaceBelow = Math.max(0, footerTop - inputRect.bottom - gap);
  const maxHeight = Math.min(preferredMax, Math.floor(spaceBelow));

  document.documentElement.style.setProperty("--results-max-height", `${Math.max(0, maxHeight)}px`);
}

let positionRaf = 0;
function schedulePositionResults() {
  if (positionRaf) return;
  positionRaf = requestAnimationFrame(() => {
    positionRaf = 0;
    positionResults();
  });
}

function normalizeQuery(value) {
  return value
    .normalize("NFKC")
    .toLowerCase()
    .replace(/[_\-./\\]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function getResourceType(path) {
  const prefix = path.split("/", 1)[0].toLowerCase();
  const found = RESOURCE_TYPES.find(([key]) => key === prefix);
  return found ? found[1] : "file";
}

function buildRecord(path) {
  const prefix = path.split("/", 1)[0].toLowerCase();
  const basename = path.split("/").pop() || path;
  return {
    path,
    prefix,
    normalizedPath: normalizeQuery(path),
    normalizedName: normalizeQuery(basename),
    type: getResourceType(path)
  };
}

async function loadVersion() {
  const candidates = ["info/version.txt", "version.txt"];

  for (const path of candidates) {
    try {
      const response = await fetch(path, { cache: "no-cache", credentials: "same-origin" });
      if (!response.ok) continue;

      const text = (await response.text()).trim();
      if (text) {
        UI.versionText.textContent = text;
        return;
      }
    } catch (_error) {
      // 版本文件是增强信息，失败时保留默认文案。
    }
  }
}

async function initSystem() {
  loadVersion();

  try {
    UI.loader.classList.add("active");
    const response = await fetch("files.json", { credentials: "same-origin" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const files = await response.json();
    State.files = Array.isArray(files) ? files.filter((file) => typeof file === "string") : [];
    State.records = State.files.map(buildRecord);
    State.isLoading = false;
    UI.input.disabled = false;
    UI.input.placeholder = "Search resources...";
    UI.statusText.textContent = "OPERATIONAL";
    UI.loader.classList.remove("active");

    if (window.matchMedia("(min-width: 768px)").matches) {
      UI.input.focus();
    }
  } catch (error) {
    console.error("System Failure:", error);
    UI.input.placeholder = "信号丢失";
    UI.input.classList.add("error");
    UI.statusDot.classList.add("error");
    UI.statusText.textContent = "OFFLINE";
    UI.loader.classList.remove("active");
    UI.input.disabled = false;
  }
}

function scoreRecord(record, terms) {
  let score = 0;

  for (const term of terms) {
    if (!record.normalizedPath.includes(term)) return -1;

    if (record.prefix === term || record.type === term) score += 120;
    else if (record.prefix.startsWith(term) || record.type.startsWith(term)) score += 70;

    if (record.normalizedName === term) score += 80;
    else if (record.normalizedName.startsWith(term)) score += 50;
    else if (record.normalizedName.includes(term)) score += 30;

    if (record.normalizedPath.startsWith(term)) score += 20;
    else score += 5;
  }

  return score;
}

function filterData(query) {
  const normalized = normalizeQuery(query);
  if (!normalized) return [];

  const terms = normalized.split(" ");
  return State.records
    .map((record) => ({ record, score: scoreRecord(record, terms) }))
    .filter((entry) => entry.score >= 0)
    .sort((a, b) => b.score - a.score || a.record.path.localeCompare(b.record.path))
    .slice(0, 20)
    .map((entry) => entry.record);
}

function toSafeHref(path) {
  return path.split("/").map((segment) => encodeURIComponent(segment)).join("/");
}

function appendHighlightedText(container, text, regex) {
  regex.lastIndex = 0;
  let lastIndex = 0;
  let match;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      container.appendChild(document.createTextNode(text.slice(lastIndex, match.index)));
    }

    const span = document.createElement("span");
    span.className = "highlight";
    span.textContent = match[0];
    container.appendChild(span);
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    container.appendChild(document.createTextNode(text.slice(lastIndex)));
  }
}

function buildHighlightRegex(query) {
  const terms = query.split(/\s+/).filter((term) => term.length > 0);
  if (!terms.length) return null;

  const escapedTerms = terms.map((term) => term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  return new RegExp(`(${escapedTerms.join("|")})`, "gi");
}

function createResultItem(record, index, query) {
  const item = document.createElement("a");
  item.href = toSafeHref(record.path);
  item.className = "result-item";
  item.role = "option";
  item.setAttribute("aria-label", record.path);
  item.id = `result-${index}`;
  item.target = "_blank";
  item.rel = "noopener noreferrer";

  const type = document.createElement("span");
  type.className = "result-type";
  type.textContent = record.type;
  item.appendChild(type);

  const path = document.createElement("span");
  path.className = "result-path";
  const regex = buildHighlightRegex(query);
  if (regex) appendHighlightedText(path, record.path, regex);
  else path.textContent = record.path;
  item.appendChild(path);

  return item;
}

function showResults() {
  UI.results.classList.add("show");
  UI.input.setAttribute("aria-expanded", "true");
  schedulePositionResults();
}

function hideResults() {
  UI.results.classList.remove("show");
  UI.input.setAttribute("aria-expanded", "false");
}

function renderQuickActions() {
  UI.results.innerHTML = "";
  State.selectedIndex = -1;
  UI.input.removeAttribute("aria-activedescendant");

  const wrapper = document.createElement("div");
  wrapper.className = "quick-actions";
  wrapper.role = "presentation";
  QUICK_ACTIONS.forEach((action, index) => {
    const button = document.createElement("div");
    button.className = "quick-action";
    button.id = `quick-action-${index}`;
    button.role = "option";
    button.tabIndex = -1;
    button.setAttribute("aria-selected", "false");
    button.textContent = action.label;
    button.addEventListener("mousedown", (event) => event.preventDefault());
    button.addEventListener("click", () => {
      UI.input.value = action.query;
      onInputValueChanged(action.query);
      UI.input.focus();
    });
    wrapper.appendChild(button);
  });

  UI.results.appendChild(wrapper);
  showResults();
}

function renderResults(matches, query) {
  UI.results.innerHTML = "";
  State.selectedIndex = -1;
  UI.input.removeAttribute("aria-activedescendant");

  if (!query) {
    renderQuickActions();
    return;
  }

  if (matches.length === 0) {
    const div = document.createElement("div");
    div.className = "result-empty";
    div.role = "option";
    div.setAttribute("aria-disabled", "true");
    div.textContent = "No echoes found.";
    UI.results.appendChild(div);
    showResults();
    return;
  }

  const fragment = document.createDocumentFragment();
  matches.forEach((record, index) => fragment.appendChild(createResultItem(record, index, query)));
  UI.results.appendChild(fragment);
  showResults();
}

let inputDebounceTimer = 0;
function onInputValueChanged(rawValue) {
  const value = rawValue.trim();
  UI.clearBtn.classList.toggle("visible", value.length > 0);
  UI.body.classList.toggle("searching", value.length > 0);
  renderResults(filterData(value), value);
}

UI.input.addEventListener("input", (event) => {
  const value = event.target.value;
  window.clearTimeout(inputDebounceTimer);
  inputDebounceTimer = window.setTimeout(() => onInputValueChanged(value), 40);
});

UI.input.addEventListener("focus", () => {
  onInputValueChanged(UI.input.value);
});

UI.input.addEventListener("blur", () => {
  setTimeout(() => {
    const active = document.activeElement;
    const keepSearching = active === UI.input || active === UI.clearBtn || UI.results.contains(active);
    if (!keepSearching) UI.body.classList.remove("searching");
  }, 200);
});

document.addEventListener("click", (event) => {
  if (!UI.input.contains(event.target) && !UI.results.contains(event.target)) {
    hideResults();
    UI.body.classList.remove("searching");
  }
});

UI.clearBtn.addEventListener("click", () => {
  UI.input.value = "";
  UI.input.focus();
  UI.clearBtn.classList.remove("visible");
  UI.body.classList.remove("searching");
  renderQuickActions();
});

UI.input.addEventListener("keydown", (event) => {
  const items = UI.results.querySelectorAll("a.result-item");

  if (event.key === "Escape") {
    UI.input.blur();
    hideResults();
    UI.body.classList.remove("searching");
    return;
  }

  if (!items.length) return;

  if (event.key === "ArrowDown" || event.key === "ArrowUp") {
    event.preventDefault();
    if (event.key === "ArrowDown") {
      State.selectedIndex = (State.selectedIndex + 1) % items.length;
    } else {
      State.selectedIndex = (State.selectedIndex - 1 + items.length) % items.length;
    }

    items.forEach((item) => item.setAttribute("aria-selected", "false"));
    const activeItem = items[State.selectedIndex];
    activeItem.setAttribute("aria-selected", "true");
    activeItem.scrollIntoView({ block: "nearest" });
    UI.input.setAttribute("aria-activedescendant", activeItem.id);
  } else if (event.key === "Enter" && State.selectedIndex > -1) {
    items[State.selectedIndex].click();
  }
});

window.addEventListener("resize", schedulePositionResults);
if (window.visualViewport) {
  window.visualViewport.addEventListener("resize", schedulePositionResults);
  window.visualViewport.addEventListener("scroll", schedulePositionResults);
}

initSystem();
