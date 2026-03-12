from app import app, db
from models import Branch, User
from werkzeug.security import generate_password_hash

with app.app_context():
    db.drop_all()
    db.create_all()
    
    # Sesuaikan dengan lokasi sebenarnya yang Anda sebutkan
    b1 = Branch(id=1, name="Wine Dental Daan Mogot", address="Ruko Daan Mogot Baru, Jl. Tampak Siring No.5")
    db.session.add(b1)
    
    # Akun Super Admin
    owner = User(
        id="OWN001", 
        username="owner", 
        full_name="Cia", # Menyesuaikan data otoritas tertinggi
        role="OWNER"
    )
    owner.set_password("owner123")
    
    db.session.add(owner)
    db.session.commit()
    
    print("========================================")
    print("Database Reset Sukses!")
    print("Cabang Terdaftar: Daan Mogot Baru")
    print("Login Akses: owner / owner123")
    print("========================================")