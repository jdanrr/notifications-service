"""Engine y sesiones de SQLAlchemy para notification_log."""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def build_engine(database_url: str):
    # pool_pre_ping evita sesiones muertas si Postgres se reinicia.
    return create_engine(database_url, pool_pre_ping=True)


def build_session_factory(engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)
