from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlmodel import Session, select
from app.database import get_session
from app.models import User, Course, UC
from app.schemas import ProfileResponse, CourseResponse, UserResponse, UserUpdateName, UserRoleUpdate, UsersPage
from app.core.helper import status_Course
from app.api.auth import get_current_user

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("", response_model=ProfileResponse)
def get_profile(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    try:
        user = current_user
        user_id = user.id
        if not user or user.id is None:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        created_courses = []
        enrolled_courses = []
        
        if user.role in {"Teacher", "Admin"}:
            created_courses_query = session.exec(
                select(Course).where(Course.creator_id == user_id)
            ).all()
            created_courses = [
                CourseResponse(
                    id=course.id,
                    title=course.title,
                    status=course.status,
                    URL=course.URL,
                    creator_id=course.creator_id
                )
                for course in created_courses_query
                if course.id is not None
            ]
        
        enrolled_ucs = session.exec(
            select(UC).where(UC.user_id == user_id)
        ).all()
        enrolled_course_ids = {uc.course_id for uc in enrolled_ucs}
        
        all_courses = session.exec(select(Course)).all()
        
        for course in all_courses:
            if course.id is None:
                continue
            
            if course.creator_id is not None and course.creator_id == user_id:
                continue
            
            if course.status == status_Course.draft:
                continue
            
            if course.status == status_Course.public:
                enrolled_courses.append(
                    CourseResponse(
                        id=course.id,
                        title=course.title,
                        status=course.status,
                        URL=course.URL,
                        creator_id=course.creator_id
                    )
                )
            elif course.status == status_Course.private:
                if course.id in enrolled_course_ids:
                    enrolled_courses.append(
                        CourseResponse(
                            id=course.id,
                            title=course.title,
                            status=course.status,
                            URL=course.URL,
                            creator_id=course.creator_id
                        )
                    )
        
        return ProfileResponse(
            id=user.id,
            name=user.name,
            role=user.role,
            created_courses=created_courses,
            enrolled_courses=enrolled_courses
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при получении профиля: {str(e)}")


@router.get("/user/{user_id}", response_model=UserResponse)
def get_user_by_id(
    user_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Получить информацию о пользователе по ID (для преподавателей)"""
    if current_user.role not in {"Teacher", "Admin"}:
        raise HTTPException(status_code=403, detail="Только преподаватели или администраторы могут просматривать информацию о других пользователях")
    
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    return UserResponse(id=user.id, name=user.name, role=user.role)


@router.put("/name", response_model=UserResponse)
def update_name(
    payload: UserUpdateName,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Изменение своего имени"""
    user = session.get(User, current_user.id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    new_name = payload.name.strip()
    if not new_name:
        raise HTTPException(status_code=400, detail="Имя не может быть пустым")

    user.name = new_name
    session.add(user)
    session.commit()
    session.refresh(user)
    return UserResponse(id=user.id, name=user.name, role=user.role)


@router.get("/users", response_model=UsersPage)
def list_users(
    search: str = Query(None, description="Поиск по имени или логину"),
    role: str = Query(None, description="Фильтр по роли"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Список пользователей (доступно только администраторам)"""
    if current_user.role != "Admin":
        raise HTTPException(status_code=403, detail="Доступ только для администраторов")

    query = select(User)
    if search:
        like = f"%{search.lower()}%"
        query = query.where(
            (User.name.ilike(like)) | (User.login.ilike(like))
        )
    if role:
        query = query.where(User.role == role)

    total = session.exec(query.with_only_columns(User.id).order_by(None)).all()
    total_count = len(total)

    items = session.exec(
        query.order_by(User.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    users = [UserResponse(id=u.id, name=u.name, role=u.role) for u in items if u.id is not None]
    return UsersPage(items=users, total=total_count, page=page, page_size=page_size)


@router.post("/users/{user_id}/make-teacher", response_model=UserResponse)
def make_teacher(
    user_id: int = Path(...),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Назначить пользователя преподавателем (только администраторы)"""
    if current_user.role != "Admin":
        raise HTTPException(status_code=403, detail="Доступ только для администраторов")

    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    if user.role == "Teacher":
        return UserResponse(id=user.id, name=user.name, role=user.role)

    user.role = "Teacher"
    session.add(user)
    session.commit()
    session.refresh(user)
    return UserResponse(id=user.id, name=user.name, role=user.role)


@router.post("/users/{user_id}/revoke-teacher", response_model=UserResponse)
def revoke_teacher(
    user_id: int = Path(...),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Снять роль преподавателя (только администраторы)"""
    if current_user.role != "Admin":
        raise HTTPException(status_code=403, detail="Доступ только для администраторов")

    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    # Нельзя разжаловать самого себя
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Нельзя изменить свою роль")

    if user.role != "Teacher":
        return UserResponse(id=user.id, name=user.name, role=user.role)

    user.role = "Student"
    session.add(user)
    session.commit()
    session.refresh(user)
    return UserResponse(id=user.id, name=user.name, role=user.role)
