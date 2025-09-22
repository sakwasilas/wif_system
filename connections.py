from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session, declarative_base


DATABASE_URL = "mysql+mysqldb://root:2480@/client"

engine = create_engine(DATABASE_URL, pool_pre_ping=True)


SessionLocal = scoped_session(sessionmaker(bind=engine, autoflush=False, autocommit=False))


Base = declarative_base()
