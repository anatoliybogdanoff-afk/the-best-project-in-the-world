
import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

# Если DATABASE_URL задан в окружении — используем его.
# Иначе подключаемся к БД на компьютере через порт 5434.
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://spy:spy@localhost:5434/spy_flights",
)

engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()


def get_db():
    """Выдаёт сессию БД для запроса и закрывает её после использования."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connection() -> bool:
    """Проверяет, отвечает ли база данных."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
