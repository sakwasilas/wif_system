# from sqlalchemy import create_engine
# from sqlalchemy.orm import sessionmaker, scoped_session, declarative_base


# DATABASE_URL = "mysql+mysqldb://root:2480@/client"

# engine = create_engine(DATABASE_URL, pool_pre_ping=True)


# SessionLocal = scoped_session(sessionmaker(bind=engine, autoflush=False, autocommit=False))

# Base = declarative_base()

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session, declarative_base

# ✅ New database URL
DATABASE_URL = "postgresql://wifi_afq5_user:yPDLc4g2zYSCpC9eOYRpCpyEk1szFbmU@dpg-d3a0so95pdvs73e10m5g-a.oregon-postgres.render.com:5432/wifi_afq5?sslmode=require"

engine = create_engine(DATABASE_URL)

Session = scoped_session(sessionmaker(bind=engine))
SessionLocal = Session

Base = declarative_base()

