from pathlib import Path
import sys

from sqlmodel import Session

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from app.database import engine, create_db_and_tables
from app.models import User, Course, UC
from app.core.security import hash_password
from app.core.helper import status_Course


def ensure_dirs():
    content_root = Path("content")
    courses_dir = content_root / "courses"
    courses_dir.mkdir(parents=True, exist_ok=True)
    return courses_dir


def write_course_json(course_id: int, courses_dir: Path, lectures: dict):
    file_path = courses_dir / f"{course_id}.json"
    import json

    file_path.write_text(json.dumps(lectures, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(file_path)


def seed():
    create_db_and_tables()
    courses_dir = ensure_dirs()

    with Session(engine) as session:
        # Users
        teacher = User(
            login="teacher",
            password=hash_password("teacher123"),
            name="Alice Teacher",
            role="Teacher",
        )
        student = User(
            login="student",
            password=hash_password("student123"),
            name="Bob Student",
            role="Student",
        )
        session.add(teacher)
        session.add(student)
        session.commit()
        session.refresh(teacher)
        session.refresh(student)

        # Courses (created by teacher)
        course_public = Course(
            title="Public Course",
            status=status_Course.public,
            URL="",  # will set after file is written
            creator_id=teacher.id,
        )
        course_private = Course(
            title="Private Course",
            status=status_Course.private,
            URL="",
            creator_id=teacher.id,
        )
        session.add(course_public)
        session.add(course_private)
        session.commit()
        session.refresh(course_public)
        session.refresh(course_private)

        # Enroll student to private course
        session.add(UC(user_id=student.id, course_id=course_private.id))
        session.commit()

        # Prepare course JSON content
        lectures_public = {
            "Lection1": {
                "file_to_text": f"courses/{course_public.id}/lecture1.html",
                "Tasks": f"courses/{course_public.id}/tasks1.json",
            },
            "Lection2": {
                "file_to_text": f"courses/{course_public.id}/lecture2.html",
                "Tasks": f"courses/{course_public.id}/tasks2.json",
            },
        }
        lectures_private = {
            "Lection1": {
                "file_to_text": f"courses/{course_private.id}/lecture1.html",
                "Tasks": f"courses/{course_private.id}/tasks1.json",
            }
        }

        # Write course JSON files
        public_json_path = write_course_json(course_public.id, courses_dir, lectures_public)
        private_json_path = write_course_json(course_private.id, courses_dir, lectures_private)

        # Update course URLs to point to local JSON files
        course_public.URL = public_json_path
        course_private.URL = private_json_path
        session.add(course_public)
        session.add(course_private)
        session.commit()

        # Create lecture and task sample files
        for course in (course_public, course_private):
            base = courses_dir / str(course.id)
            base.mkdir(parents=True, exist_ok=True)
            # lectures
            (base / "lecture1.html").write_text(
                f"<h1>Lecture 1 for course {course.title}</h1><p>Hello!</p>",
                encoding="utf-8",
            )
            (base / "lecture2.html").write_text(
                f"<h1>Lecture 2 for course {course.title}</h1><p>More text</p>",
                encoding="utf-8",
            )
            # tasks
            tasks = {
                "task1": {"html": "<p>Task 1: write something</p>"},
                "task2": {"html": "<p>Task 2: another exercise</p>"},
            }
            import json

            (base / "tasks1.json").write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8")
            (base / "tasks2.json").write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Seed completed.")
    print("Users:")
    print("  teacher / teacher123 (Teacher)")
    print("  student / student123 (Student)")
    print("Courses:")
    print(f"  Public Course (id={course_public.id})")
    print(f"  Private Course (id={course_private.id})")


if __name__ == "__main__":
    seed()

