import asyncio
from fastapi import APIRouter, Request, Depends
from sqlalchemy import select
from src.models.products import products_table
from src.utils.db import database


router = APIRouter(
    tags=["utils"],
    responses={404: {"description": "Not found"}},
)

@router.get("/load/products")
async def seed_default_data():
    """
    Seeds default data into the database if it's empty.
    """
    query = select(products_table.c.id)
    rows = await database.fetch_all(query)

    if rows:  # Already seeded
        print("✅ Default data already exists, skipping seeding.")
        return

    default_products = [
        {"name": "Premium Cashback Card", "category": "Credit Card", "description": "3% cashback on groceries."},
        {"name": "Student Debit Card", "category": "Debit Card", "description": "No maintenance fee for students."},
        {"name": "Travel Rewards Card", "category": "Credit Card", "description": "Earn miles for every purchase."},
    ]

    insert_query = products_table.insert().values(default_products)
    await database.execute(insert_query)