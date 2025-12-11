from typing import Optional, List
from pydantic import BaseModel
from app.core.helper import status_Course
from app.core.helper import status_Grade


class UserRegister(BaseModel):
    login: str
    password: str
    name: str


class UserLogin(BaseModel):
    login: str
    password: str


class UserResponse(BaseModel):
    id: int
    name: str
    role: Optional[str] = None


class UserUpdateName(BaseModel):
    name: str


class UserRoleUpdate(BaseModel):
    role: str


class UsersPage(BaseModel):
    items: List[UserResponse]
    total: int
    page: int
    page_size: int


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class CourseResponse(BaseModel):
    id: int
    title: str
    status: status_Course
    URL: str
    creator_id: Optional[int] = None
    creator_name: Optional[str] = None


class ProfileResponse(BaseModel):
    id: int
    name: str
    role: Optional[str] = None
    created_courses: List[CourseResponse] = []
    enrolled_courses: List[CourseResponse] = []


class CourseContentResponse(BaseModel):
    course: CourseResponse
    content: dict


class CourseCreate(BaseModel):
    title: str
    status: status_Course = status_Course.draft
    content: dict  # JSON структура курса с лекциями


class CourseUpdate(BaseModel):
    title: Optional[str] = None
    status: Optional[status_Course] = None
    content: Optional[dict] = None


class SubmissionBase(BaseModel):
    course_id: int
    topic_key: str
    lecture_key: str
    task_key: str
    answer: str


class SubmissionCreate(SubmissionBase):
    pass


class SubmissionUpdateGrade(BaseModel):
    status: status_Grade = status_Grade.rated
    grade: Optional[int] = None
    teacher_comment: Optional[str] = None


class SubmissionResponse(BaseModel):
    id: int
    course_id: int
    topic_key: str
    lecture_key: str
    task_key: str
    user_id: int
    answer: str
    status: status_Grade
    grade: Optional[int] = None
    teacher_comment: Optional[str] = None
    user_name: Optional[str] = None  # Имя пользователя (добавляется в API для удобства)

