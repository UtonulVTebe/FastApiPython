from sqlmodel import SQLModel, create_engine, Session
from typing import Generator
from app import models

DATABASE_URL = "sqlite:///./testapi.db"

engine = create_engine(DATABASE_URL, echo=True)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session

