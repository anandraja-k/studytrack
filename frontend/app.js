/* StudyTrack dashboard logic.
 *
 * Run mode: SINGLE-PROCESS. FastAPI serves this file and the JSON API from the same
 * origin (http://localhost:8000), so every fetch below uses a relative path.
 * If you switch to the two-process mode, set API_BASE to "http://localhost:8000".
 */

const API_BASE = "";

const rosterList = document.getElementById("roster-list");
const rosterStatus = document.getElementById("roster-status");
const studentForm = document.getElementById("student-form");
const formStatus = document.getElementById("form-status");
const errorBanner = document.getElementById("error-banner");

/* ------------------------------------------------------------------ errors */

function showError(message) {
  errorBanner.textContent = message;
  errorBanner.hidden = false;
}

function hideError() {
  errorBanner.textContent = "";
  errorBanner.hidden = true;
}

/** Turn a FastAPI error body into one readable sentence. */
function describeFailure(response, payload) {
  if (payload && typeof payload.detail === "string") {
    return payload.detail;
  }
  if (payload && Array.isArray(payload.detail)) {
    // Pydantic validation errors arrive as a list of {loc, msg} objects.
    return payload.detail
      .map((item) => `${(item.loc || []).slice(-1)[0]}: ${item.msg}`)
      .join("; ");
  }
  return `Request failed with status ${response.status}.`;
}

/**
 * One fetch wrapper used by every call on this page.
 * Any non-ok response or network rejection ends up on the visible error banner.
 */
async function apiRequest(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, options);
  } catch (networkError) {
    // The backend is unreachable (not running, or the browser is offline).
    showError("Could not reach the StudyTrack backend. Is the server running on port 8000?");
    throw networkError;
  }

  if (response.status === 204) {
    hideError();
    return null;
  }

  let payload = null;
  try {
    payload = await response.json();
  } catch (parseError) {
    payload = null;
  }

  if (!response.ok) {
    const message = describeFailure(response, payload);
    showError(`Request to ${path} failed - ${message}`);
    const failure = new Error(message);
    failure.status = response.status;
    failure.payload = payload;
    throw failure;
  }

  hideError();
  return payload;
}

/* ------------------------------------------------------------- card render */

/** Build one student card entirely with document.createElement. */
function createStudentCard(student) {
  const card = document.createElement("article");
  card.className = "student-card";
  card.dataset.id = student.id;

  const name = document.createElement("h3");
  name.textContent = student.name;
  card.appendChild(name);

  const email = document.createElement("p");
  email.className = "card-email";
  email.textContent = student.email;
  card.appendChild(email);

  const age = document.createElement("p");
  age.className = "card-age";
  age.textContent = `Age: ${student.age}`;
  card.appendChild(age);

  const actions = document.createElement("div");
  actions.className = "card-actions";

  const ageInput = document.createElement("input");
  ageInput.type = "number";
  ageInput.className = "age-input";
  ageInput.min = "1";
  ageInput.value = student.age; // pre-filled with the current age
  ageInput.setAttribute("aria-label", `New age for ${student.name}`);
  actions.appendChild(ageInput);

  const saveButton = document.createElement("button");
  saveButton.type = "button";
  saveButton.className = "save-age";
  saveButton.textContent = "Save Age";
  actions.appendChild(saveButton);

  const deleteButton = document.createElement("button");
  deleteButton.type = "button";
  deleteButton.className = "danger-btn delete-student";
  deleteButton.textContent = "Delete";
  actions.appendChild(deleteButton);

  card.appendChild(actions);
  return card;
}

/** Replace the rendered cards with the supplied records. */
function renderRoster(students) {
  rosterList.replaceChildren();
  students.forEach((student) => rosterList.appendChild(createStudentCard(student)));
  rosterStatus.textContent = students.length
    ? `${students.length} student${students.length === 1 ? "" : "s"} shown.`
    : "No students to show.";
}

/* -------------------------------------------------------------- data loads */

async function loadRoster() {
  rosterStatus.textContent = "Loading roster...";
  try {
    const students = await apiRequest("/students/");
    renderRoster(students);
  } catch (error) {
    // apiRequest already showed the banner; keep the page usable.
    rosterStatus.textContent = "Roster could not be loaded.";
  }
}

/* ------------------------------------------------ delegated card handlers */

/**
 * ONE listener for the whole roster. event.target tells us which control inside
 * which card was clicked, so no per-card or per-button listeners are ever attached.
 */
rosterList.addEventListener("click", async (event) => {
  const target = event.target;
  const card = target.closest(".student-card");
  if (!card) {
    return; // a click on the container padding, not on a card
  }
  const studentId = card.dataset.id;

  if (target.classList.contains("save-age")) {
    const ageInput = card.querySelector(".age-input");
    const newAge = Number(ageInput.value);
    try {
      const updated = await apiRequest(`/students/${studentId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ age: newAge }),
      });
      card.querySelector(".card-age").textContent = `Age: ${updated.age}`;
      ageInput.value = updated.age;
      rosterStatus.textContent = `Updated ${updated.name} to age ${updated.age}.`;
    } catch (error) {
      /* banner already shown */
    }
    return;
  }

  if (target.classList.contains("delete-student")) {
    try {
      await apiRequest(`/students/${studentId}`, { method: "DELETE" });
      card.remove();
      rosterStatus.textContent = `Deleted student ${studentId}.`;
    } catch (error) {
      /* banner already shown */
    }
  }
});

/* --------------------------------------------------------- create student */

studentForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const newStudent = {
    name: document.getElementById("student-name").value.trim(),
    email: document.getElementById("student-email").value.trim(),
    age: Number(document.getElementById("student-age").value),
  };

  try {
    const created = await apiRequest("/students/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(newStudent),
    });
    // Append just the new card -- no page reload, no full-list rebuild.
    rosterList.appendChild(createStudentCard(created));
    studentForm.reset();
    formStatus.textContent = `Added ${created.name} (id ${created.id}).`;
  } catch (error) {
    formStatus.textContent = "Student was not added.";
  }
});

/* ------------------------------------------- Part 2: algorithms engine UI */

const algorithmPanel = document.getElementById("algorithm-output-panel");
const algorithmStatus = document.getElementById("algorithm-status");
const algorithmOutput = document.getElementById("algorithm-output");

/** Reveal the algorithm output panel with a heading line and a body of text. */
function showAlgorithmOutput(statusText, bodyText) {
  algorithmStatus.textContent = statusText;
  algorithmOutput.textContent = bodyText;
  algorithmPanel.hidden = false;
}

/** Re-render the roster in the order produced by the hand-written Insertion Sort. */
async function sortRosterBy(field) {
  try {
    const students = await apiRequest(`/students/sorted?by=${encodeURIComponent(field)}`);
    renderRoster(students);
    showAlgorithmOutput(
      `GET /students/sorted?by=${field} - Insertion Sort, ascending.`,
      students.map((s, i) => `${i + 1}. ${s.name} (age ${s.age})`).join("\n"),
    );
  } catch (error) {
    /* banner already shown */
  }
}

document.getElementById("sort-age-btn").addEventListener("click", () => sortRosterBy("age"));
document.getElementById("sort-name-btn").addEventListener("click", () => sortRosterBy("name"));
document.getElementById("reload-btn").addEventListener("click", () => {
  algorithmPanel.hidden = true;
  loadRoster();
});

document.getElementById("search-btn").addEventListener("click", async () => {
  const name = document.getElementById("search-name").value.trim();
  if (!name) {
    showAlgorithmOutput("Binary search", "Enter an exact student name first.");
    return;
  }
  try {
    const student = await apiRequest(`/students/search?name=${encodeURIComponent(name)}`);
    showAlgorithmOutput(
      `GET /students/search?name=${name} - found via Binary Search.`,
      `id: ${student.id}\nname: ${student.name}\nemail: ${student.email}\nage: ${student.age}`,
    );
  } catch (error) {
    if (error.status === 404) {
      // A miss is a normal search outcome, not a broken app -- keep it off the banner.
      hideError();
      showAlgorithmOutput(
        `GET /students/search?name=${name} - 404`,
        `No student named "${name}" is on the roster.`,
      );
    }
  }
});

document.getElementById("report-btn").addEventListener("click", async () => {
  const minAge = document.getElementById("report-min-age").value || "0";
  try {
    const data = await apiRequest(`/students/report?min_age=${encodeURIComponent(minAge)}`);
    showAlgorithmOutput(
      `GET /students/report?min_age=${minAge} - ${data.count_meeting_min_age} student(s) aged ${minAge}+.`,
      data.report,
    );
  } catch (error) {
    /* banner already shown */
  }
});

/* ------------------------------------------------ Part 3: AI Helper panel */

const summaryOutput = document.getElementById("summary-output");
const notesResults = document.getElementById("notes-results");

document.getElementById("summarize-btn").addEventListener("click", async () => {
  const text = document.getElementById("notes-input").value;
  try {
    const summary = await apiRequest("/assistant/summarize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });

    summaryOutput.replaceChildren();

    const topic = document.createElement("p");
    topic.textContent = `Topic: ${summary.topic}`;
    topic.className = "ai-topic";
    summaryOutput.appendChild(topic);

    const difficulty = document.createElement("p");
    difficulty.textContent = `Difficulty: ${summary.difficulty}`;
    difficulty.className = "ai-difficulty";
    summaryOutput.appendChild(difficulty);

    const pointsHeading = document.createElement("p");
    pointsHeading.textContent = summary.key_points.length
      ? "Key points:"
      : "Key points: (none - the notes were empty)";
    summaryOutput.appendChild(pointsHeading);

    if (summary.key_points.length) {
      const list = document.createElement("ul");
      summary.key_points.forEach((point) => {
        const item = document.createElement("li");
        item.textContent = point;
        list.appendChild(item);
      });
      summaryOutput.appendChild(list);
    }

    summaryOutput.hidden = false;
  } catch (error) {
    /* banner already shown */
  }
});

document.getElementById("notes-search-btn").addEventListener("click", async () => {
  const query = document.getElementById("notes-query").value;
  try {
    const ranked = await apiRequest(`/assistant/search?query=${encodeURIComponent(query)}`);

    notesResults.replaceChildren();

    const heading = document.createElement("p");
    heading.textContent = ranked.some((note) => note.score > 0)
      ? `${ranked.length} notes ranked by cosine similarity:`
      : `${ranked.length} notes, all scoring 0.00 (no vocabulary word matched):`;
    notesResults.appendChild(heading);

    const list = document.createElement("ol");
    ranked.forEach((note) => {
      const item = document.createElement("li");

      const score = document.createElement("span");
      score.className = "note-score";
      score.textContent = note.score.toFixed(4);
      item.appendChild(score);

      const body = document.createElement("span");
      body.textContent = ` (note ${note.id}) ${note.text}`;
      item.appendChild(body);

      list.appendChild(item);
    });
    notesResults.appendChild(list);

    notesResults.hidden = false;
  } catch (error) {
    /* banner already shown */
  }
});

/* ------------------------------------------------------------------ start */

loadRoster();
