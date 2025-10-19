from sqlalchemy import Table, Column, Integer, String, Float, Boolean, DateTime, ForeignKey
from src.utils.db import metadata
from src.models.user import users_table

chat_messages_table = Table(
    "chat_messages",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("role", String, nullable=False),
    Column("message", String),
    Column("is_active", Boolean),
    Column("created_at", DateTime),
    Column("user_id", Integer, ForeignKey("users.id"), nullable=False),
)