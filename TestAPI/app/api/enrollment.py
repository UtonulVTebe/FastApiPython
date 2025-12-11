from typing import List
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlmodel import Session, select
from app.database import get_session
from app.models import Course, UC, User
from app.schemas import UserResponse
from app.core.helper import status_Course
from app.api.auth import get_current_user

router = APIRouter(prefix="/courses", tags=["enrollment"])


@router.post("/{course_id}/enroll/{user_id}", response_model=dict)
def enroll_student(
    course_id: int = Path(...),
    user_id: int = Path(...),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """
    Преподаватель зачисляет ученика на курс.
    """
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Курс не найден")
    
    # Проверяем права - только создатель курса может зачислять
    if course.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Только создатель курса может зачислять учеников")
    
    # Проверяем, что пользователь существует
    student = session.get(User, user_id)
    if not student:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    # Проверяем, не зачислен ли уже
    existing = session.exec(
        select(UC).where(UC.course_id == course_id, UC.user_id == user_id)
    ).first()
    
    if existing:
        return {"message": "Ученик уже зачислен на курс", "enrolled": True}
    
    # Зачисляем
    uc = UC(user_id=user_id, course_id=course_id)
    session.add(uc)
    session.commit()
    
    return {"message": "Ученик успешно зачислен на курс", "enrolled": True}


@router.delete("/{course_id}/enroll/{user_id}", response_model=dict)
def unenroll_student(
    course_id: int = Path(...),
    user_id: int = Path(...),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """
    Преподаватель отчисляет ученика с курса.
    """
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Курс не найден")
    
    # Проверяем права
    if course.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Только создатель курса может отчислять учеников")
    
    # Удаляем зачисление
    uc = session.exec(
        select(UC).where(UC.course_id == course_id, UC.user_id == user_id)
    ).first()
    
    if not uc:
        return {"message": "Ученик не был зачислен на курс", "enrolled": False}
    
    session.delete(uc)
    session.commit()
    
    return {"message": "Ученик отчислен с курса", "enrolled": False}


@router.get("/{course_id}/students", response_model=dict)
def list_course_students(
    course_id: int = Path(...),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """
    Получить список зачисленных учеников на курс (только для преподавателя).
    """
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Курс не найден")
    
    # Проверяем права
    if course.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Только создатель курса может просматривать список учеников")
    
    # Получаем всех зачисленных учеников
    ucs = session.exec(
        select(UC).where(UC.course_id == course_id)
    ).all()
    
    student_ids = [uc.user_id for uc in ucs]
    total = len(student_ids)
    
    if not student_ids:
        return {"items": [], "total": 0, "page": page, "page_size": page_size}
    
    start = (page - 1) * page_size
    end = start + page_size
    paginated_ids = student_ids[start:end]
    
    # Получаем информацию о пользователях
    students = []
    for user_id in paginated_ids:
        user = session.get(User, user_id)
        if user:
            students.append(UserResponse(id=user.id, name=user.name, role=user.role))
    
    return {
        "items": students,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{course_id}/available-students", response_model=dict)
def list_available_students(
    course_id: int = Path(...),
    search: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """
    Получить список доступных учеников для зачисления (все пользователи кроме уже зачисленных).
    """
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Курс не найден")
    
    # Проверяем права
    if course.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Только создатель курса может просматривать список учеников")
    
    # Получаем уже зачисленных
    ucs = session.exec(
        select(UC).where(UC.course_id == course_id)
    ).all()
    enrolled_ids = {uc.user_id for uc in ucs}
    
    # Получаем всех пользователей (студентов)
    all_users = session.exec(select(User)).all()
    
    # Фильтруем: только студенты, не зачисленные на курс
    available = []
    for user in all_users:
        if user.role == "Student" and user.id not in enrolled_ids:
            if not search or search.lower() in user.name.lower():
                available.append(UserResponse(id=user.id, name=user.name, role=user.role))
    
    total = len(available)
    start = (page - 1) * page_size
    end = start + page_size
    
    return {
        "items": available[start:end],
        "total": total,
        "page": page,
        "page_size": page_size,
    }

