from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os # Import os

# Read the database URL from environment variable, with a fallback for local dev
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./oracle.db")

engine = create_engine(DATABASE_URL)
# The 'connect_args' is for SQLite only, remove it for production
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()