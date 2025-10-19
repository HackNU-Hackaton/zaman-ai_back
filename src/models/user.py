from sqlalchemy import Table, Column, Integer, String, Float, Boolean, DateTime
from src.utils.db import metadata

users_table = Table(
    "users",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("username", String, nullable=False),
    Column("hashed_password", String),
    Column("email", String),
    Column('type_id', Integer),
    Column("is_active", Boolean),
    Column("created_at", DateTime),
    Column('thread_id', String, unique=True),
    Column('transactions_file_id', String, unique=True),
)