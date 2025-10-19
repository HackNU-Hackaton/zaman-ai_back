from src.endpoints.chat import router as chat_router
from src.endpoints.utils import router as utils_router
from src.endpoints.transactions import router as transactions_router
from src.endpoints.transactions_SME import router as transactions_SME_router
from src.endpoints.auth import router as auth_router

list_of_routes = [
    auth_router,
    chat_router,
    transactions_router,
    transactions_SME_router,
    utils_router,
]

__all__ = [
    'list_of_routes',
]
