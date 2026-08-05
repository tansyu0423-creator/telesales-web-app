from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base

# PostgreSQLの非同期接続URL
SQLALCHEMY_DATABASE_URL = "postgresql+asyncpg://user:password@localhost:5432/telesales_db"

engine = create_async_engine(SQLALCHEMY_DATABASE_URL, echo=True)
SessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()