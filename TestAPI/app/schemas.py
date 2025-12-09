from typing import Optional, List
from pydantic import BaseModel
from app.core.helper import status_Course


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

