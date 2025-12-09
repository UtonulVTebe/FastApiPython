from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.database import get_session
from app.models import User, Course, UC
from app.schemas import ProfileResponse, CourseResponse
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
        
        if user.role == "Teacher":
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

