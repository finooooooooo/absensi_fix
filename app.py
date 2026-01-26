import os, datetime, base64, pytz
from flask import Flask, render_template, request, session, jsonify, redirect, url_for
from models import db, User, Attendance, Branch, TIMEZONE

app = Flask(__name__)
app.secret_key = 'WDA_PROFESSIONAL_KEY'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///wine_dental.db'
app.config['UPLOAD_FOLDER'] = 'static/uploads/presensi'

db.init_app(app)

def get_next_id(branch_id):
    prefix = f"W{branch_id if branch_id else 0}"
    count = User.query.filter(User.id.like(f"{prefix}%")).count() + 1
    return f"{prefix}{count:03d}"

@app.route('/')
def dashboard():
    if 'uid' not in session: return redirect(url_for('login'))
    user = User.query.get(session['uid'])
    if not user: 
        session.clear()
        return redirect(url_for('login'))

    today = datetime.datetime.now(TIMEZONE).date()
    # Live Feed Monitoring (Untuk Owner/Manager/SPV)
    if user.role in ['OWNER', 'MANAGER']:
        team_attendance = Attendance.query.filter_by(date=today).order_by(Attendance.in_time.desc()).all()
        staff_list = User.query.filter(User.role != 'OWNER').all()
    elif user.role == 'SPV':
        team_attendance = Attendance.query.filter_by(date=today, branch_id=user.branch_id).all()
        staff_list = User.query.filter_by(branch_id=user.branch_id, role='STAFF').all()
    else:
        team_attendance, staff_list = [], []

    att = Attendance.query.filter_by(user_id=user.id, date=today).first()
    return render_template('dashboard.html', user=user, att=att, team_attendance=team_attendance, staff_list=staff_list, branches=Branch.query.all(), now_date=today.strftime('%d %b %Y'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = User.query.filter_by(username=request.form['username']).first()
        if u and u.check_password(request.form['password']):
            session.update({'uid': u.id, 'role': u.role, 'branch': u.branch_id})
            return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/api/create_user', methods=['POST'])
def create_user():
    if session.get('role') not in ['OWNER', 'MANAGER', 'SPV']: return "Unauthorized", 403
    bid = request.form.get('branch_id')
    role = request.form['role']
    if role == 'MANAGER': bid = None
    u = User(id=get_next_id(bid), username=request.form['username'], full_name=request.form['full_name'], role=role, branch_id=bid)
    u.set_password(request.form['password'])
    db.session.add(u)
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/api/absen', methods=['POST'])
def handle_absensi():
    data, uid = request.json, session['uid']
    user, now = User.query.get(uid), datetime.datetime.now(TIMEZONE)
    try:
        header, encoded = data['photo'].split(",", 1)
        img_data = base64.b64decode(encoded)
        fname = f"{uid}_{now.strftime('%Y%m%d_%H%M%S')}.jpg"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], fname)
        with open(filepath, "wb") as f: f.write(img_data)
    except: return jsonify({"error": "Gagal proses foto"}), 400

    att = Attendance.query.filter_by(user_id=uid, date=now.date()).first()
    if not att:
        db.session.add(Attendance(user_id=uid, branch_id=user.branch_id, in_time=now, in_photo=fname))
        msg = "Clock In Berhasil!"
    elif not att.out_time:
        att.out_time, att.out_photo = now, fname
        msg = "Clock Out Berhasil!"
    else:
        return jsonify({"error": "Sudah absen hari ini"}), 400
    
    db.session.commit()
    return jsonify({"success": True, "message": msg})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']): os.makedirs(app.config['UPLOAD_FOLDER'])
    with app.app_context(): db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)