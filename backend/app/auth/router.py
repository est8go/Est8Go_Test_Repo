from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.db import SessionLocal
from app.services.auth_service import login_user
from app.auth.schemas import LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["Auth"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/login", response_model=TokenResponse)
def login(
    data: LoginRequest,
    db: Session = Depends(get_db),
):
    return login_user(data.email, data.password, db)