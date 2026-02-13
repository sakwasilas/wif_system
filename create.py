from connections import Base, engine
from models import *

# ⚠️ Drops all existing tables and recreates them
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

print("Tables recreated with latest columns")