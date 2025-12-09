import json
from pathlib import Path as FSPath
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlmodel import Session, select
from app.database import get_session
from app.models import Course, UC, User
from app.schemas import CourseContentResponse, CourseResponse
from app.core.helper import status_Course

router = APIRouter(prefix="/courses", tags=["courses"])

CONTENT_ROOT = FSPath("content")
COURSE_CONTENT_DIR = CONTENT_ROOT / "courses"


def _load_course_content(course: Course) -> dict:
    """
    Читает JSON-файл курса.
    Путь берется из course.URL если это путь к файлу, иначе из content/courses/{id}.json.
    """
    # если URL указывает на локальный файл
    if course.URL and FSPath(course.URL).exists():
        file_path = FSPath(course.URL)
    else:
        file_path = COURSE_CONTENT_DIR / f"{course.id}.json"

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Файл курса не найден")

    try:
        return json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Некорректный JSON курса")


def _make_file_url(path_str: str) -> str:
    """
    Формирует ссылку, доступную с клиента:
    - Если http/https — оставляем как есть
    - Иначе ищем файл под папкой content/ и возвращаем /content/{relative}
    """
    parsed = urlparse(path_str)
    if parsed.scheme in ("http", "https"):
        return path_str

    file_path = (CONTENT_ROOT / path_str).resolve()

    # защита от выхода за пределы content/
    if CONTENT_ROOT.resolve() not in file_path.parents and file_path != CONTENT_ROOT.resolve():
        raise HTTPException(status_code=400, detail="Некорректный путь к файлу")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Файл не найден: {path_str}")

    rel = file_path.relative_to(CONTENT_ROOT)
    return f"/content/{rel.as_posix()}"


def _rewrite_local_links(data):
    """
    Рекурсивно проходит по dict/list и переписывает строковые пути на серверные ссылки.
    """
    if isinstance(data, dict):
        return {k: _rewrite_local_links(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_rewrite_local_links(v) for v in data]
    if isinstance(data, str):
        return _make_file_url(data)
    return data


@router.get("/{course_id}/content", response_model=CourseContentResponse)
def get_course_content(
    course_id: int = Path(...),
    user_id: int = Query(...),
    session: Session = Depends(get_session),
):
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Курс не найден")

    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    # Проверка доступа по статусу курса
    if course.status == status_Course.draft:
        if course.creator_id != user_id:
            raise HTTPException(status_code=403, detail="Нет доступа к черновику")
    elif course.status == status_Course.private:
        # приватный курс доступен, если пользователь создатель или записан в UC
        if course.creator_id != user_id:
            uc = session.exec(
                select(UC).where(UC.course_id == course_id, UC.user_id == user_id)
            ).first()
            if not uc:
                raise HTTPException(status_code=403, detail="Нет доступа к курсу")
    # public доступен всем

    content_raw = _load_course_content(course)
    content = _rewrite_local_links(content_raw)

    course_dto = CourseResponse(
        id=course.id,
        title=course.title,
        status=course.status,
        URL=course.URL,
        creator_id=course.creator_id,
    )

    return CourseContentResponse(course=course_dto, content=content)

