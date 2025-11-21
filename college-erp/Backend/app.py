from flask import Flask, request, jsonify, send_from_directory, abort, send_file
from flask_cors import CORS
import mysql.connector
from passlib.hash import bcrypt
from werkzeug.utils import secure_filename
import os
import logging
from pathlib import Path
import time
import subprocess, json

app = Flask(__name__, static_folder="../Frontend", static_url_path="/")
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'Frontend', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def get_db():
    try:
        conn = mysql.connector.connect(
            host="127.0.0.1", user="root", password="", database="college_erp"
        )
        return conn
    except mysql.connector.Error as e:
        logger.error(f"Database connection failed: {e}")
        raise

# Detect if students table has auth columns (username, password_hash)
_STUDENTS_HAS_AUTH_COLS = None
def students_has_auth_cols() -> bool:
    global _STUDENTS_HAS_AUTH_COLS
    if _STUDENTS_HAS_AUTH_COLS is not None:
        return _STUDENTS_HAS_AUTH_COLS
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("""
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'students'
        """)
        cols = {row[0] for row in cur.fetchall()}
        _STUDENTS_HAS_AUTH_COLS = {'username', 'password_hash'}.issubset(cols)
        cur.close(); conn.close()
    except Exception as e:
        logger.warning(f"Failed to inspect students columns: {e}")
        _STUDENTS_HAS_AUTH_COLS = False
    return _STUDENTS_HAS_AUTH_COLS

_NOTIFICATIONS_HAS_SENDER_COL = None
def notifications_has_sender_col() -> bool:
    global _NOTIFICATIONS_HAS_SENDER_COL
    if _NOTIFICATIONS_HAS_SENDER_COL is not None:
        return _NOTIFICATIONS_HAS_SENDER_COL
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("""
          SELECT COLUMN_NAME
          FROM INFORMATION_SCHEMA.COLUMNS
          WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME='notifications'
        """)
        cols = {r[0] for r in cur.fetchall()}
        _NOTIFICATIONS_HAS_SENDER_COL = 'sender_user_id' in cols
        cur.close(); conn.close()
    except Exception as e:
        logger.warning(f"Inspect notifications cols failed: {e}")
        _NOTIFICATIONS_HAS_SENDER_COL = False
    return _NOTIFICATIONS_HAS_SENDER_COL

_NOTIFICATIONS_HAS_TARGET_USER_COL = None
def notifications_has_target_user_col() -> bool:
    global _NOTIFICATIONS_HAS_TARGET_USER_COL
    if _NOTIFICATIONS_HAS_TARGET_USER_COL is not None:
        return _NOTIFICATIONS_HAS_TARGET_USER_COL
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("""
          SELECT COLUMN_NAME
          FROM INFORMATION_SCHEMA.COLUMNS
          WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME='notifications'
        """)
        cols = {r[0] for r in cur.fetchall()}
        _NOTIFICATIONS_HAS_TARGET_USER_COL = 'target_user_id' in cols
        cur.close(); conn.close()
    except Exception as e:
        logger.warning(f"Inspect notifications target col failed: {e}")
        _NOTIFICATIONS_HAS_TARGET_USER_COL = False
    return _NOTIFICATIONS_HAS_TARGET_USER_COL

# ============ AUTHENTICATION ============
@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.json
        if not data or not data.get('username') or not data.get('password'):
            return jsonify({"error": "Username and password required"}), 400
        
        username = data.get('username')
        password = data.get('password')
        conn = get_db()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM users WHERE username=%s", (username,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        if not user:
            logger.warning(f"Login attempt with invalid username: {username}")
            return jsonify({"error": "Invalid credentials"}), 401
        stored = user['password_hash']
        if bcrypt.verify(password, stored):
            user.pop('password_hash', None)
            logger.info(f"User {username} logged in successfully")
            return jsonify({"success": True, "user": user})
        logger.warning(f"Login attempt with invalid password for username: {username}")
        return jsonify({"error": "Invalid credentials"}), 401
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({"error": "Internal server error"}), 500

ADMIN_USERNAME = "admin"
ADMIN_EMAIL = "admin@college.edu"
ADMIN_PASSWORD_PLAIN = "admin123"

def ensure_default_admin():
    try:
        conn = get_db()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT id, password_hash FROM users WHERE username=%s AND role='admin'", (ADMIN_USERNAME,))
        row = cur.fetchone()
        needs_update = False
        if not row:
            needs_update = True
        else:
            ph = row['password_hash'] or ''
            if not (ph.startswith('$2') and len(ph) >= 60):
                needs_update = True
        if needs_update:
            pw_hash = bcrypt.hash(ADMIN_PASSWORD_PLAIN)
            if row:
                cur.execute("UPDATE users SET password_hash=%s, full_name=%s, email=%s WHERE id=%s",
                            (pw_hash, "System Administrator", ADMIN_EMAIL, row['id']))
                logger.info("Admin password repaired")
            else:
                cur.execute(
                    "INSERT INTO users (username, password_hash, role, full_name, email) VALUES (%s,%s,%s,%s,%s)",
                    (ADMIN_USERNAME, pw_hash, "admin", "System Administrator", ADMIN_EMAIL)
                )
                logger.info("Default admin user created")
            conn.commit()
        cur.close(); conn.close()
    except Exception as e:
        logger.error(f"Failed ensuring default admin: {e}")

# Seed immediately (module import) so even first request works.
ensure_default_admin()

def ensure_notifications_schema():
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("SHOW TABLES LIKE 'notifications'")
        if not cur.fetchall():
            cur.close(); conn.close()
            logger.warning("notifications table missing; skip migration")
            return
        cur.execute("SHOW COLUMNS FROM notifications")
        cols = {r[0] for r in cur.fetchall()}
        # sender_user_id
        if 'sender_user_id' not in cols:
            logger.info("Adding sender_user_id to notifications")
            cur.execute("ALTER TABLE notifications ADD COLUMN sender_user_id INT NULL")
            cur.execute("""ALTER TABLE notifications
                           ADD CONSTRAINT fk_notifications_sender
                           FOREIGN KEY (sender_user_id) REFERENCES users(id) ON DELETE SET NULL""")
        # target_user_id
        if 'target_user_id' not in cols:
            logger.info("Adding target_user_id to notifications")
            cur.execute("ALTER TABLE notifications ADD COLUMN target_user_id INT NULL")
            cur.execute("""ALTER TABLE notifications
                           ADD CONSTRAINT fk_notifications_target
                           FOREIGN KEY (target_user_id) REFERENCES users(id) ON DELETE CASCADE""")
        conn.commit(); cur.close(); conn.close()
    except Exception as e:
        logger.error(f"Notification schema migration failed: {e}")

def ensure_notification_status_table():
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("SHOW TABLES LIKE 'notification_user_status'")
        if not cur.fetchall():
            cur.execute("""
              CREATE TABLE notification_user_status (
                notification_id INT NOT NULL,
                user_id INT NOT NULL,
                deleted_at TIMESTAMP NULL,
                PRIMARY KEY (notification_id, user_id),
                FOREIGN KEY (notification_id) REFERENCES notifications(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
              )
            """)
            conn.commit()
        cur.close(); conn.close()
    except Exception as e:
        logger.error(f"Ensure notification_user_status failed: {e}")

# Seed admin and ensure notification columns
ensure_default_admin()
ensure_notifications_schema()
ensure_notification_status_table()

@app.before_first_request
def _init_system():
    ensure_default_admin()
    ensure_notifications_schema()
    ensure_notification_status_table()

@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    data = request.get_json()
    username = data.get('username'); password = data.get('password')
    if not username or not password:
        return jsonify({'success': False, 'message': 'Username and password required'}), 400
    if username != ADMIN_USERNAME:
        return jsonify({'success': False, 'message': 'Invalid credentials'}), 401
    try:
        conn = get_db(); cur = conn.cursor(dictionary=True)
        cur.execute("SELECT id, password_hash FROM users WHERE username=%s AND role='admin'", (ADMIN_USERNAME,))
        admin = cur.fetchone(); cur.close(); conn.close()
        if not admin:
            # Attempt repair then retry once
            ensure_default_admin()
            conn = get_db(); cur = conn.cursor(dictionary=True)
            cur.execute("SELECT id, password_hash FROM users WHERE username=%s AND role='admin'", (ADMIN_USERNAME,))
            admin = cur.fetchone(); cur.close(); conn.close()
            if not admin:
                return jsonify({'success': False, 'message': 'Admin account missing'}), 500
        try:
            if not bcrypt.verify(password, admin['password_hash']):
                return jsonify({'success': False, 'message': 'Invalid credentials'}), 401
        except Exception:
            ensure_default_admin()
            return jsonify({'success': False, 'message': 'Invalid credentials'}), 401
        token = f"admin_token_{username}_{int(time.time())}"
        return jsonify({'success': True, 'token': token, 'message': 'Login successful'}), 200
    except Exception as e:
        logger.error(f"Admin login error: {e}")
        return jsonify({'success': False, 'message': 'Database error'}), 500

@app.route('/api/staff/login', methods=['POST'])
def staff_login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    if not username or not password:
        return jsonify({'success': False, 'message': 'Username and password required'}), 400
    try:
        conn = get_db(); cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT u.id AS user_id, u.username, u.password_hash, u.full_name AS name, u.email,
                   s.dept AS department, s.designation, s.id AS staff_id
            FROM users u
            JOIN staff s ON s.user_id = u.id
            WHERE u.username=%s AND u.role='staff'
        """, (username,))
        rec = cur.fetchone(); cur.close(); conn.close()
        if not rec:
            logger.warning(f"Staff login invalid username: {username}")
            return jsonify({'success': False, 'message': 'Invalid credentials'}), 401
        if not bcrypt.verify(password, rec['password_hash']):
            logger.warning(f"Staff login invalid password for: {username}")
            return jsonify({'success': False, 'message': 'Invalid credentials'}), 401
        token = f"staff_token_{username}_{int(time.time())}"
        staff_data = {
            'id': rec['user_id'],
            'username': rec['username'],
            'name': rec['name'],
            'email': rec['email'],
            'department': rec['department'],
            'designation': rec['designation'],
            'staff_id': rec['staff_id']
        }
        logger.info(f"Staff {username} logged in")
        return jsonify({'success': True, 'token': token, 'staff': staff_data, 'message': 'Login successful'}), 200
    except Exception as e:
        logger.error(f"Staff login error: {e}")
        return jsonify({'success': False, 'message': 'Database error: ' + str(e)}), 500

@app.route('/api/student/login', methods=['POST'])
def student_login():
    data = request.get_json()
    identifier = data.get('username'); password = data.get('password')
    if not identifier or not password:
        return jsonify({'success': False, 'message': 'Username/Roll and password required'}), 400
    try:
        conn = get_db(); cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT u.id AS user_id, u.username, u.password_hash,
                   s.roll_no, s.course, s.semester,
                   u.full_name, u.email
            FROM users u
            JOIN students s ON s.user_id = u.id
            WHERE u.username=%s OR s.roll_no=%s
            LIMIT 1
        """,(identifier, identifier))
        rec = cur.fetchone(); cur.close(); conn.close()
        if not rec or not bcrypt.verify(password, rec['password_hash']):
            logger.warning(f"Student login failed identifier={identifier}")
            return jsonify({'success': False, 'message': 'Invalid credentials'}), 401
        token = f"student_token_{rec['username']}_{int(time.time())}"
        student_data = {
            'id': rec['user_id'],
            'username': rec['username'],
            'full_name': rec['full_name'],
            'email': rec['email'],
            'roll_no': rec['roll_no'],
            'course': rec['course'],
            'semester': rec['semester']
        }
        logger.info(f"Student {rec['username']} logged in")
        return jsonify({'success': True, 'token': token, 'student': student_data, 'message': 'Login successful'}), 200
    except Exception as e:
        logger.error(f"Student login error: {e}")
        return jsonify({'success': False, 'message': 'Database error'}), 500

@app.route('/api/verify-token', methods=['POST'])
def verify_token():
    data = request.get_json()
    token = data.get('token')
    user_type = data.get('user_type')  # admin, staff, student
    
    if token and token.startswith(f"{user_type}_token_"):
        return jsonify({'valid': True}), 200
    else:
        return jsonify({'valid': False}), 401

# ============ STUDENT ENDPOINTS ============
@app.route('/api/student/<int:user_id>/summary', methods=['GET'])
def student_summary(user_id):
    try:
        conn = get_db()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT id FROM students WHERE user_id=%s", (user_id,))
        s = cur.fetchone()
        if not s:
            cur.close()
            conn.close()
            return jsonify({"error": "Student not found"}), 404
        sid = s['id']
        
        cur.execute("""SELECT COUNT(*) as total, SUM(present=1) as present 
                       FROM attendance WHERE student_id=%s""", (sid,))
        a = cur.fetchone()
        total = a['total'] or 0
        present = a['present'] or 0
        overall = int((present/total)*100) if total > 0 else 0
        
        cur.execute("SELECT AVG(marks) as avg_marks FROM grades WHERE student_id=%s", (sid,))
        gm = cur.fetchone()
        avg_marks = gm['avg_marks'] or 0
        
        cur.execute("SELECT SUM(amount) as pending FROM fees WHERE student_id=%s AND status='pending'", (sid,))
        f = cur.fetchone()
        pending_fees = f['pending'] or 0
        
        cur.close()
        conn.close()
        return jsonify({
            "attendance_percent": overall,
            "days_present": present,
            "days_total": total,
            "avg_marks": round(avg_marks, 2),
            "pending_fees": float(pending_fees)
        })
    except Exception as e:
        logger.error(f"Student summary error for user {user_id}: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/student/<int:user_id>/subjects', methods=['GET'])
def student_subjects(user_id):
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT id FROM students WHERE user_id=%s", (user_id,))
    s = cur.fetchone()
    if not s:
        cur.close(); conn.close()
        return jsonify({"error":"Student not found"}), 404
    sid = s['id']
    cur.execute("""
      SELECT c.id as course_id, c.code, c.title,
        SUM(a.present=1) as presents,
        COUNT(a.id) as total
      FROM courses c
      LEFT JOIN attendance a ON a.course_id = c.id AND a.student_id=%s
      GROUP BY c.id
    """,(sid,))
    rows = cur.fetchall()
    cur.close(); conn.close()
    
    res=[]
    for r in rows:
        total = r['total'] or 0
        present = r['presents'] or 0
        percent = int((present/total)*100) if total>0 else 0
        res.append({
            "course_id":r['course_id'],
            "code":r['code'],
            "title":r['title'],
            "present":present,
            "total":total,
            "percent":percent
        })
    return jsonify(res)

@app.route('/api/student/<int:user_id>/grades', methods=['GET'])
def student_grades(user_id):
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT id FROM students WHERE user_id=%s", (user_id,))
    s = cur.fetchone()
    if not s:
        cur.close(); conn.close()
        return jsonify({"error":"Student not found"}), 404
    sid = s['id']
    cur.execute("""
      SELECT c.code, c.title, g.marks, g.grade
      FROM grades g
      JOIN courses c ON g.course_id = c.id
      WHERE g.student_id=%s
    """,(sid,))
    data = cur.fetchall()
    cur.close(); conn.close()
    return jsonify(data)

@app.route('/api/student/<int:user_id>/materials', methods=['GET'])
def student_materials(user_id):
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
      SELECT sm.id, sm.title, sm.filename, c.code, c.title as course_title, sm.uploaded_at
      FROM study_materials sm
      JOIN courses c ON sm.course_id = c.id
      ORDER BY sm.uploaded_at DESC
    """)
    data = cur.fetchall()
    cur.close(); conn.close()
    return jsonify(data)

@app.route('/api/student/complaint', methods=['POST'])
def submit_complaint():
    try:
        body = request.json
        if not body or not body.get('user_id') or not body.get('subject') or not body.get('description'):
            return jsonify({"error": "All fields required"}), 400
        
        user_id = body.get('user_id')
        subject = body.get('subject')
        description = body.get('description')
        conn = get_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO complaints (user_id, subject, description) VALUES (%s,%s,%s)",
                    (user_id, subject, description))
        conn.commit()
        cur.close()
        conn.close()
        logger.info(f"Complaint submitted by user {user_id}")
        return jsonify({"ok": True})
    except Exception as e:
        logger.error(f"Submit complaint error: {e}")
        return jsonify({"error": "Internal server error"}), 500

# ============ STAFF ENDPOINTS ============
@app.route('/api/staff/<int:user_id>/summary', methods=['GET'])
def staff_summary(user_id):
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT id FROM staff WHERE user_id=%s", (user_id,))
    s = cur.fetchone()
    if not s:
        cur.close(); conn.close()
        return jsonify({"error":"Staff not found"}), 404
    
    cur.execute("SELECT COUNT(*) as total FROM courses")
    courses = cur.fetchone()
    
    cur.execute("SELECT COUNT(*) as total FROM students")
    students = cur.fetchone()
    
    cur.close(); conn.close()
    return jsonify({
        "total_courses": courses['total'],
        "total_students": students['total']
    })

@app.route('/api/staff/courses', methods=['GET'])
def staff_courses():
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM courses")
    data = cur.fetchall()
    cur.close(); conn.close()
    return jsonify(data)

@app.route('/api/staff/students', methods=['GET'])
def staff_students():
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
      SELECT s.id, s.roll_no, s.course, s.semester, u.full_name, u.email
      FROM students s
      JOIN users u ON s.user_id = u.id
    """)
    data = cur.fetchall()
    cur.close(); conn.close()
    return jsonify(data)

@app.route('/api/staff/attendance', methods=['POST'])
def mark_attendance():
    body = request.json
    course_id = body.get('course_id')
    date = body.get('date')
    students = body.get('students')  # [{student_id, present}, ...]
    
    conn = get_db(); cur = conn.cursor()
    for s in students:
        cur.execute("""
          INSERT INTO attendance (student_id, course_id, date, present)
          VALUES (%s, %s, %s, %s)
          ON DUPLICATE KEY UPDATE present=%s
        """, (s['student_id'], course_id, date, s['present'], s['present']))
    conn.commit()
    cur.close(); conn.close()
    return jsonify({"ok":True})

@app.route('/api/staff/grades', methods=['POST'])
def enter_grades():
    body = request.json
    student_id = body.get('student_id')
    course_id = body.get('course_id')
    marks = body.get('marks')
    grade = body.get('grade')
    
    conn = get_db(); cur = conn.cursor()
    cur.execute("""
      INSERT INTO grades (student_id, course_id, marks, grade)
      VALUES (%s, %s, %s, %s)
      ON DUPLICATE KEY UPDATE marks=%s, grade=%s
    """, (student_id, course_id, marks, grade, marks, grade))
    conn.commit()
    cur.close(); conn.close()
    return jsonify({"ok":True})

@app.route('/api/staff/upload-material', methods=['POST'])
def upload_material():
    try:
        f = request.files.get('file')
        course_id = request.form.get('course_id')
        title = request.form.get('title')
        if not f or not course_id or not title:
            return jsonify({"error": "File, course_id, and title required"}), 400
        
        filename = secure_filename(f.filename)
        f.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
        conn = get_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO study_materials (course_id, title, filename) VALUES (%s,%s,%s)",
                    (course_id, title, filename))
        conn.commit()
        cur.close()
        conn.close()
        logger.info(f"Material uploaded: {filename}")
        return jsonify({"ok": True, "filename": filename})
    except Exception as e:
        logger.error(f"Upload material error: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/staff/profile', methods=['POST'])
def get_staff_profile():
    data = request.get_json()
    token = data.get('token')
    if not token or not token.startswith('staff_token_'):
        return jsonify({'success': False, 'message': 'Invalid token'}), 401
    try:
        parts = token.split('_')
        if len(parts) < 3:
            return jsonify({'success': False, 'message': 'Invalid token'}), 401
        username = parts[2]
        conn = get_db(); cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT u.id AS user_id, u.username, u.full_name AS name, u.email,
                   s.dept AS department, s.designation, s.id AS staff_id
            FROM users u
            JOIN staff s ON s.user_id = u.id
            WHERE u.username=%s AND u.role='staff'
        """, (username,))
        rec = cur.fetchone(); cur.close(); conn.close()
        if not rec:
            return jsonify({'success': False, 'message': 'Staff not found'}), 404
        staff = {
            'id': rec['user_id'],
            'username': rec['username'],
            'name': rec['name'],
            'email': rec['email'],
            'department': rec['department'],
            'designation': rec['designation'],
            'staff_id': rec['staff_id']
        }
        return jsonify({'success': True, 'staff': staff}), 200
    except Exception as e:
        logger.error(f"Get staff profile error: {e}")
        return jsonify({'success': False, 'message': 'Database error: ' + str(e)}), 500

# ============ ADMIN ENDPOINTS ============
@app.route('/api/admin/summary', methods=['GET'])
def admin_summary():
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    
    cur.execute("SELECT COUNT(*) as total FROM students")
    students = cur.fetchone()
    
    cur.execute("SELECT COUNT(*) as total FROM staff")
    staff = cur.fetchone()
    
    cur.execute("SELECT COUNT(*) as total FROM courses")
    courses = cur.fetchone()
    
    cur.execute("SELECT COUNT(*) as total FROM complaints WHERE status='open'")
    complaints = cur.fetchone()
    
    cur.close(); conn.close()
    return jsonify({
        "total_students": students['total'],
        "total_staff": staff['total'],
        "total_courses": courses['total'],
        "open_complaints": complaints['total']
    })

@app.route('/api/admin/users', methods=['GET'])
def get_users():
    role = request.args.get('role', 'all')
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    if role == 'all':
        cur.execute("SELECT id, username, role, full_name, email, created_at FROM users")
    else:
        cur.execute("SELECT id, username, role, full_name, email, created_at FROM users WHERE role=%s", (role,))
    data = cur.fetchall()
    cur.close(); conn.close()
    return jsonify(data)

@app.route('/api/admin/user', methods=['POST'])
def add_user():
    try:
        body = request.json
        required_fields = ['username', 'password', 'role', 'full_name', 'email']
        if not body or not all(body.get(f) for f in required_fields):
            return jsonify({"error": "All required fields must be provided"}), 400
        username = body['username']; password_plain = body['password']
        password_hash = bcrypt.hash(password_plain)
        role = body['role']; full_name = body['full_name']; email = body['email']
        conn = get_db(); cur = conn.cursor()
        cur.execute("INSERT INTO users (username, password_hash, role, full_name, email) VALUES (%s,%s,%s,%s,%s)",
                    (username, password_hash, role, full_name, email))
        user_id = cur.lastrowid

        if role == 'student':
            roll_no = body.get('roll_no'); course = body.get('course'); semester = body.get('semester')
            if not roll_no or not course or semester is None:
                conn.rollback(); cur.close(); conn.close()
                return jsonify({"error":"Student fields required (roll_no, course, semester)"}), 400
            if students_has_auth_cols():
                cur.execute(
                    "INSERT INTO students (user_id, username, password_hash, roll_no, course, semester) VALUES (%s,%s,%s,%s,%s,%s)",
                    (user_id, username, password_hash, roll_no, course, semester)
                )
            else:
                # Backward-compatible insert for older schema
                cur.execute(
                    "INSERT INTO students (user_id, roll_no, course, semester) VALUES (%s,%s,%s,%s)",
                    (user_id, roll_no, course, semester)
                )
        elif role == 'staff':
            dept = body.get('dept'); designation = body.get('designation')
            if not dept or not designation:
                conn.rollback(); cur.close(); conn.close()
                return jsonify({"error":"Staff fields required (dept, designation)"}), 400
            cur.execute("INSERT INTO staff (user_id, dept, designation) VALUES (%s,%s,%s)",
                        (user_id, dept, designation))

        conn.commit(); cur.close(); conn.close()
        logger.info(f"User {username} added successfully")
        return jsonify({"ok": True, "user_id": user_id})
    except mysql.connector.IntegrityError as e:
        logger.warning(f"Integrity error adding user: {e}")
        msg = "Username or email already exists"
        if "for key 'students.username'" in str(e):
            msg = "Student username already exists"
        elif "for key 'students.roll_no'" in str(e):
            msg = "Student roll number already exists"
        elif "for key 'staff.user_id'" in str(e):
            msg = "Staff already exists for this user"
        return jsonify({"error": msg}), 409
    except Exception as e:
        logger.error(f"Add user error: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/admin/courses', methods=['GET'])
def get_courses():
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM courses")
    data = cur.fetchall()
    cur.close(); conn.close()
    return jsonify(data)

@app.route('/api/admin/course', methods=['POST'])
def add_course():
    try:
        body = request.json
        if not body or not body.get('code') or not body.get('title'):
            return jsonify({"error": "Code and title required"}), 400
        
        code = body.get('code')
        title = body.get('title')
        credits = body.get('credits', 3)
        conn = get_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO courses (code,title,credits) VALUES (%s,%s,%s)", (code, title, credits))
        conn.commit()
        cur.close()
        conn.close()
        logger.info(f"Course {code} added successfully")
        return jsonify({"ok": True})
    except mysql.connector.IntegrityError as e:
        logger.warning(f"Integrity error adding course: {e}")
        return jsonify({"error": "Course code already exists"}), 409
    except Exception as e:
        logger.error(f"Add course error: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/admin/complaints', methods=['GET'])
def get_complaints():
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
      SELECT c.id, c.subject, c.description, c.status, c.created_at, u.full_name
      FROM complaints c
      JOIN users u ON c.user_id = u.id
      ORDER BY c.created_at DESC
    """)
    data = cur.fetchall()
    cur.close(); conn.close()
    return jsonify(data)

@app.route('/api/admin/complaint/<int:id>/status', methods=['PUT'])
def update_complaint_status(id):
    try:
        body = request.json
        if not body or not body.get('status'):
            return jsonify({"error": "Status required"}), 400
        
        status = body.get('status')
        if status not in ['open', 'in_progress', 'resolved']:
            return jsonify({"error": "Invalid status"}), 400
        
        conn = get_db()
        cur = conn.cursor()
        cur.execute("UPDATE complaints SET status=%s WHERE id=%s", (status, id))
        if cur.rowcount == 0:
            cur.close()
            conn.close()
            return jsonify({"error": "Complaint not found"}), 404
        conn.commit()
        cur.close()
        conn.close()
        logger.info(f"Complaint {id} status updated to {status}")
        return jsonify({"ok": True})
    except Exception as e:
        logger.error(f"Update complaint status error: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/admin/students', methods=['GET'])
def admin_list_students():
    try:
        conn = get_db(); cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT u.id AS user_id, u.username, u.full_name, u.email, u.created_at,
                   s.id AS student_id, s.roll_no, s.course, s.semester
            FROM users u
            JOIN students s ON s.user_id = u.id
            WHERE u.role='student'
            ORDER BY u.created_at DESC
        """)
        rows = cur.fetchall(); cur.close(); conn.close()
        return jsonify(rows)
    except Exception as e:
        logger.error(f"List students error: {e}")
        return jsonify({"error":"Internal server error"}), 500

@app.route('/api/admin/staff', methods=['GET'])
def admin_list_staff():
    try:
        conn = get_db(); cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT u.id AS user_id, u.username, u.full_name, u.email, u.created_at,
                   s.id AS staff_row_id, s.dept, s.designation
            FROM users u
            JOIN staff s ON s.user_id = u.id
            WHERE u.role='staff'
            ORDER BY u.created_at DESC
        """)
        rows = cur.fetchall(); cur.close(); conn.close()
        return jsonify(rows)
    except Exception as e:
        logger.error(f"List staff error: {e}")
        return jsonify({"error":"Internal server error"}), 500

@app.route('/api/admin/user/<int:user_id>', methods=['PUT'])
def admin_update_user(user_id):
    try:
        body = request.json or {}
        conn = get_db(); cur = conn.cursor(dictionary=True)
        cur.execute("SELECT id, role FROM users WHERE id=%s", (user_id,))
        u = cur.fetchone()
        if not u:
            cur.close(); conn.close()
            return jsonify({"error":"User not found"}), 404
        updates = []
        params = []
        if body.get('username'):
            updates.append("username=%s"); params.append(body['username'])
        if body.get('full_name'):
            updates.append("full_name=%s"); params.append(body['full_name'])
        if body.get('email'):
            updates.append("email=%s"); params.append(body['email'])
        if body.get('password'):
            updates.append("password_hash=%s"); params.append(bcrypt.hash(body['password']))
        # Only update users table if there is something
        if updates:
            sql = "UPDATE users SET " + ", ".join(updates) + " WHERE id=%s"
            params.append(user_id)
            cur.execute(sql, tuple(params))
        # Role-specific
        if u['role'] == 'student':
            stu_updates = []
            stu_params = []
            if 'roll_no' in body: stu_updates.append("roll_no=%s"); stu_params.append(body['roll_no'])
            if 'course' in body: stu_updates.append("course=%s"); stu_params.append(body['course'])
            if 'semester' in body: stu_updates.append("semester=%s"); stu_params.append(body['semester'])
            if stu_updates:
                cur.execute("UPDATE students SET " + ", ".join(stu_updates) + " WHERE user_id=%s",
                            tuple(stu_params+[user_id]))
        elif u['role'] == 'staff':
            stf_updates = []
            stf_params = []
            if 'dept' in body: stf_updates.append("dept=%s"); stf_params.append(body['dept'])
            if 'designation' in body: stf_updates.append("designation=%s"); stf_params.append(body['designation'])
            if stf_updates:
                cur.execute("UPDATE staff SET " + ", ".join(stf_updates) + " WHERE user_id=%s",
                            tuple(stf_params+[user_id]))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"ok":True})
    except mysql.connector.IntegrityError:
        return jsonify({"error":"Duplicate username/email"}), 409
    except Exception as e:
        logger.error(f"Update user error: {e}")
        return jsonify({"error":"Internal server error"}), 500

@app.route('/api/admin/user/<int:user_id>', methods=['DELETE'])
def admin_delete_user(user_id):
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("DELETE FROM users WHERE id=%s", (user_id,))
        affected = cur.rowcount
        conn.commit(); cur.close(); conn.close()
        if affected == 0:
            return jsonify({"error":"User not found"}), 404
        return jsonify({"ok":True})
    except Exception as e:
        logger.error(f"Delete user error: {e}")
        return jsonify({"error":"Internal server error"}), 500

# ============ NOTIFICATIONS ============
@app.route('/api/notifications', methods=['GET'])
def get_notifications():
    target = request.args.get('role','all')
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    # modified: include sender info
    base = """
      SELECT n.id, n.title, n.body, n.target_role, n.created_at,
             u.username AS sender_username, u.full_name AS sender_full_name
      FROM notifications n
      LEFT JOIN users u ON n.sender_user_id = u.id
    """
    if target=='all':
        cur.execute(base + " ORDER BY n.created_at DESC LIMIT 50")
    else:
        cur.execute(base + " WHERE n.target_role IN ('all', %s) ORDER BY n.created_at DESC LIMIT 50",(target,))
    data = cur.fetchall()
    cur.close(); conn.close()
    return jsonify(data)

@app.route('/api/staff/notifications', methods=['GET'])
def staff_notifications():
    # staff receives 'all' + 'staff'
    conn = get_db(); cur = conn.cursor(dictionary=True)
    cur.execute("""
      SELECT n.id, n.title, n.body, n.target_role, n.created_at,
             u.username AS sender_username, u.full_name AS sender_full_name
      FROM notifications n
      LEFT JOIN users u ON n.sender_user_id = u.id
      WHERE n.target_role IN ('all','staff')
      ORDER BY n.created_at DESC LIMIT 50
    """)
    rows = cur.fetchall(); cur.close(); conn.close()
    return jsonify(rows)

def _send_email_via_node(recipients, subject, body):
    """
    Fire-and-forget email sending via Node + nodemailer.
    recipients: list of email strings
    """
    if not recipients:
        return
    try:
        script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'mailer', 'send-email.js'))
        if not os.path.isfile(script_path):
            logger.warning(f"Mailer script not found at {script_path}")
            return
        payload = json.dumps({
            "recipients": recipients,
            "subject": subject,
            "body": body
        })
        subprocess.Popen(['node', script_path, payload], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        logger.error(f"Email dispatch failed: {e}")

@app.route('/api/notification', methods=['POST'])
def send_notification():
    try:
        body = request.json or {}
        title = body.get('title'); message = body.get('body')
        if not title or not message:
            return jsonify({"error": "Title and body required"}), 400
        target_role = body.get('target_role', 'all')
        if target_role not in {'all','student','staff','admin'}:
            target_role = 'all'
        target_user_id = body.get('target_user_id')
        sender_user_id = body.get('sender_user_id')
        has_sender = notifications_has_sender_col()
        has_target = notifications_has_target_user_col()

        conn = get_db(); cur = conn.cursor()
        if has_sender and has_target:
            cur.execute(
                "INSERT INTO notifications (title, body, target_role, sender_user_id, target_user_id) VALUES (%s,%s,%s,%s,%s)",
                (title, message, target_role, sender_user_id, target_user_id)
            )
        elif has_sender:
            cur.execute(
                "INSERT INTO notifications (title, body, target_role, sender_user_id) VALUES (%s,%s,%s,%s)",
                (title, message, target_role, sender_user_id)
            )
        else:
            cur.execute(
                "INSERT INTO notifications (title, body, target_role) VALUES (%s,%s,%s)",
                (title, message, target_role)
            )
        conn.commit()

        recipient_emails = []
        rcur = conn.cursor()
        if target_user_id:
            rcur.execute("SELECT email FROM users WHERE id=%s LIMIT 1", (target_user_id,))
            recipient_emails = [r[0] for r in rcur.fetchall() if r[0]]
        else:
            if target_role == 'student':
                rcur.execute("SELECT email FROM users WHERE role='student'")
            elif target_role == 'staff':
                rcur.execute("SELECT email FROM users WHERE role='staff'")
            elif target_role == 'admin':
                rcur.execute("SELECT email FROM users WHERE role='admin'")
            else:
                rcur.execute("SELECT email FROM users WHERE role IN ('student','staff','admin')")
            recipient_emails = [r[0] for r in rcur.fetchall() if r[0]]
        rcur.close(); cur.close(); conn.close()

        _send_email_via_node(recipient_emails, title, message)
        return jsonify({
            "ok": True,
            "emails_queued": len(recipient_emails),
            "sender_column": has_sender,
            "target_column": has_target
        })
    except mysql.connector.IntegrityError as e:
        logger.error(f"Notification integrity error: {e}")
        return jsonify({"error": "DB integrity error"}), 409
    except Exception as e:
        logger.error(f"Send notification error: {e}")
        return jsonify({"error": str(e) or 'Internal error'}), 500

@app.route('/api/notification/<int:notification_id>', methods=['DELETE'])
def delete_notification(notification_id):
    try:
        body = request.get_json() or {}
        user_id = body.get('user_id')
        if not user_id:
            return jsonify({"error": "user_id required"}), 400
        conn = get_db(); cur = conn.cursor(dictionary=True)
        cur.execute("SELECT id, sender_user_id FROM notifications WHERE id=%s", (notification_id,))
        row = cur.fetchone()
        if not row:
            cur.close(); conn.close()
            return jsonify({"error": "Not found"}), 404
        cur.execute("SELECT role FROM users WHERE id=%s", (user_id,))
        u = cur.fetchone()
        role = u['role'] if u else None
        # sender or admin: hard delete
        if role == 'admin' or row['sender_user_id'] == user_id:
            cur.execute("DELETE FROM notifications WHERE id=%s", (notification_id,))
            conn.commit()
            cur.close(); conn.close()
            return jsonify({"ok": True, "mode": "hard"})
        # else soft delete
        cur.execute("""
          INSERT INTO notification_user_status (notification_id, user_id, deleted_at)
          VALUES (%s,%s,NOW())
          ON DUPLICATE KEY UPDATE deleted_at=VALUES(deleted_at)
        """,(notification_id, user_id))
        conn.commit()
        cur.close(); conn.close()
        return jsonify({"ok": True, "mode": "soft"})
    except Exception as e:
        logger.error(f"Delete notification error: {e}")
        return jsonify({"error": "Internal server error"}), 500

# ============ SERVE FRONTEND ============
from config import (
    FRONTEND_INDEX,
    FRONTEND_ROOT,
    ALLOWED_FRONTEND_EXTENSIONS,
)

def _resolve_frontend_asset(request_path: str) -> Path:
    """
    Map the requested path to an allowed file inside the frontend directory.
    Blocks path traversal attempts and unknown extensions.
    """
    candidate = (FRONTEND_ROOT / request_path).resolve()
    if not str(candidate).startswith(str(FRONTEND_ROOT)):
        abort(404)

    if candidate.is_dir():
        candidate = candidate / "index.html"

    if not candidate.exists():
        abort(404)

    if candidate.suffix and candidate.suffix.lower() not in ALLOWED_FRONTEND_EXTENSIONS:
        abort(403)

    return candidate


FRONTEND_DIR = os.path.join(os.path.dirname(__file__), '..', 'Frontend')
FRONTEND_INDEX = os.path.join(FRONTEND_DIR, 'index.html')


@app.route('/')
def serve_root():
    return send_file(FRONTEND_INDEX)


@app.get("/<path:resource>")
def serve_resource(resource: str):
    target = _resolve_frontend_asset(resource)
    return send_file(target)


@app.route('/api/users', methods=['GET'])
def public_users():
    role = request.args.get('role','all')
    conn = get_db(); cur = conn.cursor(dictionary=True)
    if role == 'all':
        cur.execute("SELECT id, username, role, full_name, email, created_at FROM users")
    else:
        cur.execute("SELECT id, username, role, full_name, email, created_at FROM users WHERE role=%s",(role,))
    rows = cur.fetchall(); cur.close(); conn.close()
    return jsonify(rows)

@app.route('/api/user/<int:user_id>/notifications', methods=['GET'])
def user_notifications(user_id):
    """Return notifications for a specific user: role-based + direct (target_user_id)."""
    try:
        conn = get_db(); cur = conn.cursor(dictionary=True)
        cur.execute("SELECT role FROM users WHERE id=%s", (user_id,))
        r = cur.fetchone()
        if not r:
            cur.close(); conn.close()
            return jsonify({"error":"User not found"}), 404
        role = r['role']
        has_target = notifications_has_target_user_col()
        # exclude soft-deleted
        base_filter = "NOT EXISTS (SELECT 1 FROM notification_user_status nus WHERE nus.notification_id = n.id AND nus.user_id=%s AND nus.deleted_at IS NOT NULL)"
        if has_target:
            cur.execute(f"""
              SELECT n.id, n.title, n.body, n.target_role, n.created_at,
                     u.username AS sender_username, u.full_name AS sender_full_name
              FROM notifications n
              LEFT JOIN users u ON n.sender_user_id = u.id
              WHERE ({base_filter})
                AND (n.target_role IN ('all', %s) OR n.target_user_id=%s)
              ORDER BY n.created_at DESC
              LIMIT 50
            """,(user_id, role, user_id))
        else:
            cur.execute(f"""
              SELECT n.id, n.title, n.body, n.target_role, n.created_at,
                     u.username AS sender_username, u.full_name AS sender_full_name
              FROM notifications n
              LEFT JOIN users u ON n.sender_user_id = u.id
              WHERE ({base_filter}) AND n.target_role IN ('all', %s)
              ORDER BY n.created_at DESC
              LIMIT 50
            """,(user_id, role))
        rows = cur.fetchall(); cur.close(); conn.close()
        return jsonify(rows)
    except Exception as e:
        logger.error(f"User notifications error: {e}")
        return jsonify({"error":"Internal server error"}), 500

if __name__ == "__main__":
    app.run(debug=True, port=5000, host="0.0.0.0")
