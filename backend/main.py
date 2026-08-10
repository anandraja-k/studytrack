"""StudyTrack FastAPI application.

One process serves everything: the JSON API, and the dashboard in frontend/ mounted
as static files at "/". Run it from the repository root with:

    uvicorn backend.main:app --reload
"""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Literal, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend import ai_service, algorithms, crud, models, schemas
from backend.database import Base, SessionLocal, engine, get_db
from backend.seed_data import seed_if_empty

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create the tables and seed the roster before the first request is served.

    This is the modern replacement for @app.on_event("startup"), which FastAPI now
    deprecates; the behaviour is identical.
    """
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        inserted = seed_if_empty(db)
        if inserted:
            print(f"[startup] Seeded {inserted} students into an empty database.")
        else:
            print("[startup] Database already populated -- skipping seed.")
    finally:
        db.close()
    yield


app = FastAPI(
    title="StudyTrack",
    description=(
        "Study management platform: Student/Course roster CRUD, a hand-written "
        "sorting/searching engine, and an offline AI study assistant."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# The submitted run mode is single-process (same-origin), so CORS is not strictly
# needed -- it is configured anyway as a documented convenience for developing the
# frontend on a Live Server at port 5500 against this same API. The wildcard "*" is
# deliberately never used.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5500", "http://127.0.0.1:5500"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _get_student_or_404(db: Session, student_id: int) -> models.Student:
    student = crud.get_student(db, student_id)
    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student {student_id} not found.",
        )
    return student


def _get_course_or_404(db: Session, course_id: int) -> models.Course:
    course = crud.get_course(db, course_id)
    if course is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course {course_id} not found.",
        )
    return course


# --------------------------------------------------------------------------- #
# Students -- collection
# --------------------------------------------------------------------------- #
@app.post("/students/", response_model=schemas.StudentRead, status_code=status.HTTP_201_CREATED, tags=["students"])
def create_student(student: schemas.StudentCreate, db: Session = Depends(get_db)):
    """Create a student. A duplicate e-mail is a handled 409, never a 500."""
    try:
        return crud.create_student(db, student)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A student with the e-mail '{student.email}' already exists.",
        )


@app.get("/students/", response_model=List[schemas.StudentRead], tags=["students"])
def list_students(
    min_age: Optional[int] = Query(default=None, ge=0, description="Keep only students aged >= this value."),
    db: Session = Depends(get_db),
):
    """List all students, or only those with age >= min_age when the filter is supplied."""
    return crud.get_students(db, min_age=min_age)


# --------------------------------------------------------------------------- #
# Students -- algorithms engine (Part 2)
#
# ROUTE ORDER MATTERS: these literal /students/<word> paths must be declared ABOVE
# /students/{student_id}, otherwise FastAPI matches the literal segment as a path
# parameter and rejects "sorted"/"search"/"report" as a non-integer id.
#
# All three read the LIVE roster through crud, so they reflect every create, edit
# and delete made from the dashboard -- they are not backed by a static sample list.
# --------------------------------------------------------------------------- #
def _students_as_dicts(db: Session) -> List[dict]:
    """Load the live roster and convert the ORM rows to plain dictionaries."""
    return [
        {"id": s.id, "name": s.name, "email": s.email, "age": s.age}
        for s in crud.get_students(db)
    ]


@app.get("/students/sorted", response_model=List[schemas.StudentRead], tags=["algorithms"])
def sorted_students(
    by: Literal["age", "name"] = Query(default="age", description="Field to sort ascending by."),
    db: Session = Depends(get_db),
):
    """Roster sorted ascending by age (default) or name, using the hand-written Insertion Sort."""
    roster = _students_as_dicts(db)
    algorithms.insertion_sort_by_field(roster, by)  # sorts the list in place
    return roster


@app.get("/students/search", response_model=schemas.StudentRead, tags=["algorithms"])
def search_student_by_name(
    name: str = Query(..., description="Exact student name to look for."),
    db: Session = Depends(get_db),
):
    """Find one student by exact name using the hand-written Binary Search.

    Binary Search needs its input ordered on the field being searched, so the roster
    is first copied into name order with Python's built-in sorted(); only the search
    itself is hand-written.
    """
    roster = _students_as_dicts(db)
    by_name = sorted(roster, key=lambda student: student["name"])
    result = algorithms.binary_search_by_name(by_name, name)
    if result == -1:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No student named '{name}' is on the roster.",
        )
    return result


@app.get("/students/report", response_model=schemas.RosterReportRead, tags=["algorithms"])
def roster_report(
    min_age: int = Query(default=21, ge=0, description="Age threshold for the counted subset."),
    db: Session = Depends(get_db),
):
    """A printable roster report plus how many students are at least `min_age` years old."""
    roster = _students_as_dicts(db)
    return schemas.RosterReportRead(
        report=algorithms.format_roster_report(roster),
        count_meeting_min_age=algorithms.count_students_meeting_min_age(roster, min_age),
    )


# --------------------------------------------------------------------------- #
# Students -- single resource
# --------------------------------------------------------------------------- #
@app.get("/students/{student_id}", response_model=schemas.StudentRead, tags=["students"])
def read_student(student_id: int, db: Session = Depends(get_db)):
    return _get_student_or_404(db, student_id)


@app.patch("/students/{student_id}", response_model=schemas.StudentRead, tags=["students"])
def patch_student(student_id: int, changes: schemas.StudentUpdate, db: Session = Depends(get_db)):
    """Partial update -- only the fields present in the body are written."""
    student = _get_student_or_404(db, student_id)
    try:
        return crud.update_student(db, student, changes)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That e-mail is already used by another student.",
        )


@app.delete("/students/{student_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["students"])
def remove_student(student_id: int, db: Session = Depends(get_db)):
    student = _get_student_or_404(db, student_id)
    crud.delete_student(db, student)
    return None


@app.get("/students/{student_id}/course-count", response_model=schemas.CourseCountRead, tags=["students"])
def student_course_count(student_id: int, db: Session = Depends(get_db)):
    """How many courses this student is enrolled in, counted by a SQL aggregate."""
    _get_student_or_404(db, student_id)
    return schemas.CourseCountRead(
        student_id=student_id,
        course_count=crud.count_courses_for_student(db, student_id),
    )


# --------------------------------------------------------------------------- #
# Courses
# --------------------------------------------------------------------------- #
@app.post("/courses/", response_model=schemas.CourseRead, status_code=status.HTTP_201_CREATED, tags=["courses"])
def create_course(course: schemas.CourseCreate, db: Session = Depends(get_db)):
    """Create one enrollment. The owning student must exist."""
    _get_student_or_404(db, course.student_id)
    try:
        return crud.create_course(db, course)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Course could not be created -- check credits (1-6) and student_id.",
        )


@app.get("/courses/", response_model=List[schemas.CourseRead], tags=["courses"])
def list_courses(
    student_id: Optional[int] = Query(default=None, description="Keep only this student's enrollments."),
    db: Session = Depends(get_db),
):
    return crud.get_courses(db, student_id=student_id)


@app.get("/courses/{course_id}", response_model=schemas.CourseRead, tags=["courses"])
def read_course(course_id: int, db: Session = Depends(get_db)):
    return _get_course_or_404(db, course_id)


@app.patch("/courses/{course_id}", response_model=schemas.CourseRead, tags=["courses"])
def patch_course(course_id: int, changes: schemas.CourseUpdate, db: Session = Depends(get_db)):
    course = _get_course_or_404(db, course_id)
    if changes.student_id is not None:
        _get_student_or_404(db, changes.student_id)
    try:
        return crud.update_course(db, course, changes)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Course could not be updated -- check credits (1-6) and student_id.",
        )


@app.delete("/courses/{course_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["courses"])
def remove_course(course_id: int, db: Session = Depends(get_db)):
    course = _get_course_or_404(db, course_id)
    crud.delete_course(db, course)
    return None


# --------------------------------------------------------------------------- #
# AI assistant (Part 3) -- offline mock mode, no API key and no network call.
# --------------------------------------------------------------------------- #
@app.post("/assistant/summarize", response_model=schemas.SummaryRead, tags=["assistant"])
def summarize(request: schemas.SummarizeRequest):
    """Summarize raw study notes into the fixed {topic, key_points, difficulty} shape."""
    return ai_service.summarize_notes(request.text)


@app.get("/assistant/search", response_model=List[schemas.ScoredNote], tags=["assistant"])
def semantic_search(
    query: str = Query(default="", description="Free text to rank the study notes against."),
):
    """Rank the sample study notes by cosine similarity to `query`, most similar first.

    A query containing none of the 12 vocabulary words scores every note 0.0 and the
    notes come back in id order -- a successful response, never a division by zero.
    """
    return ai_service.search_notes(query)


# --------------------------------------------------------------------------- #
# Static dashboard -- mounted LAST so it never shadows an API route.
# Opening http://localhost:8000/ serves frontend/index.html.
# --------------------------------------------------------------------------- #
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="static")
