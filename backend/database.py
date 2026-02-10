import os

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Local development in this repo runs Postgres via docker port-forward on 55432.
# Override with DATABASE_URL when running in other environments (e.g. containers).
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://audit_user:audit_pass@localhost:55432/auditdb",
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
