from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# 🔴 FORCE model registration (VERY IMPORTANT)
import app.tenants.models  # noqa
import app.company_profiles.models  # noqa