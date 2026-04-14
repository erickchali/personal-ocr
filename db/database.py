import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://{user}:{password}@{host}:{port}/{db}".format(
        user=os.getenv("POSTGRES_USER", "financial_assistant"),
        password=os.getenv("POSTGRES_PASSWORD", "financial_assistant_pw"),
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_HOST_PORT", "5432"),
        db=os.getenv("POSTGRES_DB", "financial_assistant"),
    ),
)

DATABASE_READ_URL = os.getenv(
    "DATABASE_READ_URL",
    "postgresql://{user}:{password}@{host}:{port}/{db}".format(
        user="query_reader",
        password="query_reader_pw",
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_HOST_PORT", "5432"),
        db=os.getenv("POSTGRES_DB", "financial_assistant"),
    ),
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
