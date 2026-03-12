from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import datetime
import pytz

db = SQLAlchemy()
TIMEZONE = pytz.timezone('Asia/Jakarta')

class Branch(db.Model):
    __tablename__ = 'branches'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    address = db.Column(db.Text, nullable=True) # Persiapan untuk Geofencing nanti

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.String(20), primary_key=True) 
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False) # OWNER, MANAGER, SPV, STAFF
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'), nullable=True)
    
    branch = db.relationship('Branch', backref='staffs')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Attendance(db.Model):
    __tablename__ = 'attendances'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(20), db.ForeignKey('users.id'), nullable=False)
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'), nullable=True)
    # Gunakan fungsi callable agar dihitung setiap kali baris baru dibuat
    date = db.Column(db.Date, default=lambda: datetime.datetime.now(TIMEZONE).date())
    in_time = db.Column(db.DateTime(timezone=True))
    in_photo = db.Column(db.String(255)) # Menyimpan nama file, String cukup
    out_time = db.Column(db.DateTime(timezone=True))
    out_photo = db.Column(db.String(255))
    
    user = db.relationship('User', backref='history')