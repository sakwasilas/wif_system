from werkzeug.security import generate_password_hash
from connections import SessionLocal
from models import User

db = SessionLocal()


admin = db.query(User).filter_by(username="admin").first()

if not admin:
    hashed_pw = generate_password_hash("admin123")
    new_admin = User(username="admin", password=hashed_pw)
    db.add(new_admin)
    db.commit()
    print("✅ Default admin created: username=admin, password=admin123")
else:
    print("ℹ️ Admin already exists in database")

db.close()
