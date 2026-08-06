from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from config import settings  # config.pyから設定を読み込む

# URLの直書きをやめて、settings.database_url を使用する
engine = create_async_engine(settings.database_url, echo=True)
SessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()