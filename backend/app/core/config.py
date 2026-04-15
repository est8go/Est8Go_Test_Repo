import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    APP_NAME: str = os.getenv("APP_NAME", "Multi-Tenant AI Platform")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./app.db")

    JWT_SECRET: str = os.getenv("JWT_SECRET", "change-me-to-a-long-random-secret")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")

    # ✅ ADD THIS LINE (THIS IS YOUR FIX)
    PUBLIC_API_KEY: str = os.getenv("PUBLIC_API_KEY", "")


settings = Settings()