import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# 1. Setup the Engine
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 2. The Master Base (All models MUST use this)
Base = declarative_base()


# 3. Simple Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
