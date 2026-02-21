from connections import SessionLocal
from models import User

db = SessionLocal()

admin = db.query(User).filter_by(username="admin").first()

if not admin:
    new_admin = User(
        username="admin",
        password="simlaw",      
        role="super_admin",
        is_active=True
    )
    db.add(new_admin)
    db.commit()
    print("✅ Default admin created: username=admin, password=simlaw")
else:
    print("ℹ️ Admin already exists in database")

db.close()