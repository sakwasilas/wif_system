from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session, declarative_base

# ✅ New database URL
DATABASE_URL = "postgresql://wifi_system_zpes_user:YR5eOiEeYHWC3ZqEPWuMSWhDU8mP5nr7@dpg-d3jk97p5pdvs73egi8dg-a.oregon-postgres.render.com:5432/wifi_system_zpes?sslmode=require"

engine = create_engine(DATABASE_URL)

Session = scoped_session(sessionmaker(bind=engine))
SessionLocal = Session

Base = declarative_base()
