from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select, func, insert

from src.utils.db import database
from src.models.user import users_table
from src.schemas.users import UserOut, UserCreate,Token
from src.utils.security import (
    get_password_hash, verify_password,
    create_access_token, get_current_user
)

router = APIRouter(
    tags=["auth"],
    responses={404: {"description": "Not found"}},
)



@router.post("/register", response_model=UserOut, status_code=201)
async def register(user_in: UserCreate):
    q = select(users_table).where(func.lower(users_table.c.username) == user_in.username.lower())
    if user_in.email:
        q = q.union_all(select(users_table).where(func.lower(users_table.c.email) == user_in.email.lower()))
    existing = await database.fetch_one(q)
    if existing:
        raise HTTPException(status_code=400, detail="Username или Email уже существует")

    ins = insert(users_table).values(
        username=user_in.username,
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        is_active=True,
        created_at=datetime.utcnow(),
    )
    new_id = await database.execute(ins)
    row = await database.fetch_one(select(users_table).where(users_table.c.id == new_id))
    return UserOut(**dict(row))

@router.post("/token", response_model=Token)
async def login(username: str, password: str):
    candidate = username
    q = select(users_table).where(
        (func.lower(users_table.c.username) == candidate.lower()) |
        (func.lower(users_table.c.email) == candidate.lower())
    )
    user = await database.fetch_one(q)
    if not user or not verify_password(password, user["hashed_password"]):
        raise HTTPException(status_code=400, detail="Неверный логин или пароль. Попробуйте еще раз")

    token = create_access_token({"sub": user["username"]})
    return {"access_token": token, "token_type": "bearer", "id": user["id"], "username": user["username"], "email": user["email"], "type_id" : user["type_id"]}

@router.get("/me", response_model=UserOut)
async def read_me(current_user: dict = Depends(get_current_user)):
    return UserOut(**current_user)
