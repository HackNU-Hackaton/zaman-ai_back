from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    username: str
    email: Optional[EmailStr] = None
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    email: Optional[EmailStr] = None
    is_active: bool
    created_at: datetime


class Token(BaseModel):
    id: int
    access_token: str
    token_type: str = "bearer"
    username: str
    email: str
    type_id: int

