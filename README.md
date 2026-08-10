# StudyTrack

A single full-stack study management platform for the Trainee Enablement team. One
FastAPI process serves everything:

- **Part 1 — Core app.** A Student/Course roster stored in SQLite through the
  SQLAlchemy ORM, with full CRUD over a JSON API and a plain HTML/CSS/JS dashboard
  that talks to that same backend.
- **Part 2 — Algorithms engine.** An Insertion Sort and a Binary Search written by
  hand, exposed as real endpoints that operate on the live roster and driven from a
  toolbar on the dashboard.
- **Part 3 — AI assistant.** A note summarizer and a semantic note search, both fully
  offline and deterministic, exposed as endpoints and driven from an "AI Helper"
  panel on the same dashboard.

There is no second service, no standalone script and no external API. Every request
the dashboard makes goes to this project's own backend.

---

## Table of contents

1. [Requirements](#requirements)
2. [Setup](#setup)
3. [Running the app](#running-the-app)
4. [Repository layout](#repository-layout)
5. [Data model](#data-model)
6. [API reference](#api-reference)
7. [Using the dashboard](#using-the-dashboard)
8. [End-to-end walkthrough](#end-to-end-walkthrough)
9. [Part 2 — complexity write-up](#part-2--complexity-write-up)
10. [Part 3 — how the AI assistant works](#part-3--how-the-ai-assistant-works)
11. [Git history](#git-history)

---

## Requirements

- Python 3.10 or newer (developed and verified on Python 3.12.3)
- A modern browser
- No API key, no account and no internet connection are needed to run any feature

---

## Setup

From the repository root:

```bash
# 1. create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 2. install the dependencies
pip install -r backend/requirements.txt
```

`backend/requirements.txt` is pinned from the environment this project was built and
verified in:

```
fastapi==0.141.1
SQLAlchemy==2.0.51
pydantic==2.13.4
uvicorn==0.52.1
```

(plus their transitive dependencies).

There is nothing to configure. `.env.example` documents the single optional variable,
`AI_MODE`, whose default value `mock` is what this submission implements — copy it to
`.env` only if you want to set it explicitly. No `.env` file, API key or secret is
committed anywhere in this repository.

---

## Running the app

**This project uses the single-process run mode.** FastAPI serves both the JSON API
and the dashboard, so there is one command and one port.

```bash
# from the repository root, with the virtual environment active
uvicorn backend.main:app --reload
```

Then open **<http://localhost:8000/>** for the dashboard, and
**<http://localhost:8000/docs>** for the Swagger UI (16 documented operations).

Run the command from the **repository root**, not from inside `backend/` — the modules
import each other as `backend.<module>`.

### Seeding

Seeding is automatic. A `lifespan` startup handler in `backend/main.py` creates the
tables and calls `seed_if_empty(db)` from `backend/seed_data.py`, which inserts the
eight seed students **only when the Student table is empty**. (The brief suggests
`@app.on_event("startup")`; `lifespan` is the modern, non-deprecated equivalent and
behaves identically.)

First start against an empty database:

```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
[startup] Seeded 8 students into an empty database.
```

Every later start, so your edits survive a restart:

```
[startup] Database already populated -- skipping seed.
```

To start over, stop the server and delete `studytrack.db` (it is gitignored and
recreated on the next start).

### The other run mode

The two-process mode is not what is submitted, but the code supports it: set
`API_BASE` at the top of `frontend/app.js` to `"http://localhost:8000"`, run the
backend with the command above, and serve `frontend/index.html` on port 5500 (e.g. the
VS Code "Live Server" extension). This works because CORS already names that origin —
see below.

### CORS

`CORSMiddleware` is configured in `backend/main.py` with:

```python
allow_origins=["http://localhost:5500", "http://127.0.0.1:5500"]
```

The wildcard `"*"` is deliberately never used. The submitted single-process mode is
same-origin and does not need CORS at all; the origins are listed as a documented
convenience so the frontend can be developed on a Live Server against this same API.

---

## Repository layout

```
studytrack/
├── backend/
│   ├── main.py            # FastAPI app: routes, CORS, static mount, startup seeding
│   ├── database.py        # engine + sessionmaker + declarative_base + get_db()
│   ├── models.py          # Student, Course ORM models
│   ├── schemas.py         # Pydantic request/response models
│   ├── crud.py            # every database operation
│   ├── algorithms.py      # Part 2: hand-written sort / search / report
│   ├── ai_service.py      # Part 3: summarizer + embedding + cosine similarity
│   ├── seed_data.py       # the exact seed roster + seed_if_empty()
│   └── requirements.txt
├── frontend/
│   ├── index.html         # semantic page structure
│   ├── style.css          # external stylesheet, box model, responsive rule
│   └── app.js             # fetch calls, rendering, event delegation
├── .env.example
├── .gitignore
└── README.md
```

---

## Data model

**Student** — `id` (PK), `name` (not null), `email` (unique, not null), `age` (int).

**Course** — `id` (PK), `course_name` (not null), `credits` (int, 1–6 inclusive),
`student_id` (FK → `students.id`).

The relationship is wired both ways with SQLAlchemy's `relationship()`:
`student.courses` lists that student's enrollments and `course.student` returns the
owning student. **Each Course row is one enrollment**, so the same course name can
legitimately appear under several students.

`credits` is constrained twice: a `CheckConstraint("credits >= 1 AND credits <= 6")` on
the table, and `Field(ge=1, le=6)` on the Pydantic schema so the API rejects an
out-of-range value with a 422 before it ever reaches the database.

Validation on `StudentCreate`:

- `email` runs through a custom `@field_validator` that rejects any string without an
  `@` character (422).
- `age` uses `Field(gt=0)`, so zero and negative ages are rejected (422).

Every route obtains its session from the `get_db()` dependency, which is defined with
`yield` inside a `try/finally` and injected with `Depends` — the session is opened
before the route body runs and closed afterwards even if the route raises.

---

## API reference

All bodies and responses are JSON. `<base>` is `http://localhost:8000`.

### Students

| Method | Path | Request body | Response |
| --- | --- | --- | --- |
| `POST` | `/students/` | `{"name": str, "email": str, "age": int}` | **201** `{"id", "name", "email", "age"}` |
| `GET` | `/students/` | — | **200** list of student objects |
| `GET` | `/students/?min_age=<int>` | — | **200** only students with `age >= min_age` |
| `GET` | `/students/{student_id}` | — | **200** student object · **404** if unknown |
| `PATCH` | `/students/{student_id}` | any subset of `{"name", "email", "age"}` | **200** the updated student · **404** if unknown |
| `DELETE` | `/students/{student_id}` | — | **204** no content · **404** if unknown |
| `GET` | `/students/{student_id}/course-count` | — | **200** `{"student_id": int, "course_count": int}` |

Error behaviour: a duplicate e-mail returns **409** with a readable message (the
`IntegrityError` is caught and the session rolled back — it is never an unhandled
500); an e-mail without `@`, or an age of `0` or less, returns **422** from the
validator before the database is touched.

**Which call performs the count.** `GET /students/{id}/course-count` calls
`crud.count_courses_for_student()`, which is:

```python
db.query(func.count(models.Course.id)).filter(models.Course.student_id == student_id).scalar()
```

SQLAlchemy emits `SELECT count(courses.id) AS count_1 FROM courses WHERE
courses.student_id = ?`. The count is computed by the database; no course rows are
loaded into Python and `len()` is never used.

### Courses

| Method | Path | Request body | Response |
| --- | --- | --- | --- |
| `POST` | `/courses/` | `{"course_name": str, "credits": 1..6, "student_id": int}` | **201** `{"id", "course_name", "credits", "student_id"}` · **404** if the student does not exist |
| `GET` | `/courses/` | — | **200** list of course objects (optional `?student_id=` filter) |
| `GET` | `/courses/{course_id}` | — | **200** course object · **404** if unknown |
| `PATCH` | `/courses/{course_id}` | any subset of the create fields | **200** the updated course · **404** if unknown |
| `DELETE` | `/courses/{course_id}` | — | **204** no content · **404** if unknown |

### Algorithms engine (Part 2)

| Method | Path | Response |
| --- | --- | --- |
| `GET` | `/students/sorted?by=age` (default) or `?by=name` | **200** the roster as a list, sorted ascending by that field · **422** for any other field |
| `GET` | `/students/search?name=<exact name>` | **200** the matching student · **404** if no student has that name |
| `GET` | `/students/report?min_age=<int>` (default `21`) | **200** `{"report": "<multiline string>", "count_meeting_min_age": int}` |

All three read the **live** roster through `crud`, so they reflect anything you have
created, edited or deleted from the dashboard.

> **Implementation note — route order.** These three literal paths are declared *above*
> `/students/{student_id}` in `main.py`. Declared the other way round, FastAPI would
> try to parse `sorted`, `search` and `report` as an integer `student_id` and return a
> 422.

### AI assistant (Part 3)

| Method | Path | Request body | Response |
| --- | --- | --- | --- |
| `POST` | `/assistant/summarize` | `{"text": "<raw notes>"}` | **200** `{"topic": str, "key_points": [str], "difficulty": str}` |
| `GET` | `/assistant/search?query=<text>` | — | **200** the five sample notes as `{"id", "text", "score"}`, sorted by score descending |

`query` defaults to `""`, so `/assistant/search` is callable with no parameter at all.

### Example requests and responses

```bash
$ curl -s "http://localhost:8000/students/sorted?by=age"
[{"id":4,"name":"Farhan Sheikh","email":"farhan.sheikh@example.com","age":18},
 {"id":2,"name":"Rohan Mehta","email":"rohan.mehta@example.com","age":19},
 {"id":7,"name":"Meera Joshi","email":"meera.joshi@example.com","age":20},
 {"id":5,"name":"Priya Iyer","email":"priya.iyer@example.com","age":21},
 {"id":1,"name":"Aditi Rao","email":"aditi.rao@example.com","age":22},
 {"id":6,"name":"Devansh Gupta","email":"devansh.gupta@example.com","age":23},
 {"id":8,"name":"Sameer Khan","email":"sameer.khan@example.com","age":24},
 {"id":3,"name":"Kavya Nair","email":"kavya.nair@example.com","age":25}]

$ curl -s "http://localhost:8000/students/search?name=Priya%20Iyer"
{"id":5,"name":"Priya Iyer","email":"priya.iyer@example.com","age":21}

$ curl -s "http://localhost:8000/students/search?name=Nobody%20Here"      # HTTP 404
{"detail":"No student named 'Nobody Here' is on the roster."}

$ curl -s "http://localhost:8000/students/report?min_age=21"
{"report":"[Age 22] Aditi Rao <aditi.rao@example.com>\n[Age 19] Rohan Mehta <rohan.mehta@example.com>\n[Age 25] Kavya Nair <kavya.nair@example.com>\n[Age 18] Farhan Sheikh <farhan.sheikh@example.com>\n[Age 21] Priya Iyer <priya.iyer@example.com>\n[Age 23] Devansh Gupta <devansh.gupta@example.com>\n[Age 20] Meera Joshi <meera.joshi@example.com>\n[Age 24] Sameer Khan <sameer.khan@example.com>","count_meeting_min_age":5}

$ curl -s -X POST http://localhost:8000/assistant/summarize \
       -H "Content-Type: application/json" \
       -d '{"text": "Binary search requires a sorted array. Binary search halves the range each step! Does that make sense?"}'
{"topic":"binary",
 "key_points":["Binary search requires a sorted array",
               "Binary search halves the range each step",
               "Does that make sense"],
 "difficulty":"easy"}

$ curl -s -X POST http://localhost:8000/assistant/summarize \
       -H "Content-Type: application/json" -d '{"text": ""}'
{"topic":"untitled","key_points":[],"difficulty":"easy"}

$ curl -s "http://localhost:8000/assistant/search?query=binary+search+algorithm"
[{"id":1,"text":"Binary search requires a sorted array and repeatedly halves the search range using a midpoint comparison.","score":0.9486832980505138},
 {"id":2,"text":"Insertion sort builds a sorted list one element at a time by shifting larger elements to the right.","score":0.0},
 {"id":3,"text":"FastAPI uses Pydantic models to validate request bodies and automatically generates Swagger documentation.","score":0.0},
 {"id":4,"text":"SQL joins combine rows from two tables using a matching column, such as inner join, left join, and full join.","score":0.0},
 {"id":5,"text":"Prompt engineering structures a task, context, constraints, and desired output format to guide an LLM's response.","score":0.0}]

$ curl -s "http://localhost:8000/assistant/search?query=xyz+zzz"    # HTTP 200, not a 500
# all five notes, every score 0.0, returned in their original id order
```

---

## Using the dashboard

Open <http://localhost:8000/>. Everything below happens on that one page.

### Roster (Part 1)

- The seeded roster loads automatically and renders as one card per student. Each card
  shows the name, e-mail and age, plus an age input pre-filled with the current age, a
  **Save Age** button and a **Delete** button.
- **Save Age** — change the number in a card's input and click it. The page sends
  `PATCH /students/{id}` with `{"age": <new value>}` and updates that card's age text
  in place.
- **Delete** — sends `DELETE /students/{id}` and removes that card from the DOM.
- **Add a student** — fill in name, e-mail and age and submit. The page sends
  `POST /students/` and appends the new card, including the id the backend assigned,
  without reloading.
- **Errors** — if a request fails or the backend is unreachable, a red banner appears
  at the top of the page ("Could not reach the StudyTrack backend. Is the server
  running on port 8000?"). Stop the uvicorn process and click **Reset order** to see
  it. It is a real DOM element, not a `console.log` and not an `alert()`.

Implementation details worth knowing:

- Cards are built with `document.createElement` and `appendChild`; the page never
  builds list markup by concatenating `innerHTML` strings.
- **Exactly one** click listener is attached, to `#roster-list`. It uses `event.target`
  to work out whether a Save Age button or a Delete button was clicked and which card
  it belongs to (event delegation). No listener is attached per card or per button.
- The roster container and every card carry explicit `padding`, `margin` and a visible
  `border`, with `box-sizing: border-box` applied globally.
- Below 600px viewport width, a `@media (max-width: 600px)` rule switches the card grid
  from multi-column to a single column. Verified: at 1200px the computed
  `grid-template-columns` is `327.328px 327.328px 327.344px`; at 500px it is `359px`.

### Algorithms toolbar (Part 2)

In the toolbar under the header:

- **Sort by Age** / **Sort by Name** — call `GET /students/sorted?by=…` and re-render
  the roster in the returned order. The ordered list also appears in the "Algorithm
  output" panel.
- **Find Student** — type an exact name and click. Calls `GET /students/search?name=…`
  and shows the matched record, or a plain "No student named X is on the roster."
  message on a 404. A search miss is a normal outcome, so it is not treated as a
  request failure and does not raise the error banner.
- **Build Report** — set a minimum age and click. Calls `GET /students/report?min_age=…`
  and renders the report text with the count in the status line.
- **Reset order** — reloads the roster in database order.

### AI Helper (Part 3)

At the bottom of the page:

- **Summarize** — paste notes into the textarea and click. Calls
  `POST /assistant/summarize` and renders the topic, the difficulty and the key points
  as a list.
- **Search Notes** — type a query and click. Calls `GET /assistant/search?query=…` and
  renders the five notes ranked by score. If nothing matched the vocabulary, it says so
  and shows every note at `0.0000`.

---

## End-to-end walkthrough

Captured from an actual run against a freshly seeded database. The left column is the
command; the block underneath is the real response; the server log for the whole
sequence follows.

```bash
$ uvicorn backend.main:app --reload
INFO:     Started server process [57505]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
[startup] Seeded 8 students into an empty database.
```

**1. The dashboard loads the seeded roster from the backend.** Opening
<http://localhost:8000/> issues these requests, all to this project's own backend:

```
GET http://localhost:8000/
GET http://localhost:8000/style.css
GET http://localhost:8000/app.js
GET http://localhost:8000/students/
```

and renders 8 cards, the first reading `Aditi Rao / aditi.rao@example.com / Age: 22`.

**2. Edit a student's age** (the dashboard's Save Age button issues exactly this):

```bash
$ curl -s -X PATCH http://localhost:8000/students/1 \
       -H "Content-Type: application/json" -d '{"age": 27}'
{"id":1,"name":"Aditi Rao","email":"aditi.rao@example.com","age":27}
```

**3. Add a student** (the dashboard's form issues exactly this):

```bash
$ curl -s -X POST http://localhost:8000/students/ \
       -H "Content-Type: application/json" \
       -d '{"name": "Nikhil Verma", "email": "nikhil.verma@example.com", "age": 26}'
{"id":9,"name":"Nikhil Verma","email":"nikhil.verma@example.com","age":26}
```

**4. Delete a student** (the dashboard's Delete button issues exactly this):

```bash
$ curl -s -o /dev/null -w "%{http_code}\n" -X DELETE http://localhost:8000/students/9
204
```

**5. Enroll a student in two courses, then count them:**

```bash
$ curl -s -X POST http://localhost:8000/courses/ -H "Content-Type: application/json" \
       -d '{"course_name": "Data Structures", "credits": 4, "student_id": 1}'
{"id":1,"course_name":"Data Structures","credits":4,"student_id":1}

$ curl -s -X POST http://localhost:8000/courses/ -H "Content-Type: application/json" \
       -d '{"course_name": "Database Systems", "credits": 3, "student_id": 1}'
{"id":2,"course_name":"Database Systems","credits":3,"student_id":1}

$ curl -s http://localhost:8000/students/1/course-count
{"student_id":1,"course_count":2}
```

Server log for steps 1–5:

```
INFO:     127.0.0.1:57538 - "GET /students/ HTTP/1.1" 200 OK
INFO:     127.0.0.1:57540 - "PATCH /students/1 HTTP/1.1" 200 OK
INFO:     127.0.0.1:57554 - "POST /students/ HTTP/1.1" 201 Created
INFO:     127.0.0.1:57570 - "DELETE /students/9 HTTP/1.1" 204 No Content
INFO:     127.0.0.1:57582 - "POST /courses/ HTTP/1.1" 201 Created
INFO:     127.0.0.1:57584 - "POST /courses/ HTTP/1.1" 201 Created
INFO:     127.0.0.1:57588 - "GET /students/1/course-count HTTP/1.1" 200 OK
```

**6. The filter and the failure cases:**

```bash
$ curl -s "http://localhost:8000/students/?min_age=20"
# Aditi Rao (22), Kavya Nair (25), Priya Iyer (21), Devansh Gupta (23),
# Meera Joshi (20), Sameer Khan (24) -- nobody under 20

$ curl -s -X POST http://localhost:8000/students/ -H "Content-Type: application/json" \
       -d '{"name": "No At", "email": "noatsign.example.com", "age": 20}'      # HTTP 422
{"detail":[{"type":"value_error","loc":["body","email"],
            "msg":"Value error, email must contain an '@' character", ...}]}

$ curl -s -X POST http://localhost:8000/students/ -H "Content-Type: application/json" \
       -d '{"name": "Dup", "email": "aditi.rao@example.com", "age": 20}'       # HTTP 409
{"detail":"A student with the e-mail 'aditi.rao@example.com' already exists."}

$ curl -s http://localhost:8000/students/999                                    # HTTP 404
{"detail":"Student 999 not found."}

$ curl -s -X POST http://localhost:8000/courses/ -H "Content-Type: application/json" \
       -d '{"course_name": "Bad", "credits": 9, "student_id": 1}'               # HTTP 422
```

```
INFO:     127.0.0.1:58732 - "POST /students/ HTTP/1.1" 422 Unprocessable Entity
INFO:     127.0.0.1:58742 - "POST /students/ HTTP/1.1" 409 Conflict
INFO:     127.0.0.1:58744 - "GET /students/999 HTTP/1.1" 404 Not Found
INFO:     127.0.0.1:58748 - "POST /courses/ HTTP/1.1" 422 Unprocessable Entity
```

Note the 409 and the 404: bad input is handled and reported, never an unhandled 500.

**7. Restarting is safe** — the seed does not run twice and step 2's edit survives:

```
[startup] Database already populated -- skipping seed.

$ curl -s http://localhost:8000/students/1
{"id":1,"name":"Aditi Rao","email":"aditi.rao@example.com","age":27}
```

---

## Part 2 — complexity write-up

**Insertion Sort.** For each element the algorithm holds it as a key and shifts every
already-sorted element larger than that key one slot to the right. In the worst case —
a roster in descending age order, so every key is smaller than everything before it —
iteration `i` shifts all `i` preceding elements, giving `1 + 2 + … + (n-1) = n(n-1)/2`
operations, which is **O(n²)**. In the best case — a roster already in ascending order —
the very first comparison of each inner `while` fails because the element to the left is
already smaller, so nothing is ever shifted and the outer loop does exactly one
comparison per element: **O(n)**. Roster data is a good fit for this because it is small
(eight students here) and frequently near-sorted after an edit, which lands close to the
linear end of that range rather than the quadratic one.

**Binary Search.** Binary Search compares the target with the middle element and then
discards half the remaining range, and that discard is only sound if the list is sorted
**on the field being compared** — sorted order is precisely what guarantees the
discarded half cannot contain the target. On an unsorted list the algorithm would throw
away the half the target actually sits in and report "not found" for a record that is
present, which is why `GET /students/search` sorts the roster by name with `sorted()`
before searching by name; a list ordered by age would be useless for a name lookup. The
payoff for that precondition is the halving itself: **O(log n)** comparisons instead of
the **O(n)** of scanning every record.

---

## Part 3 — how the AI assistant works

**Mode used for this submission: `mock`.** Every acceptance criterion is satisfied by
the mock path alone. No real LLM or embedding provider is called, no `AI_MODE=real`
code path is implemented, and therefore **no API key exists anywhere in this
repository** — `.env.example` names the `AI_MODE` variable and nothing else. Both
features run with zero network access; verified by executing them with every socket
call in the process patched to raise, and by confirming `backend/ai_service.py` imports
only `math`, `os`, `re` and `typing`.

### Summarizer

`summarize_notes(raw_text)` always returns exactly three keys — `topic`, `key_points`,
`difficulty` — no matter what it is given, which is the structured-output pattern a
real LLM would be constrained to. It is deterministic: identical input produces
byte-identical output every time.

- **`topic` rule (the one chosen and used):** the **most frequent non-trivial word** in
  the text, where non-trivial means at least four characters long and not in a small
  stopword list ("that", "this", "with", "from", …). Ties are broken by earliest
  appearance, so the result never depends on iteration luck. If no word qualifies, it
  falls back to the most frequent token of any length; if the text has no word
  characters at all, it falls back to `"untitled"`.
- **`key_points`:** the text is split on `.`, `!` and `?`; each fragment is stripped and
  its internal whitespace runs collapsed; empty fragments are dropped; the first three
  survivors are kept.
- **`difficulty` thresholds:** total word count **under 40 → `"easy"`**, **40 to 100
  inclusive → `"medium"`**, **over 100 → `"hard"`**.
- **Empty input:** `summarize_notes("")` and `summarize_notes(" ")` do not raise. They
  return `topic: "untitled"` (there is no first line and no word to count, so the normal
  rule has nothing to work with), `key_points: []` (no sentences to extract), and
  `difficulty: "easy"` (a word count of 0 falls under the 40-word threshold).

### The prompt a real LLM would receive

If an `AI_MODE=real` path were wired in, this is the exact prompt that would be sent to
produce the identical JSON shape. It is written in the role / task / context /
constraints / output-format structure:

```
You are a study-notes summarizer for StudyTrack, an internal learning platform used by
software-engineering trainees.

TASK
Read the trainee's raw study notes below and produce a compact structured summary of
them.

CONTEXT
The notes are informal, pasted straight from a trainee's own revision material. They
cover software-engineering topics such as algorithms, web frameworks, databases and
prompt engineering. The summary is rendered directly in a dashboard panel, so it must
be short and immediately readable.

CONSTRAINTS
- Derive everything from the notes themselves. Do not add facts, opinions or topics
  that are not present in the input.
- "topic" must be a single lower-case word or short phrase naming the main subject.
- "key_points" must contain at most 3 items, each a single sentence taken or closely
  paraphrased from the notes, with no leading bullet characters or numbering.
- "difficulty" must be exactly one of: "easy", "medium", "hard". Judge it by the
  conceptual load and the length of the notes, not by your own confidence.
- If the notes are empty or contain no usable content, return "untitled" as the topic,
  an empty key_points list, and "easy" as the difficulty.

OUTPUT FORMAT
Reply with a single JSON object and nothing else -- no markdown fences, no commentary
before or after it. The object must have exactly these three keys, in this order:

{
  "topic": "<string>",
  "key_points": ["<string>", "..."],
  "difficulty": "easy" | "medium" | "hard"
}

STUDY NOTES
"""
{raw_text}
"""
```

### Embeddings and similarity

`mock_embed(text)` turns any string into a fixed-length 12-dimensional vector — a word
count over this fixed vocabulary, in this order:

```
["sort", "search", "binary", "insertion", "sql", "join",
 "fastapi", "pydantic", "prompt", "llm", "database", "validate"]
```

Tokenization lower-cases the input and splits on any run of characters that are not
letters or digits, so spaces, punctuation and apostrophes all separate tokens — `"LLM's"`
becomes the two tokens `llm` and `s`. Only exact whole tokens count: `"sorted"` is a
different token from `"sort"` and contributes nothing. The result is always a list of
exactly 12 numbers; for an empty string it is twelve zeros.

`cosine_similarity(vec_a, vec_b)` is the formula written out from first principles — the
dot product divided by the product of the two magnitudes, using `math.sqrt`. No
linear-algebra library is involved.

- **Zero-vector rule:** if either vector has an L2 norm of exactly 0 — which happens
  whenever a text contains none of the 12 vocabulary words, such as an empty query or
  one made entirely of out-of-vocabulary words — the function returns `0.0` immediately.
  It can never raise `ZeroDivisionError`.
- The result is clamped to cosine similarity's true mathematical range of `[-1, 1]`,
  because floating-point rounding could otherwise return `1.0000000000000002` for a
  vector compared with itself. A vector compared with itself therefore returns `1.0`, up
  to ordinary floating-point rounding (one vocabulary combination comes back as
  `0.9999999999999998` — the honest result of the arithmetic, well within tolerance).
- Two non-zero vectors with no overlapping non-zero positions return exactly `0.0`.

`GET /assistant/search` embeds every note and the query, scores each pair, and sorts
descending. The sort is Python's `sorted`, which is **stable**, so when the query embeds
to an all-zero vector every note scores `0.0` and they come back in their original id
order — a successful 200 response, never a division-by-zero error.

Worked example: the query `"binary search algorithm"` embeds with `binary = 1` and
`search = 1` (`algorithm` is not in the vocabulary). Note 1 embeds with `binary = 1` and
`search = 2`, giving a dot product of 3 over magnitudes `√2 × √5`, so **0.9487** — and
note 1 ranks first. None of the other four notes share a vocabulary word with that
query, so they all score `0.0`.

---

## Git history

The work is split across two feature branches, each committed to more than once and
merged back into `main` with `--no-ff` so the merge commits are real and visible:

```
$ git log --graph --oneline
*   Merge branch 'feature/ai-assistant'
|\
| * Wire the AI assistant into the API and the dashboard
| * Add offline AI assistant module
|/
*   Merge branch 'feature/algorithms-engine'
|\
| * Wire the algorithms engine into the API and the dashboard
| * Add hand-written algorithms module
|/
* Add Part 1: StudyTrack CRUD service and dashboard
* Scaffold StudyTrack repository
```

`git log --graph --all` shows the same structure with both branch heads.
