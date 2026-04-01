from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession
import os

def _get_db_uri(user: str, password: str, host: str = "localhost", 
                port: int = 5432, database: str = "eventforge_gateway") -> str:
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"

engine = create_async_engine(
    _get_db_uri(
        os.getenv("GATEWAY_DB_USER", "root"),
        os.getenv("GATEWAY_DB_PASSWORD", "password"),
        os.getenv("GATEWAY_DB_HOST", "localhost"),
        int(os.getenv("GATEWAY_DB_PORT", 5432)),
        os.getenv("GATEWAY_DB_NAME", "eventforge_gateway")
    )
)

session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def _get_db() -> AsyncGenerator[AsyncSession, None]:
    async with session_factory() as session:
        yield session
        