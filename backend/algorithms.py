"""Hand-written sorting, searching and reporting for the live StudyTrack roster.

These functions operate on plain dictionaries (`{"id", "name", "email", "age"}`)
produced from the Student rows in the database, so the endpoints in main.py sort and
search the real roster rather than a detached sample list.

Nothing here delegates the actual algorithm to a library: the insertion sort and the
binary search are written out step by step.
"""

from typing import Any, Dict, List, Union

Student = Dict[str, Any]

SORTABLE_FIELDS = ("age", "name")


def insertion_sort_by_field(students: List[Student], field: str) -> List[Student]:
    """Sort `students` IN PLACE, ascending, by `field` ("age" or "name").

    Classic Insertion Sort: walk forward from the second element, hold the current
    element as `key`, shift every already-sorted element that is larger than the key
    one slot to the right, then drop the key into the gap that opens up.

    No sorted(), no list.sort(), no library helper -- the comparisons and the shifting
    are all written out below. The list object passed in is mutated and also returned
    for the caller's convenience.
    """
    if field not in SORTABLE_FIELDS:
        raise ValueError(f"Cannot sort by {field!r}; expected one of {SORTABLE_FIELDS}.")

    # Outer loop: everything left of `index` is already in order.
    for index in range(1, len(students)):
        key_record = students[index]
        key_value = key_record[field]
        position = index - 1

        # Inner loop: shift larger-valued records one slot to the right to make room.
        while position >= 0 and students[position][field] > key_value:
            students[position + 1] = students[position]
            position -= 1

        # Final placement of the held key into the gap.
        students[position + 1] = key_record

    return students


def binary_search_by_name(
    sorted_by_name_list: List[Student], name: str
) -> Union[Student, int]:
    """Find the record whose "name" equals `name`; return -1 when there is no match.

    Iterative Binary Search over a list that the CALLER has already sorted
    alphabetically by name. The midpoint uses the overflow-safe form
    `low + (high - low) // 2` rather than `(low + high) // 2`.
    """
    low = 0
    high = len(sorted_by_name_list) - 1

    while low <= high:
        mid = low + (high - low) // 2
        mid_name = sorted_by_name_list[mid]["name"]

        if mid_name == name:
            return sorted_by_name_list[mid]
        if mid_name < name:
            # The target sorts after the midpoint, so discard the left half.
            low = mid + 1
        else:
            # The target sorts before the midpoint, so discard the right half.
            high = mid - 1

    return -1


def format_roster_report(students: List[Student]) -> str:
    """Build a multi-line roster report, one f-string line per student.

    Each line reads: "[Age 22] Aditi Rao <aditi.rao@example.com>".
    """
    lines = []
    for student in students:
        lines.append(f"[Age {student['age']}] {student['name']} <{student['email']}>")
    return "\n".join(lines)


def count_students_meeting_min_age(students: List[Student], min_age: int) -> int:
    """How many students are at least `min_age` years old.

    Written as an explicit loop with a visible accumulator so the counting step is
    readable, rather than collapsed into a one-line sum() generator expression.
    """
    count = 0
    for student in students:
        if student["age"] >= min_age:
            count += 1
    return count
