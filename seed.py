from app import app, db
from models import Branch, User
from werkzeug.security import generate_password_hash

with app.app_context():
    db.drop_all()
    db.create_all()
    db.session.add_all([Branch(id=1, name="Wine Dental Salatiga"), Branch(id=2, name="Wine Dental Semarang")])
    owner = User(id="W9999", username="owner", password_hash=generate_password_hash("owner123"), full_name="Owner Utama", role="OWNER")
    db.session.add(owner)
    db.session.commit()
    print("Reset Sukses! Login owner / owner123")