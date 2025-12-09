from __future__ import annotations
from typing import Optional, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship
from app.core import helper as h

if TYPE_CHECKING:
    from typing import List


class UG(SQLModel, table=True):
    grade_id: int = Field(foreign_key="grade.id", primary_key=True)
    user_id: int = Field(foreign_key="user.id", primary_key=True)


class UC(SQLModel, table=True):
    user_id: int = Field(foreign_key="user.id", primary_key=True)
    course_id: int = Field(foreign_key="course.id", primary_key=True)


class User(SQLModel, table=True):
    __tablename__ = "user"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    role: Optional[str] = Field(default="Student")
    login: str
    password: Optional[str] = None


class Grade(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    URL: str
    status: h.status_Grade = Field(default=h.status_Grade.not_verified)
    grade: int


class Course(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    status: h.status_Course = Field(default=h.status_Course.draft)
    URL: str
    creator_id: Optional[int] = Field(default=None, foreign_key="user.id")

