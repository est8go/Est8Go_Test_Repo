import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    APP_NAME: str = os.getenv("APP_NAME", "Multi-Tenant AI Platform")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./app.db")

    # JWT_SECRET / JWT_ALGORITHM removed — they were a second, divergent
    # copy of the signing config. Tokens are issued by app.core.security
    # with SECRET_KEY; anything verifying a token imports SECRET_KEY /
    # ALGORITHM from there so there is exactly one signing key.

    PUBLIC_API_KEY: str = os.getenv("PUBLIC_API_KEY", "")


settings = Settings()