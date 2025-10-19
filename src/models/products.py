from sqlalchemy import Table, Column, Integer, String, Float, MetaData
from src.utils.db import metadata

products_table = Table(
    "products",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String, nullable=False),
    Column("category", String),
    Column("description", String),
)