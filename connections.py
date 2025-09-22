# from sqlalchemy import create_engine
# from sqlalchemy.orm import sessionmaker, scoped_session, declarative_base


# DATABASE_URL = "mysql+mysqldb://root:2480@/client"

# engine = create_engine(DATABASE_URL, pool_pre_ping=True)


# SessionLocal = scoped_session(sessionmaker(bind=engine, autoflush=False, autocommit=False))


# Base = declarative_base()

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session, declarative_base

# Updated database URL
DATABASE_URL = "postgresql://wifi_z5hr_user:oXaTrfZR9jZECSnwVCoRSEsof7SuIvTC@dpg-d38mg2odl3ps73a43ge0-a.oregon-postgres.render.com:5432/wifi_z5hr?sslmode=require"

engine = create_engine(DATABASE_URL)

Session = scoped_session(sessionmaker(bind=engine))
SessionLocal = Session

Base = declarative_base()

