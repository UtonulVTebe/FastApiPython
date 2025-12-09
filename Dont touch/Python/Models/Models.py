import Helper as h
from sqlmodel import Field, SQLModel, create_engine, Session, select, Relationship
from typing import Optional

class User(SQLModel, table = True) :
    id : Optional[int] = Field (default = None, primary_key = True)
    name: str
    role: Optional[str] = Field(default="Student")
    login: str
    password: Optional[str] = None

    grades:  list["Grade"] = Relationship(back_populates = "grade")

class Grade(SQLModel, table = True):
    id: Optional[int] = Field(default = None, primary_key= True)
    URL: str
    status: h.status_Grade = Field(default = h.status_Grade.not_verified)
    grade: int

class UG(SQLModel, table = True):
    grade_id: Optional[int] = Field(default = None, primary_key = True)
    user_id: Optional[int] = Field(default = None, primary_key = True)

class Course(SQLModel, table = True):
    id: Optional[int] = Field(default = None, primary_key = True)
    title: str
    status: h.status_Course = Field(default = h.status_Course.draft)
    URL: str

class UC(SQLModel, table = True):
    user_id: int = Field(foreign_key = "user.id", primary_key = True)
    course_id: int = Field(foreign_key = "course.id", primary_key = True)

file_name = "database.db"
URL =  f"sqlite:///{file_name}"
engine = create_engine(URL)