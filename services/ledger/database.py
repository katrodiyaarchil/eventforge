from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
import os

def _get_ledger_db_uri(user: str, password: str, host: str = "localhost",
                port: int = 5432, database: str = "eventforge_ledger") -> str:
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"


engine = create_async_engine(
    _get_ledger_db_uri(
        os.getenv("LEDGER_DB_USER", "root"),
        os.getenv("LEDGER_DB_PASSWORD", "password"),
        os.getenv("LEDGER_DB_HOST", "localhost"),
        int(os.getenv("LEDGER_DB_PORT", 5432)),
        os.getenv("LEDGER_DB_NAME", "eventforge_ledger")
    )
)

session_maker = async_sessionmaker(bind=engine, expire_on_commit=False)