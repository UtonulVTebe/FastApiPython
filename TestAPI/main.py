from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.database import create_db_and_tables
from app.api import auth, profile, courses, submissions, enrollment

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

# Разрешаем запросы с фронта (Vue по умолчанию на 8080)
origins = [
    "http://localhost:8080",
    "http://127.0.0.1:8080",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(courses.router)
app.include_router(submissions.router)
app.include_router(enrollment.router)

app.mount("/content", StaticFiles(directory="content"), name="content")


@app.get("/")
async def root():
    return {"message": "TestAPI is running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
