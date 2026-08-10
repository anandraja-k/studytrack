"""Pydantic request/response models (Pydantic v2).

Creation schemas carry the validation rules; read schemas are built straight from
ORM objects thanks to `from_attributes=True`.
"""

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# --------------------------------------------------------------------------- #
# Students
# --------------------------------------------------------------------------- #
class StudentBase(BaseModel):
    name: str = Field(min_length=1)
    email: str
    # gt=0 rejects a zero or negative age with a 422 before the DB is touched.
    age: int = Field(gt=0)

    @field_validator("email")
    @classmethod
    def email_must_contain_at_sign(cls, value: str) -> str:
        """Reject any e-mail string without an '@' character."""
        if "@" not in value:
            raise ValueError("email must contain an '@' character")
        return value


class StudentCreate(StudentBase):
    """Body for POST /students/."""


class StudentUpdate(BaseModel):
    """Body for PATCH /students/{id} -- every field optional (partial update)."""

    name: Optional[str] = Field(default=None, min_length=1)
    email: Optional[str] = None
    age: Optional[int] = Field(default=None, gt=0)

    @field_validator("email")
    @classmethod
    def email_must_contain_at_sign(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and "@" not in value:
            raise ValueError("email must contain an '@' character")
        return value


class StudentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    age: int


# --------------------------------------------------------------------------- #
# Courses
# --------------------------------------------------------------------------- #
class CourseBase(BaseModel):
    course_name: str = Field(min_length=1)
    # Credits are constrained to 1..6 inclusive here and by a CHECK constraint in models.py.
    credits: int = Field(ge=1, le=6)
    student_id: int = Field(gt=0)


class CourseCreate(CourseBase):
    """Body for POST /courses/."""


class CourseUpdate(BaseModel):
    """Body for PATCH /courses/{id} -- every field optional (partial update)."""

    course_name: Optional[str] = Field(default=None, min_length=1)
    credits: Optional[int] = Field(default=None, ge=1, le=6)
    student_id: Optional[int] = Field(default=None, gt=0)


class CourseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    course_name: str
    credits: int
    student_id: int


# --------------------------------------------------------------------------- #
# Small response envelopes
# --------------------------------------------------------------------------- #
class CourseCountRead(BaseModel):
    student_id: int
    course_count: int


class RosterReportRead(BaseModel):
    report: str
    count_meeting_min_age: int


class SummarizeRequest(BaseModel):
    text: str = ""


class SummaryRead(BaseModel):
    """The fixed three-key shape the summarizer always returns."""

    topic: str
    key_points: List[str]
    difficulty: str


class ScoredNote(BaseModel):
    id: int
    text: str
    score: float
