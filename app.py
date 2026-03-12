import os, datetime, base64
import pandas as pd
from io import BytesIO
from flask import Flask, render_template, request, session, jsonify, redirect, url_for, flash, send_file
from models import db, User, Attendance, Branch, TIMEZONE
from sqlalchemy.exc import IntegrityError

app = Flask(__name__)
app.secret_key = 'WINE_DENTAL_PRODUCTION_KEY_2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///wine_dental.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

UPLOAD_FOLDER = os.path.join('static', 'uploads', 'presensi')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

db.init_app(app)

# --- UTILITY FUNCTION ---
def generate_custom_id(role, branch_id):
    """Membuat ID unik berdasarkan role dan cabang."""
    prefix = ""
    if role == 'OWNER': prefix = "OWN"
    elif role == 'MANAGER': prefix = "MGR"
    elif role == 'SPV': prefix = f"SPV{branch_id}"
    else: prefix = f"STF{branch_id}"
    
    count = User.query.filter(User.id.like(f"{prefix}%")).count() + 1
    return f"{prefix}{count:03d}"

# --- ROUTES ---
@app.route('/')
def dashboard():
    if 'uid' not in session: return redirect(url_for('login'))
    
    user = User.query.get(session['uid'])
    if not user:
        session.clear()
        return redirect(url_for('login'))
    
    today = datetime.datetime.now(TIMEZONE).date()
    att = Attendance.query.filter_by(user_id=user.id, date=today).first()
    
    # Logic Pemantauan Berdasarkan Role HIERARKI KETAT
    if user.role == 'OWNER':
        team_attendance = Attendance.query.filter_by(date=today).order_by(Attendance.in_time.desc()).all()
        staff_list = User.query.filter(User.role != 'OWNER').all()
    elif user.role == 'MANAGER':
        team_attendance = Attendance.query.join(User).filter(Attendance.date == today, User.role.in_(['SPV', 'STAFF'])).order_by(Attendance.in_time.desc()).all()
        staff_list = User.query.filter(User.role.in_(['SPV', 'STAFF'])).all()
    elif user.role == 'SPV':
        team_attendance = Attendance.query.join(User).filter(Attendance.date == today, User.branch_id == user.branch_id, User.role == 'STAFF').order_by(Attendance.in_time.desc()).all()
        staff_list = User.query.filter_by(branch_id=user.branch_id, role='STAFF').all()
    else:
        team_attendance, staff_list = [], []

    return render_template('dashboard.html', 
                           user=user, 
                           att=att, 
                           team_attendance=team_attendance, 
                           staff_list=staff_list, 
                           branches=Branch.query.all(), 
                           now_date=today.strftime('%d %B %Y'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'uid' in session: return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        u = User.query.filter_by(username=username).first()
        if u and u.check_password(password):
            session.update({'uid': u.id, 'role': u.role, 'branch': u.branch_id})
            return redirect(url_for('dashboard'))
        else:
            flash('Username atau Password salah!', 'danger')
            
    return render_template('login.html')

@app.route('/api/absen', methods=['POST'])
def handle_absensi():
    if 'uid' not in session: return jsonify({"success": False, "error": "Unauthorized"}), 401
    
    data = request.json
    uid = session.get('uid')
    user = User.query.get(uid)
    now = datetime.datetime.now(TIMEZONE)
    
    if not data or 'photo' not in data:
        return jsonify({"success": False, "error": "Data foto tidak ditemukan."}), 400

    try:
        header, encoded = data['photo'].split(",", 1)
        img_data = base64.b64decode(encoded)
        filename = f"{uid}_{now.strftime('%Y%m%d_%H%M%S')}.jpg"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        with open(filepath, "wb") as f:
            f.write(img_data)
    except Exception as e:
        return jsonify({"success": False, "error": f"Gagal memproses foto: {str(e)}"}), 500

    att = Attendance.query.filter_by(user_id=uid, date=now.date()).first()
    
    if not att:
        new_att = Attendance(user_id=uid, branch_id=user.branch_id, in_time=now, in_photo=filename)
        db.session.add(new_att)
        msg = "Clock In Berhasil!"
    elif not att.out_time:
        att.out_time = now
        att.out_photo = filename
        msg = "Clock Out Berhasil!"
    else:
        return jsonify({"success": False, "error": "Anda sudah menyelesaikan shift hari ini."}), 400
        
    db.session.commit()
    return jsonify({"success": True, "message": msg})

@app.route('/api/create_user', methods=['POST'])
def create_user():
    if session.get('role') not in ['OWNER', 'MANAGER', 'SPV']: 
        return "Unauthorized", 403
        
    role = request.form.get('role')
    bid = request.form.get('branch_id')
    
    if role == 'MANAGER': bid = None
        
    new_id = generate_custom_id(role, bid)
    
    try:
        u = User(id=new_id, username=request.form['username'], full_name=request.form['full_name'], role=role, branch_id=bid)
        u.set_password(request.form['password'])
        db.session.add(u)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        
    return redirect(url_for('dashboard'))

@app.route('/api/kick_user/<user_id>', methods=['POST'])
def kick_user(user_id):
    kicker = User.query.get(session.get('uid'))
    target = User.query.get(user_id)
    
    if not target or not kicker:
        return jsonify({"success": False, "error": "Data tidak valid"}), 400

    if kicker.role == 'SPV':
        return jsonify({"success": False, "error": "SPV tidak berhak menghapus akun."}), 403
    if kicker.role == 'MANAGER' and target.role in ['OWNER', 'MANAGER']:
        return jsonify({"success": False, "error": "Manager hanya bisa menghapus SPV dan Staff."}), 403

    try:
        Attendance.query.filter_by(user_id=target.id).delete()
        db.session.delete(target)
        db.session.commit()
        return jsonify({"success": True, "message": f"Akun {target.full_name} berhasil dihapus permanen."})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": "Gagal menghapus data."}), 500

@app.route('/api/end_shift_all', methods=['POST'])
def end_shift_all():
    user = User.query.get(session.get('uid'))
    if user.role not in ['OWNER', 'MANAGER', 'SPV']:
        return jsonify({"success": False, "error": "Akses Ditolak"}), 403

    now = datetime.datetime.now(TIMEZONE)
    today = now.date()
    
    query = Attendance.query.join(User).filter(Attendance.date == today, Attendance.out_time == None)
    
    if user.role == 'MANAGER':
        query = query.filter(User.role.in_(['SPV', 'STAFF']))
    elif user.role == 'SPV':
        query = query.filter(User.branch_id == user.branch_id, User.role == 'STAFF')
        
    pending_absences = query.all()
    
    count = 0
    for att in pending_absences:
        att.out_time = now
        att.out_photo = "system_auto_closed" 
        count += 1
        
    db.session.commit()
    return jsonify({"success": True, "message": f"{count} shift karyawan berhasil diakhiri secara paksa."})

@app.route('/api/export_excel')
def export_excel():
    user = User.query.get(session.get('uid'))
    if user.role not in ['OWNER', 'MANAGER', 'SPV']: return "Akses Ditolak", 403

    current_month = datetime.datetime.now(TIMEZONE).month
    query = db.session.query(
        User.id, User.full_name, User.role, Branch.name.label('branch_name'),
        Attendance.date, Attendance.in_time, Attendance.out_time
    ).join(Attendance, User.id == Attendance.user_id)\
     .outerjoin(Branch, User.branch_id == Branch.id)\
     .filter(db.extract('month', Attendance.date) == current_month)

    if user.role == 'MANAGER':
        query = query.filter(User.role.in_(['SPV', 'STAFF']))
    elif user.role == 'SPV':
        query = query.filter(User.branch_id == user.branch_id, User.role == 'STAFF')

    records = query.all()
    
    if not records:
        flash('Tidak ada data absensi untuk diekspor bulan ini.', 'warning')
        return redirect(url_for('dashboard'))

    data = []
    for r in records:
        in_str = r.in_time.strftime('%H:%M:%S') if r.in_time else "Tidak Absen"
        out_str = r.out_time.strftime('%H:%M:%S') if r.out_time else "Belum Selesai"
        
        data.append({
            "ID Karyawan": r.id, "Nama Lengkap": r.full_name, "Jabatan": r.role,
            "Cabang": r.branch_name or 'Pusat', "Tanggal": r.date.strftime('%Y-%m-%d'),
            "Jam Masuk": in_str, "Jam Keluar": out_str
        })

    df = pd.DataFrame(data)
    output = BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Laporan Absensi')
    
    output.seek(0)
    filename = f"Laporan_Absensi_WineDental_{datetime.datetime.now(TIMEZONE).strftime('%b_%Y')}.xlsx"
    
    return send_file(output, download_name=filename, as_attachment=True)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)