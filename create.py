from connections import Base, engine, SessionLocal
from models import User, Customer


Base.metadata.create_all(bind=engine)
print("Tables created successfully!")
