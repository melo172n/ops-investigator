from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def asynchronous_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql://"):
        return database_url.replace(
            "postgresql://",
            "postgresql+asyncpg://",
            1,
        )
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    return database_url


class Database:
    def __init__(self, database_url: str) -> None:
        self.engine: AsyncEngine = create_async_engine(
            asynchronous_database_url(database_url),
            pool_pre_ping=True,
        )
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def dispose(self) -> None:
        await self.engine.dispose()
