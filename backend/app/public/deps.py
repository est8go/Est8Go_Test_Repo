import os
from fastapi import Header, HTTPException


def require_public_api_key():
    return