from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from app.database import get_session
from app.models import User
from app.schemas import UserRegister, UserResponse
from app.core.security import hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse)
def register(user_data: UserRegister, session: Session = Depends(get_session)):
    existing_user = session.exec(select(User).where(User.login == user_data.login)).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Пользователь с таким логином уже существует")
    
    hashed_password = hash_password(user_data.password)
    new_user = User(
        login=user_data.login,
        password=hashed_password,
        name=user_data.name
    )
    session.add(new_user)
    session.commit()
    session.refresh(new_user)
    
    if new_user.id is None:
        raise HTTPException(status_code=500, detail="Ошибка при создании пользователя")
    
    return UserResponse(id=new_user.id, name=new_user.name, role=new_user.role)


@router.get("/login", response_model=UserResponse)
def login(login: str = Query(...), password: str = Query(...), session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.login == login)).first()
    if not user or not user.password:
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")
    
    if not verify_password(password, user.password):
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")
    
    if user.id is None:
        raise HTTPException(status_code=500, detail="Ошибка данных пользователя")
    
    return UserResponse(id=user.id, name=user.name, role=user.role)

