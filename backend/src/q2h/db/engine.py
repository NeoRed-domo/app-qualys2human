from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from q2h.config import get_settings


def get_database_url() -> str:
    s = get_settings().database
    return f"postgresql+asyncpg://{s.user}:{s.password}@{s.host}:{s.port}/{s.name}"


engine = None
SessionLocal = None


def init_engine():
    global engine, SessionLocal
    engine = create_async_engine(get_database_url(), pool_size=20, max_overflow=10)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def dispose_engine():
    global engine, SessionLocal
    if engine is not None:
        await engine.dispose()
        engine = None
        SessionLocal = None


async def get_db():
    if SessionLocal is None:
        init_engine()
    async with SessionLocal() as session:
        yield session
