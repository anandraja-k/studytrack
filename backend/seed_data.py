"""The exact seed roster used to demonstrate Parts 1 and 2.

These eight records are inserted automatically the first time the app starts against
an empty database, and never again once the Student table has rows.
"""

from sqlalchemy.orm import Session

from backend import models

SEED_STUDENTS = [
    {"name": "Aditi Rao",     "email": "aditi.rao@example.com",     "age": 22},
    {"name": "Rohan Mehta",   "email": "rohan.mehta@example.com",   "age": 19},
    {"name": "Kavya Nair",    "email": "kavya.nair@example.com",    "age": 25},
    {"name": "Farhan Sheikh", "email": "farhan.sheikh@example.com", "age": 18},
    {"name": "Priya Iyer",    "email": "priya.iyer@example.com",    "age": 21},
    {"name": "Devansh Gupta", "email": "devansh.gupta@example.com", "age": 23},
    {"name": "Meera Joshi",   "email": "meera.joshi@example.com",   "age": 20},
    {"name": "Sameer Khan",   "email": "sameer.khan@example.com",   "age": 24},
]


def seed_if_empty(db: Session) -> int:
    """Insert the seed roster only when the Student table is currently empty.

    Returns the number of students inserted (0 when the database already had data),
    which keeps restarts idempotent -- edits made through the dashboard survive them.
    """
    already_present = db.query(models.Student).first()
    if already_present is not None:
        return 0

    db.add_all([models.Student(**record) for record in SEED_STUDENTS])
    db.commit()
    return len(SEED_STUDENTS)
