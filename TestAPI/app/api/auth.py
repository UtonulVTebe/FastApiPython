from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlmodel import Session, select
from app.database import get_session
from app.models import User
from app.schemas import UserRegister, UserResponse, UserLogin, TokenResponse
from app.core.security import hash_password, verify_password, create_access_token, verify_token

router = APIRouter(prefix="/auth", tags=["auth"])
security = HTTPBearer()


@router.post("/register", response_model=TokenResponse)
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
    
    # Создаем токен для нового пользователя
    access_token = create_access_token(data={"sub": str(new_user.id), "login": new_user.login})
    user_response = UserResponse(id=new_user.id, name=new_user.name, role=new_user.role)
    
    return TokenResponse(access_token=access_token, user=user_response)


@router.post("/login", response_model=TokenResponse)
def login(credentials: UserLogin, session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.login == credentials.login)).first()
    if not user or not user.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль"
        )
    
    if not verify_password(credentials.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль"
        )
    
    if user.id is None:
        raise HTTPException(status_code=500, detail="Ошибка данных пользователя")
    
    # Создаем токен
    access_token = create_access_token(data={"sub": str(user.id), "login": user.login})
    user_response = UserResponse(id=user.id, name=user.name, role=user.role)
    
    return TokenResponse(access_token=access_token, user=user_response)


@router.get("/me", response_model=UserResponse)
def get_current_user_info(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: Session = Depends(get_session)
):
    """Получить информацию о текущем авторизованном пользователе"""
    token = credentials.credentials
    payload = verify_token(token)
    user_id = int(payload.get("sub"))
    
    user = session.get(User, user_id)
    if not user or user.id is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    return UserResponse(id=user.id, name=user.name, role=user.role)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: Session = Depends(get_session)
) -> User:
    """Dependency для получения текущего пользователя из токена"""
    token = credentials.credentials
    payload = verify_token(token)
    user_id = int(payload.get("sub"))
    
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )
    
    return user

