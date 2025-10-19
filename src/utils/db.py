from databases import Database
from sqlalchemy import MetaData

DATABASE_URL = "sqlite+aiosqlite:///./bank_assistant.db"

database = Database(DATABASE_URL)
metadata = MetaData()

from src import models