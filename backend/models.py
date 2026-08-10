"""SQLAlchemy ORM models for StudyTrack.

A Student owns many Course rows. Each Course row represents ONE enrollment, so the
same course name may legitimately appear several times across different students.
"""

from sqlalchemy import CheckConstraint, Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from backend.database import Base


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    age = Column(Integer, nullable=False)

    # student.courses -> list of that student's enrollments.
    # Deleting a student removes their enrollments rather than orphaning them.
    courses = relationship(
        "Course",
        back_populates="student",
        cascade="all, delete-orphan",
    )


class Course(Base):
    __tablename__ = "courses"
    # Database-level guard so credits stay in range even if a row is inserted
    # outside the API (the Pydantic Field(ge=1, le=6) covers the API path).
    __table_args__ = (
        CheckConstraint("credits >= 1 AND credits <= 6", name="ck_courses_credits_range"),
    )

    id = Column(Integer, primary_key=True, index=True)
    course_name = Column(String, nullable=False)
    credits = Column(Integer, nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)

    # course.student -> the owning student.
    student = relationship("Student", back_populates="courses")
