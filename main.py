import uvicorn
from fastapi import FastAPI

from starlette.middleware.cors import CORSMiddleware

from src.endpoints import list_of_routes
from sqlalchemy import create_engine
from src.utils.db import database, metadata, DATABASE_URL
from contextlib import asynccontextmanager

def bind_routes(application: FastAPI) -> None:
    for route in list_of_routes:
        application.include_router(route, prefix='/api/v1')


@asynccontextmanager
async def lifespan(app: FastAPI):
    from src.models.products import products_table
    from src.models.user import users_table

    engine = create_engine(DATABASE_URL.replace("+aiosqlite", ""), connect_args={"check_same_thread": False})

    # Логика при старте приложения: устанавливаем соединение с БД
    metadata.create_all(bind=engine)
    await database.connect()
    yield
    # Логика при завершении работы приложения: разрываем соединение с БД
    await database.disconnect()
app = FastAPI(lifespan=lifespan)

origins = []

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

bind_routes(app)

# IGNORED_PATHS = [
#     "/docs",
#     "/redoc",
#     "/openapi.json",
#     "/health",
#     "/metrics",
# ]


if __name__ == "__main__":
    # uvicorn.run("main:app", host="0.0.0.0", port=9000, reload=True)
    uvicorn.run("main:app", host="0.0.0.0", port=8000, workers=1, reload=True)