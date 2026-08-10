"""Database operations.

Route handlers in main.py stay thin: they validate, call one of these functions and
shape the HTTP response. Every actual query lives here.
"""

from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend import models, schemas


# --------------------------------------------------------------------------- #
# Students
# --------------------------------------------------------------------------- #
def get_students(db: Session, min_age: Optional[int] = None) -> List[models.Student]:
    """List students, optionally keeping only those with age >= min_age."""
    query = db.query(models.Student)
    if min_age is not None:
        query = query.filter(models.Student.age >= min_age)
    return query.order_by(models.Student.id).all()


def get_student(db: Session, student_id: int) -> Optional[models.Student]:
    return db.query(models.Student).filter(models.Student.id == student_id).first()


def create_student(db: Session, student: schemas.StudentCreate) -> models.Student:
    db_student = models.Student(name=student.name, email=student.email, age=student.age)
    db.add(db_student)
    db.commit()
    db.refresh(db_student)
    return db_student


def update_student(
    db: Session, db_student: models.Student, changes: schemas.StudentUpdate
) -> models.Student:
    """Partial update: only the fields actually present in the request body are applied."""
    for field, value in changes.model_dump(exclude_unset=True).items():
        setattr(db_student, field, value)
    db.commit()
    db.refresh(db_student)
    return db_student


def delete_student(db: Session, db_student: models.Student) -> None:
    db.delete(db_student)
    db.commit()


def count_courses_for_student(db: Session, student_id: int) -> int:
    """Number of enrollments for one student, counted by the database.

    This is a SQL aggregate -- SELECT count(courses.id) ... WHERE student_id = ? --
    so no course rows are ever loaded into Python and len() is never involved.
    """
    return (
        db.query(func.count(models.Course.id))
        .filter(models.Course.student_id == student_id)
        .scalar()
    )


# --------------------------------------------------------------------------- #
# Courses
# --------------------------------------------------------------------------- #
def get_courses(db: Session, student_id: Optional[int] = None) -> List[models.Course]:
    query = db.query(models.Course)
    if student_id is not None:
        query = query.filter(models.Course.student_id == student_id)
    return query.order_by(models.Course.id).all()


def get_course(db: Session, course_id: int) -> Optional[models.Course]:
    return db.query(models.Course).filter(models.Course.id == course_id).first()


def create_course(db: Session, course: schemas.CourseCreate) -> models.Course:
    db_course = models.Course(
        course_name=course.course_name,
        credits=course.credits,
        student_id=course.student_id,
    )
    db.add(db_course)
    db.commit()
    db.refresh(db_course)
    return db_course


def update_course(
    db: Session, db_course: models.Course, changes: schemas.CourseUpdate
) -> models.Course:
    for field, value in changes.model_dump(exclude_unset=True).items():
        setattr(db_course, field, value)
    db.commit()
    db.refresh(db_course)
    return db_course


def delete_course(db: Session, db_course: models.Course) -> None:
    db.delete(db_course)
    db.commit()
