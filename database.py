from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import load_config

config = load_config("config.yaml")

SQLALCHEMY_DATABASE_URL = config["DATABASE_URL"]

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
