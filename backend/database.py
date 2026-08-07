from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool
try:
    from .config import settings
except ImportError:
    from config import settings

# URLの直書きをやめて、settings.database_url を使用する
engine = create_async_engine(settings.database_url, echo=True, poolclass=NullPool)
SessionLocal = async_sessionmaker(autoflush=False, bind=engine, expire_on_commit=False)

Base = declarative_base()