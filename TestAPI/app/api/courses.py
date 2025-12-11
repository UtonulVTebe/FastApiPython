import json
from pathlib import Path as FSPath
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, HTTPException, Path
from sqlmodel import Session, select
from app.database import get_session
from app.models import Course, UC, User
from app.schemas import CourseContentResponse, CourseResponse, CourseCreate, CourseUpdate
from app.core.helper import status_Course
from app.api.auth import get_current_user

router = APIRouter(prefix="/courses", tags=["courses"])

# Используем абсолютный путь для CONTENT_ROOT
CONTENT_ROOT = FSPath(__file__).parent.parent.parent / "content"
CONTENT_ROOT = CONTENT_ROOT.resolve()
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

    try:
        # Пробуем относительный путь от CONTENT_ROOT
        file_path = (CONTENT_ROOT / path_str).resolve()
        
        # Проверяем, что файл находится внутри CONTENT_ROOT
        try:
            rel = file_path.relative_to(CONTENT_ROOT)
        except ValueError:
            # Если путь не внутри CONTENT_ROOT, пробуем как абсолютный
            file_path = FSPath(path_str).resolve()
            try:
                rel = file_path.relative_to(CONTENT_ROOT)
            except ValueError:
                # Если все равно не получается, возвращаем как есть (может быть внешний URL)
                return path_str

        if not file_path.exists():
            return path_str  # Возвращаем оригинальный путь если файл не найден

        return f"/content/{rel.as_posix()}"
    except Exception:
        # В случае любой ошибки возвращаем оригинальный путь
        return path_str


def _rewrite_local_links(data):
    """
    Рекурсивно проходит по dict/list и переписывает строковые пути на серверные ссылки.
    """
    try:
        if isinstance(data, dict):
            return {k: _rewrite_local_links(v) for k, v in data.items()}
        if isinstance(data, list):
            return [_rewrite_local_links(v) for v in data]
        if isinstance(data, str):
            return _make_file_url(data)
        return data
    except Exception as e:
        # В случае ошибки возвращаем данные как есть
        return data


@router.get("/{course_id}/content", response_model=CourseContentResponse)
def get_course_content(
    course_id: int = Path(...),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Курс не найден")

    user = current_user
    user_id = user.id

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


TEACH_ROLES = {"Teacher", "Admin"}


@router.post("", response_model=CourseResponse)
def create_course(
    course_data: CourseCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Создать новый курс (только для преподавателей)"""
    if current_user.role not in TEACH_ROLES:
        raise HTTPException(status_code=403, detail="Только преподаватели или администраторы могут создавать курсы")
    
    if current_user.id is None:
        raise HTTPException(status_code=500, detail="Ошибка данных пользователя")
    
    # Сохраняем JSON структуру курса в файл
    course_id = None  # Будет установлен после создания записи в БД
    course_file_path = COURSE_CONTENT_DIR / "temp.json"
    
    # Сначала создаем курс в БД
    new_course = Course(
        title=course_data.title,
        status=course_data.status,
        URL="",  # Будет установлен после сохранения файла
        creator_id=current_user.id
    )
    session.add(new_course)
    session.commit()
    session.refresh(new_course)
    
    if new_course.id is None:
        raise HTTPException(status_code=500, detail="Ошибка при создании курса")
    
    course_id = new_course.id
    
    # Сохраняем JSON файл курса
    course_file_path = COURSE_CONTENT_DIR / f"{course_id}.json"
    COURSE_CONTENT_DIR.mkdir(parents=True, exist_ok=True)
    course_file_path.write_text(json.dumps(course_data.content, ensure_ascii=False, indent=2), encoding="utf-8")
    
    # Обновляем URL курса
    new_course.URL = str(course_file_path.relative_to(CONTENT_ROOT))
    session.add(new_course)
    session.commit()
    session.refresh(new_course)
    
    return CourseResponse(
        id=new_course.id,
        title=new_course.title,
        status=new_course.status,
        URL=new_course.URL,
        creator_id=new_course.creator_id
    )


@router.put("/{course_id}", response_model=CourseResponse)
def update_course(
    course_id: int = Path(...),
    course_data: CourseUpdate = ...,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Обновить курс (только для создателя)"""
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Курс не найден")
    
    if current_user.id is None:
        raise HTTPException(status_code=500, detail="Ошибка данных пользователя")
    
    if course.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Только создатель может редактировать курс")
    
    # Обновляем поля курса
    if course_data.title is not None:
        course.title = course_data.title
    if course_data.status is not None:
        course.status = course_data.status
    
    # Обновляем JSON файл курса если изменился content
    if course_data.content is not None:
        course_file_path = COURSE_CONTENT_DIR / f"{course_id}.json"
        COURSE_CONTENT_DIR.mkdir(parents=True, exist_ok=True)
        course_file_path.write_text(
            json.dumps(course_data.content, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        course.URL = str(course_file_path.relative_to(CONTENT_ROOT))
    
    session.add(course)
    session.commit()
    session.refresh(course)
    
    return CourseResponse(
        id=course.id,
        title=course.title,
        status=course.status,
        URL=course.URL,
        creator_id=course.creator_id
    )


@router.delete("/{course_id}", response_model=dict)
def delete_course(
    course_id: int = Path(...),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Удалить курс (только создатель)"""
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Курс не найден")

    if current_user.id is None or course.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Только создатель может удалить курс")

    # Пытаемся удалить файл контента
    if course.URL:
        file_path = (CONTENT_ROOT / course.URL).resolve()
        try:
            if CONTENT_ROOT in file_path.parents or CONTENT_ROOT == file_path.parent:
                if file_path.exists():
                    file_path.unlink()
        except Exception:
            # не блокируем удаление если файл не удалился
            pass

    session.delete(course)
    session.commit()
    return {"message": "Курс удален", "id": course_id}
