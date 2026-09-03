from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import settings

DATABASE_URL = settings.DATABASE_URL
DATABASE_READ_URL = settings.DATABASE_READ_URL

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
