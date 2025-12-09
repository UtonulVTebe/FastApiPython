from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from app.database import create_db_and_tables
from app.api import auth, profile, courses

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield

app = FastAPI(
    title="TestAPI",
    description="API для управления пользователями, курсами и оценками",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(courses.router)

app.mount("/content", StaticFiles(directory="content"), name="content")


@app.get("/")
async def root():
    return {"message": "TestAPI is running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
