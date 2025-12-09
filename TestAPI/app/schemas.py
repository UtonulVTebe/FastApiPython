from typing import Optional, List
from pydantic import BaseModel
from app.core.helper import status_Course


class UserRegister(BaseModel):
    login: str
    password: str
    name: str


class UserResponse(BaseModel):
    id: int
    name: str
    role: Optional[str] = None


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

