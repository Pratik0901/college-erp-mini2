from flask import Flask, request, jsonify, send_from_directory, abort, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from functools import wraps
from datetime import datetime, timedelta
import jwt
import mysql.connector
from passlib.hash import bcrypt
from werkzeug.utils import secure_filename
import os
import logging
from pathlib import Path
import time
import random
import secrets
from datetime import date, timedelta

app = Flask(__name__, static_folder="../Frontend", static_url_path="/")
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqlconnector://root:@127.0.0.1/college_erp'
app.config['SECRET_KEY'] = 'your_secret_key'  # Change this to a strong secret key
db = SQLAlchemy(app)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Suppress MySQL connector verbose logging
logging.getLogger('mysql.connector').setLevel(logging.WARNING)

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

def initialize_database():
    """Initialize database tables if they don't exist"""
    try:
        conn = get_db()
        cur = conn.cursor()
        
        # Create tables if they don't exist
        tables = [
            """CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(80) UNIQUE NOT NULL,
                email VARCHAR(120) UNIQUE NOT NULL,
                full_name VARCHAR(200),
                password_hash VARCHAR(255),
                role VARCHAR(50) DEFAULT 'student',
                phone VARCHAR(20),
                gender VARCHAR(20),
                dob DATE,
                enrollment_number VARCHAR(50),
                roll_number VARCHAR(50),
                course VARCHAR(100),
                semester VARCHAR(20),
                address TEXT,
                city VARCHAR(100),
                state VARCHAR(100),
                postal_code VARCHAR(20),
                country VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
            
            """CREATE TABLE IF NOT EXISTS students (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                roll_no VARCHAR(50) UNIQUE,
                course VARCHAR(100),
                semester INT,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
            
            """CREATE TABLE IF NOT EXISTS staff (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                dept VARCHAR(100),
                designation VARCHAR(100),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
            
            """CREATE TABLE IF NOT EXISTS courses (
                id INT AUTO_INCREMENT PRIMARY KEY,
                code VARCHAR(50) UNIQUE NOT NULL,
                title VARCHAR(200) NOT NULL,
                credits INT DEFAULT 3
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
            
            """CREATE TABLE IF NOT EXISTS attendance (
                id INT AUTO_INCREMENT PRIMARY KEY,
                student_id INT NOT NULL,
                course_id INT NOT NULL,
                date DATE NOT NULL,
                present BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
                FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
                UNIQUE KEY unique_attendance (student_id, course_id, date)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
            
            """CREATE TABLE IF NOT EXISTS grades (
                id INT AUTO_INCREMENT PRIMARY KEY,
                student_id INT NOT NULL,
                course_id INT NOT NULL,
                marks DECIMAL(7,2) DEFAULT 0,
                grade VARCHAR(16) DEFAULT NULL,
                semester INT DEFAULT 1,
                grade_point DECIMAL(5,2) DEFAULT 0,
                credits INT DEFAULT 3,
                academic_year VARCHAR(20),
                recorded_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
                FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
                UNIQUE KEY uq_student_course_semester (student_id, course_id, semester)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
            
            """CREATE TABLE IF NOT EXISTS fees (
                id INT AUTO_INCREMENT PRIMARY KEY,
                student_id INT NOT NULL,
                amount DECIMAL(10,2) NOT NULL,
                reason VARCHAR(255),
                due_date DATE NULL,
                status VARCHAR(20) DEFAULT 'pending',
                payment_method VARCHAR(50),
                payment_reference VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
            
            """CREATE TABLE IF NOT EXISTS complaints (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                subject VARCHAR(200) NOT NULL,
                description TEXT NOT NULL,
                status VARCHAR(20) DEFAULT 'open',
                admin_response TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
            
            """CREATE TABLE IF NOT EXISTS notifications (
                id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(200) NOT NULL,
                body TEXT NOT NULL,
                target_role VARCHAR(20) DEFAULT 'all',
                sender_user_id INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sender_user_id) REFERENCES users(id) ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
            
            """CREATE TABLE IF NOT EXISTS study_materials (
                id INT AUTO_INCREMENT PRIMARY KEY,
                course_id INT NOT NULL,
                title VARCHAR(200) NOT NULL,
                filename VARCHAR(255) NOT NULL,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""
        ]
        
        for table_sql in tables:
            cur.execute(table_sql)
        
        conn.commit()
        cur.close()
        conn.close()
        logger.info("✅ Database tables initialized successfully")
        
    except Exception as e:
        logger.error(f"❌ Database initialization error: {e}")
        raise

# Initialize database before creating admin
try:
    initialize_database()
except Exception as e:
    logger.warning(f"Database initialization warning: {e}")

# Token required decorator
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(" ")[1]
            except IndexError:
                return jsonify({'error': 'Invalid token format'}), 401
        
        if not token:
            return jsonify({'error': 'Token is missing'}), 401
        
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user = User.query.get(data['user_id'])
            if not current_user:
                return jsonify({'error': 'User not found'}), 404
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401
        
        return f(current_user, *args, **kwargs)
    
    return decorated

# Add User model definition if it doesn't exist
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    full_name = db.Column(db.String(200))
    password_hash = db.Column(db.String(255))
    role = db.Column(db.String(50), default='student')
    phone = db.Column(db.String(20))
    gender = db.Column(db.String(20))
    dob = db.Column(db.Date)
    enrollment_number = db.Column(db.String(50))
    roll_number = db.Column(db.String(50))
    course = db.Column(db.String(100))
    semester = db.Column(db.String(20))
    address = db.Column(db.Text)
    city = db.Column(db.String(100))
    state = db.Column(db.String(100))
    postal_code = db.Column(db.String(20))
    country = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<User {self.username}>'

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
        
        if bcrypt.verify(password, user['password_hash']):
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

ensure_default_admin()

@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    if not username or not password:
        return jsonify({'success': False, 'message': 'Username and password required'}), 400
    if username != ADMIN_USERNAME:
        return jsonify({'success': False, 'message': 'Invalid credentials'}), 401
    try:
        conn = get_db(); cur = conn.cursor(dictionary=True)
        cur.execute("SELECT id, password_hash FROM users WHERE username=%s AND role='admin'", (ADMIN_USERNAME,))
        admin = cur.fetchone(); cur.close(); conn.close()
        if not admin:
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
    """Student login endpoint"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Accept both 'identifier' and 'username' for compatibility
        identifier = data.get('identifier') or data.get('username')
        password = data.get('password')
        
        if not identifier or not password:
            return jsonify({'error': 'Username and password are required'}), 400
        
        # Use raw SQL query like other endpoints
        conn = get_db()
        cur = conn.cursor(dictionary=True)
        
        # Try to find student by username or roll_no (in students table)
        cur.execute("""
            SELECT u.id, u.username, u.full_name, u.email, u.password_hash, u.role,
                   s.roll_no as enrollment_number
            FROM users u
            LEFT JOIN students s ON s.user_id = u.id
            WHERE u.role = 'student' AND (u.username = %s OR s.roll_no = %s)
        """, (identifier, identifier))
        
        student = cur.fetchone()
        cur.close()
        conn.close()
        
        if not student:
            app.logger.warning(f'Student login failed identifier={identifier}')
            return jsonify({'success': False, 'message': 'Invalid credentials'}), 401
        
        # Check password using bcrypt (same as other login endpoints)
        if not bcrypt.verify(password, student['password_hash']):
            app.logger.warning(f'Student login failed identifier={identifier}')
            return jsonify({'success': False, 'message': 'Invalid credentials'}), 401
        
        # Generate token (simple token like other endpoints)
        token = f"student_token_{student['username']}_{int(time.time())}"
        
        # Remove password hash from response
        student_data = {
            'id': student['id'],
            'username': student['username'],
            'full_name': student['full_name'],
            'email': student['email'],
            'role': student['role'],
            'enrollment_number': student['enrollment_number']
        }
        
        app.logger.info(f'Student login successful identifier={identifier} user_id={student["id"]}')
        
        return jsonify({
            'success': True,
            'token': token,
            'student': student_data,
            'message': 'Login successful'
        }), 200
        
    except Exception as e:
        app.logger.error(f'Student login error: {str(e)}')
        return jsonify({'success': False, 'message': 'Internal server error'}), 500

def check_password(password_hash, password):
    """Check if provided password matches the hash"""
    # If you're using werkzeug.security
    try:
        from werkzeug.security import check_password_hash
        return check_password_hash(password_hash, password)
    except ImportError:
        # Simple comparison if no hashing is implemented
        return password_hash == password

# ============ STUDENT ENDPOINTS ============
@app.route('/api/student/<int:user_id>/summary', methods=['GET'])
def student_summary(user_id):
    try:
        conn = get_db()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT id FROM students WHERE user_id=%s", (user_id,))
        s = cur.fetchone()
        if not s:
            cur.close(); conn.close()
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
        
        cur.close(); conn.close()
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
    try:
        conn = get_db()
        cur = conn.cursor(dictionary=True)
        
        cur.execute("SELECT id FROM students WHERE user_id=%s", (user_id,))
        s = cur.fetchone()
        if not s:
            cur.close(); conn.close()
            return jsonify({"error":"Student not found"}), 404
        
        sid = s['id']
        cur.execute("""
          SELECT c.code, c.title, c.credits, g.marks, g.grade,
                 g.semester, g.academic_year, g.created_at
          FROM grades g
          JOIN courses c ON g.course_id = c.id
          WHERE g.student_id=%s
          ORDER BY g.semester DESC, c.code ASC
        """, (sid,))
        data = cur.fetchall()
        cur.close(); conn.close()
        
        return jsonify(data)
    except Exception as e:
        logger.error(f"Student grades error for user {user_id}: {e}")
        return jsonify({"error": "Internal server error"}), 500

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

@app.route('/api/student/<int:user_id>/complaints', methods=['GET'])
def get_student_complaints(user_id):
    try:
        conn = get_db()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT id FROM users WHERE id=%s AND role='student'", (user_id,))
        if not cur.fetchone():
            cur.close(); conn.close()
            return jsonify({"error": "Student not found"}), 404
        
        cur.execute("""
            SELECT c.id, c.subject, c.description, c.status, c.created_at,
                   c.admin_response, c.updated_at
            FROM complaints c
            WHERE c.user_id = %s
            ORDER BY c.created_at DESC
        """, (user_id,))
        
        complaints = cur.fetchall()
        cur.close(); conn.close()
        
        formatted_complaints = []
        for complaint in complaints:
            formatted_complaints.append({
                'id': complaint['id'],
                'subject': complaint['subject'],
                'description': complaint['description'],
                'status': complaint['status'],
                'created_at': complaint['created_at'].isoformat() if complaint['created_at'] else None,
                'updated_at': complaint['updated_at'].isoformat() if complaint['updated_at'] else None,
                'admin_response': complaint.get('admin_response', '')
            })
        
        logger.info(f"Retrieved {len(formatted_complaints)} complaints for student {user_id}")
        return jsonify(formatted_complaints)
    except Exception as e:
        logger.error(f"Get student complaints error: {e}")
        return jsonify({"error": "Internal server error"}), 500

# ============ FEES ENDPOINTS ============
@app.route('/api/student/<int:user_id>/fees', methods=['GET'])
def get_student_fees(user_id):
    try:
        conn = get_db()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT id FROM students WHERE user_id=%s", (user_id,))
        s = cur.fetchone()
        if not s:
            cur.close(); conn.close()
            return jsonify({"error": "Student not found"}), 404
        sid = s['id']

        cur.execute("""
            SELECT id, amount, reason, due_date, status, payment_method, payment_reference, created_at
            FROM fees
            WHERE student_id=%s
            ORDER BY created_at DESC
        """, (sid,))
        rows = cur.fetchall()
        cur.close(); conn.close()

        for r in rows:
            if r.get('created_at'):
                r['created_at'] = r['created_at'].isoformat()
            if r.get('due_date'):
                r['due_date'] = r['due_date'].isoformat()
        return jsonify(rows)
    except Exception as e:
        logger.error(f"Get student fees error for {user_id}: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/student/<int:user_id>/pay-fee', methods=['POST'])
def student_pay_fee(user_id):
    """
    Creates a fee record. If payment_method == 'UPI', returns a dummy UPI deep link
    and payment_id so the frontend can display a QR/link and poll status.
    """
    try:
        body = request.get_json() or {}
        amount = body.get('amount')
        reason = (body.get('reason') or '').strip()
        due_date = body.get('due_date')
        payment_method = (body.get('payment_method') or '').strip() or None

        if amount is None:
            return jsonify({"error": "amount required"}), 400

        # Create fees table if it doesn't exist (safe to call repeatedly)
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS fees (
                id INT AUTO_INCREMENT PRIMARY KEY,
                student_id INT NOT NULL,
                amount DECIMAL(10,2) NOT NULL,
                reason VARCHAR(255),
                due_date DATE NULL,
                status VARCHAR(20) DEFAULT 'pending',
                payment_method VARCHAR(50),
                payment_reference VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
            ) ENGINE=InnoDB
        """)
        conn.commit()

        # Find student row id
        cur.execute("SELECT id FROM students WHERE user_id=%s", (user_id,))
        s = cur.fetchone()
        if not s:
            cur.close(); conn.close()
            return jsonify({"error": "Student not found"}), 404
        sid = s[0]

        # Insert fee record as pending
        cur.execute("""
            INSERT INTO fees (student_id, amount, reason, due_date, payment_method, status)
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (sid, float(amount), reason or None, due_date, payment_method, 'pending'))
        conn.commit()
        new_id = cur.lastrowid

        # If UPI, return a dummy UPI deep-link and payment_id the front-end can use
        if payment_method and payment_method.upper() == 'UPI':
            # Create dummy UPI id and link (NOT real UPI — just for testing)
            payment_id = f"UPI-{new_id}-{int(time.time())}"
            # A simple UPI deep link (mock). Real apps would use payee vpa, amount, txn note, etc.
            upi_deep_link = f"upi://pay?pa=merchant@upi&pn=CollegeFees&am={float(amount):.2f}&tn={secure_filename(reason or 'Fee')}&tr={payment_id}"

            # Save the payment_id into payment_reference temporarily (optional)
            cur.execute("UPDATE fees SET payment_reference=%s WHERE id=%s", (payment_id, new_id))
            conn.commit()
            cur.close(); conn.close()

            return jsonify({
                "ok": True,
                "fee_id": new_id,
                "payment_method": "UPI",
                "payment_id": payment_id,
                "upi_link": upi_deep_link,
                "message": "UPI payment created (dummy). Poll /api/fee/<fee_id>/status to check result."
            }), 201

        # Non-UPI flow: return created record info (status pending — manual/offline payment)
        cur.close(); conn.close()
        return jsonify({"ok": True, "fee_id": new_id, "message": "Fee record created (pending)"}), 201

    except Exception as e:
        logger.error(f"student_pay_fee error for {user_id}: {e}", exc_info=True)
        return jsonify({"error": "Internal server error", "details": str(e)}), 500

@app.route('/api/fee/<int:fee_id>/pay-upi', methods=['POST'])
def pay_fee_upi(fee_id):
    """
    Direct UPI payment for existing fee record.
    Generates dummy UPI payment and immediately marks as paid for demo purposes.
    """
    try:
        conn = get_db()
        cur = conn.cursor(dictionary=True)
        
        # Get fee details
        cur.execute("SELECT * FROM fees WHERE id=%s", (fee_id,))
        fee = cur.fetchone()
        if not fee:
            cur.close(); conn.close()
            return jsonify({"error": "Fee not found"}), 404
        
        if fee['status'] == 'paid':
            cur.close(); conn.close()
            return jsonify({"error": "Fee already paid"}), 400
        
        # Generate dummy payment reference
        payment_ref = f"UPI{random.randint(100000000000, 999999999999)}"
        
        # Check if updated_at column exists, if not use simpler query
        try:
            # Try with updated_at column first
            cur.execute("""
                UPDATE fees SET status='paid', payment_method='UPI', 
                               payment_reference=%s, updated_at=NOW() 
                WHERE id=%s
            """, (payment_ref, fee_id))
        except mysql.connector.Error as e:
            if "Unknown column 'updated_at'" in str(e):
                # Fallback to simpler query without updated_at
                cur.execute("""
                    UPDATE fees SET status='paid', payment_method='UPI', 
                                   payment_reference=%s 
                    WHERE id=%s
                """, (payment_ref, fee_id))
            else:
                raise e
        
        conn.commit()
        
        # Get student details for receipt
        cur.execute("""
            SELECT u.id as user_id, u.full_name, u.username, s.roll_no 
            FROM students s 
            JOIN users u ON s.user_id = u.id 
            WHERE s.id = %s
        """, (fee['student_id'],))
        student = cur.fetchone()
        
        cur.close(); conn.close()
        
        return jsonify({
            "ok": True,
            "fee_id": fee_id,
            "payment_reference": payment_ref,
            "amount": float(fee['amount']),
            "reason": fee['reason'],
            "student_name": student['full_name'] if student else 'Unknown',
            "student_roll": student['roll_no'] if student else 'Unknown',
            "paid_at": datetime.now().isoformat(),
            "message": "Payment successful!"
        })
        
    except Exception as e:
        logger.error(f"pay_fee_upi error for fee {fee_id}: {e}", exc_info=True)
        return jsonify({"error": "Internal server error", "details": str(e)}), 500

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
    students = body.get('students')
    
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

@app.route('/api/staff/grades/auto', methods=['POST'])
def staff_grades_auto():
    """
    Robust single-file solution:
    - creates the grades table if missing
    - ensures required columns and unique index exist
    - inserts/updates grades (ON DUPLICATE KEY)
    - computes semester GPA and overall CGPA
    """
    try:
        body = request.json or {}
        student_id = body.get('student_id')
        sem_no = int(body.get('sem_no', 1))
        subjects_input = body.get('subjects', [])

        if not student_id or not subjects_input:
            return jsonify({"error": "student_id and subjects required"}), 400

        conn = get_db()
        cur = conn.cursor(dictionary=True)

        # --- ensure grades table exists with sensible schema (idempotent) ---
        cur.execute("""
            CREATE TABLE IF NOT EXISTS grades (
                id INT AUTO_INCREMENT PRIMARY KEY,
                student_id INT NOT NULL,
                course_id INT NOT NULL,
                marks DECIMAL(7,2) DEFAULT 0,
                grade VARCHAR(16) DEFAULT NULL,
                semester INT DEFAULT 1,
                grade_point DECIMAL(5,2) DEFAULT 0,
                credits INT DEFAULT 3,
                recorded_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB
        """)
        conn.commit()

        # Ensure required columns exist (safe ALTER TABLE ADD COLUMN IF NOT EXISTS)
        try:
            cur.execute("ALTER TABLE grades ADD COLUMN IF NOT EXISTS grade_point DECIMAL(5,2) DEFAULT 0")
            cur.execute("ALTER TABLE grades ADD COLUMN IF NOT EXISTS credits INT DEFAULT 3")
            cur.execute("ALTER TABLE grades ADD COLUMN IF NOT EXISTS recorded_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP")
            conn.commit()
        except Exception as e:
            # MySQL versions < 8.0 don't support "IF NOT EXISTS" for ALTER TABLE
            # Try individual column additions with error handling
            try:
                cur.execute("ALTER TABLE grades ADD COLUMN grade_point DECIMAL(5,2) DEFAULT 0")
            except:
                pass  # Column already exists
            try:
                cur.execute("ALTER TABLE grades ADD COLUMN credits INT DEFAULT 3")
            except:
                pass  # Column already exists
            try:
                cur.execute("ALTER TABLE grades ADD COLUMN recorded_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP")
            except:
                pass  # Column already exists
            conn.commit()

        # Ensure unique index exists for upsert key (student_id, course_id, semester)
        cur.execute("""
            SELECT COUNT(*) AS cnt
            FROM INFORMATION_SCHEMA.STATISTICS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'grades' AND INDEX_NAME = 'uq_student_course_semester'
        """)
        idx = cur.fetchone()
        if not idx or idx.get('cnt', 0) == 0:
            try:
                cur.execute("ALTER TABLE grades ADD UNIQUE KEY uq_student_course_semester (student_id, course_id, semester)")
                conn.commit()
            except Exception as e:
                # if it fails (rare), continue; upsert behavior may be affected
                logger.warning(f"Could not add unique index (maybe already present): {e}")

        # verify student exists (students.id)
        cur.execute("SELECT id FROM students WHERE id=%s LIMIT 1", (student_id,))
        if not cur.fetchone():
            cur.close(); conn.close()
            return jsonify({"error": "Student not found"}), 404

        # helper: compute grade and points
        def compute_grade_and_points(marks):
            try:
                m = float(marks or 0)
            except Exception:
                m = 0.0
            if m >= 90: return 'O', 10
            elif m >= 80: return 'A+', 9
            elif m >= 70: return 'A', 8
            elif m >= 60: return 'B+', 7
            elif m >= 55: return 'B', 6
            elif m >= 50: return 'C', 5
            elif m >= 45: return 'P', 4
            else: return 'F', 0

        computed_subjects = []

        for subj in subjects_input:
            course_code = (subj.get('course_code') or '').strip()
            marks = subj.get('marks', 0)

            if not course_code:
                continue

            cur.execute("SELECT id, title, credits FROM courses WHERE code=%s LIMIT 1", (course_code,))
            course = cur.fetchone()
            if not course:
                cur.close(); conn.close()
                return jsonify({"error": f"Course {course_code} not found"}), 404

            grade, grade_point = compute_grade_and_points(marks)
            credits = int(course.get('credits') or 3)

            # upsert row using the unique key (student_id, course_id, semester)
            cur.execute("""
                INSERT INTO grades (student_id, course_id, marks, grade, semester, grade_point, credits, recorded_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                ON DUPLICATE KEY UPDATE
                  marks = VALUES(marks),
                  grade = VALUES(grade),
                  grade_point = VALUES(grade_point),
                  credits = VALUES(credits),
                  recorded_at = NOW()
            """, (student_id, course['id'], float(marks), grade, sem_no, grade_point, credits))

            computed_subjects.append({
                'course_code': course_code,
                'course_title': course['title'],
                'marks': float(marks),
                'grade': grade,
                'grade_point': grade_point,
                'credits': credits,
                'semester': sem_no
            })

        # compute semester GPA
        cur.execute("""
            SELECT COALESCE(g.grade_point,0) AS gp, COALESCE(c.credits, g.credits, 3) AS credits
            FROM grades g
            JOIN courses c ON g.course_id = c.id
            WHERE g.student_id = %s AND g.semester = %s
        """, (student_id, sem_no))
        sem_rows = cur.fetchall()
        total_credits = sum(float(r['credits'] or 3) for r in sem_rows)
        weighted_points = sum(float(r['gp'] or 0) * float(r['credits'] or 3) for r in sem_rows)
        semester_gpa = (weighted_points / total_credits) if total_credits > 0 else 0.0

        # compute CGPA across all semesters
        cur.execute("""
            SELECT COALESCE(g.grade_point,0) AS gp, COALESCE(c.credits, g.credits, 3) AS credits
            FROM grades g
            JOIN courses c ON g.course_id = c.id
            WHERE g.student_id = %s
        """, (student_id,))
        all_rows = cur.fetchall()
        total_all_credits = sum(float(r['credits'] or 3) for r in all_rows)
        weighted_all = sum(float(r['gp'] or 0) * float(r['credits'] or 3) for r in all_rows)
        cgpa = (weighted_all / total_all_credits) if total_all_credits > 0 else 0.0

        conn.commit()
        cur.close(); conn.close()

        logger.info(f"Auto-computed {len(computed_subjects)} grades for student {student_id}, semester {sem_no}")

        return jsonify({
            "ok": True,
            "subjects": computed_subjects,
            "semester_gpa": round(semester_gpa, 2),
            "cgpa": round(cgpa, 2)
        })
    except Exception as e:
        logger.error(f"Auto-grades error: {e}", exc_info=True)
        return jsonify({"error": "Internal server error", "details": str(e)}), 500

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

@app.route('/api/admin/users', methods=['GET'])
def admin_list_users():
    """Get users filtered by role"""
    try:
        role = request.args.get('role')
        
        conn = get_db()
        cur = conn.cursor(dictionary=True)
        
        if role:
            if role == 'admin':
                cur.execute("""
                    SELECT u.id AS user_id, u.username, u.full_name, u.email, u.role, u.created_at
                    FROM users u
                    WHERE u.role = 'admin'
                    ORDER BY u.created_at DESC
                """)
            elif role == 'student':
                cur.execute("""
                    SELECT u.id AS user_id, u.username, u.full_name, u.email, u.role, u.created_at,
                           s.id AS student_id, s.roll_no, s.course, s.semester
                    FROM users u
                    LEFT JOIN students s ON s.user_id = u.id
                    WHERE u.role = 'student'
                    ORDER BY u.created_at DESC
                """)
            elif role == 'staff':
                cur.execute("""
                    SELECT u.id AS user_id, u.username, u.full_name, u.email, u.role, u.created_at,
                           s.id AS staff_row_id, s.dept, s.designation
                    FROM users u
                    LEFT JOIN staff s ON s.user_id = u.id
                    WHERE u.role = 'staff'
                    ORDER BY u.created_at DESC
                """)
            else:
                cur.execute("""
                    SELECT u.id AS user_id, u.username, u.full_name, u.email, u.role, u.created_at
                    FROM users u
                    WHERE u.role = %s
                    ORDER BY u.created_at DESC
                """, (role,))
        else:
            # Get all users if no role specified
            cur.execute("""
                SELECT u.id AS user_id, u.username, u.full_name, u.email, u.role, u.created_at
                FROM users u
                ORDER BY u.created_at DESC
            """)
        
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        # Format datetime objects
        for row in rows:
            if row.get('created_at'):
                row['created_at'] = row['created_at'].isoformat()
        
        return jsonify(rows)
    except Exception as e:
        logger.error(f"List users error: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/admin/user', methods=['POST'])
def add_user():
    try:
        body = request.json
        required_fields = ['username', 'password', 'role', 'full_name', 'email']
        if not body or not all(body.get(f) for f in required_fields):
            return jsonify({"error": "All required fields must be provided"}), 400
        
        username = body['username']
        password_hash = bcrypt.hash(body['password'])
        role = body['role']
        full_name = body['full_name']
        email = body['email']
        
        conn = get_db()
        cur = conn.cursor()
        
        # Insert into users table
        cur.execute("INSERT INTO users (username, password_hash, role, full_name, email) VALUES (%s,%s,%s,%s,%s)",
                    (username, password_hash, role, full_name, email))
        user_id = cur.lastrowid

        # Insert into role-specific tables
        if role == 'student':
            # Defensive trimming
            roll_no = (body.get('roll_no') or '').strip()
            course = (body.get('course') or '').strip()
            semester = body.get('semester')

            if not roll_no or not course or semester is None:
                conn.rollback(); cur.close(); conn.close()
                return jsonify({"error": "Student fields (roll_no, course, semester) are required"}), 400

            username_clean = username.strip()
            email_clean = email.strip()

            # Exclude current inserted user from duplicate check
            cur.execute("SELECT id FROM users WHERE (username=%s OR email=%s) AND id<>%s LIMIT 1",
                        (username_clean, email_clean, user_id))
            if cur.fetchone():
                conn.rollback(); cur.close(); conn.close()
                return jsonify({"error": "Username or email already exists"}), 409

            cur.execute("SELECT id FROM students WHERE roll_no=%s LIMIT 1", (roll_no,))
            if cur.fetchone():
                conn.rollback(); cur.close(); conn.close()
                return jsonify({"error": "Student roll number already exists"}), 409

            try:
                # Minimal insert; add columns if they exist in your schema
                cur.execute(
                    "INSERT INTO students (user_id, roll_no, course, semester) VALUES (%s,%s,%s,%s)",
                    (user_id, roll_no, course, int(semester))
                )
            except mysql.connector.IntegrityError as ie:
                conn.rollback(); cur.close(); conn.close()
                logger.warning(f"Integrity error when inserting student row: {ie}")
                return jsonify({"error": "Database integrity error when creating student"}), 409

        elif role == 'staff':
            dept = body.get('dept')
            designation = body.get('designation')
            if not dept or not designation:
                conn.rollback()
                cur.close()
                conn.close()
                return jsonify({"error": "Staff fields (dept, designation) are required"}), 400
            
            # Insert into staff table
            cur.execute("INSERT INTO staff (user_id, dept, designation) VALUES (%s,%s,%s)",
                        (user_id, dept, designation))

        conn.commit()
        cur.close()
        conn.close()
        logger.info(f"User {username} added successfully with role {role}")
        return jsonify({"ok": True, "user_id": user_id, "message": f"{role.title()} created successfully"})
        
    except mysql.connector.IntegrityError as e:
        logger.warning(f"Integrity error adding user: {e}")
        return jsonify({"error": "Username or email already exists"}), 409
    except Exception as e:
        logger.error(f"Add user error: {e}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

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
    except mysql.connector.IntegrityError:
        return jsonify({"error": "Course code already exists"}), 409
    except Exception as e:
        logger.error(f"Add course error: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/admin/complaints', methods=['GET'])
def get_complaints():
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
      SELECT c.id, c.subject, c.description, c.status, c.created_at, 
             c.admin_response, c.updated_at, u.full_name
      FROM complaints c
      JOIN users u ON c.user_id = u.id
      ORDER BY c.created_at DESC
    """)
    data = cur.fetchall()
    
    for complaint in data:
        if complaint['created_at']:
            complaint['created_at'] = complaint['created_at'].isoformat()
        if complaint['updated_at']:
            complaint['updated_at'] = complaint['updated_at'].isoformat()
    
    cur.close()
    conn.close()
    return jsonify(data)

@app.route('/api/admin/complaint/<int:id>/status', methods=['PUT'])
def update_complaint_status(id):
    try:
        body = request.json
        if not body or not body.get('status'):
            return jsonify({"error": "Status required"}), 400
        
        status = body.get('status')
        admin_response = body.get('admin_response', '')
        
        if status not in ['open', 'in_progress', 'resolved']:
            return jsonify({"error": "Invalid status"}), 400
        
        conn = get_db()
        cur = conn.cursor()
        cur.execute("UPDATE complaints SET status=%s, admin_response=%s, updated_at=NOW() WHERE id=%s", 
                    (status, admin_response, id))
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

@app.route('/api/notification', methods=['POST'])
def send_notification():
    try:
        body = request.json or {}
        title = body.get('title')
        message = body.get('body')
        if not title or not message:
            return jsonify({"error": "Title and body required"}), 400
        target_role = body.get('target_role', 'all')
        if target_role not in {'all','student','staff','admin'}:
            target_role = 'all'
        
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO notifications (title, body, target_role) VALUES (%s,%s,%s)",
            (title, message, target_role)
        )
        conn.commit()
        cur.close(); conn.close()

        return jsonify({"ok": True, "emails_queued": 0})
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
        conn = get_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM notifications WHERE id=%s", (notification_id,))
        conn.commit()
        cur.close(); conn.close()
        return jsonify({"ok": True})
    except Exception as e:
        logger.error(f"Delete notification error: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/user/<int:user_id>/notifications', methods=['GET'])
def user_notifications(user_id):
    try:
        conn = get_db()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT role FROM users WHERE id=%s", (user_id,))
        r = cur.fetchone()
        if not r:
            cur.close(); conn.close()
            return jsonify({"error":"User not found"}), 404
        role = r['role']
        
        cur.execute("""
          SELECT n.id, n.title, n.body, n.target_role, n.created_at,
                 u.username AS sender_username, u.full_name AS sender_full_name
          FROM notifications n
          LEFT JOIN users u ON n.sender_user_id = u.id
          WHERE n.target_role IN ('all', %s)
          ORDER BY n.created_at DESC
          LIMIT 50
        """, (role,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(rows)
    except Exception as e:
        logger.error(f"User notifications error: {e}")
        return jsonify({"error":"Internal server error"}), 500

# ============ SERVE FRONTEND ============
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), '..', 'Frontend')
FRONTEND_INDEX = os.path.join(FRONTEND_DIR, 'index.html')

@app.route('/')
def serve_root():
    return send_file(FRONTEND_INDEX)

@app.route('/api/student/<int:user_id>/profile', methods=['GET', 'PUT'])
@token_required
def student_profile(current_user, user_id):
    """Get or update student profile"""
    # Verify student owns their own profile
    if current_user.id != user_id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    student = User.query.get(user_id)
    if not student or student.role != 'student':
        return jsonify({'error': 'Student not found'}), 404
    
    if request.method == 'GET':
        return jsonify({
            'id': student.id,
            'username': student.username,
            'full_name': student.full_name,
            'email': student.email,
            'phone': student.phone,
            'dob': student.dob.isoformat() if student.dob else None,
            'gender': student.gender,
            'enrollment_number': student.enrollment_number,
            'roll_number': student.roll_number,
            'course': student.course,
            'semester': student.semester,
            'address': student.address,
            'city': student.city,
            'state': student.state,
            'postal_code': student.postal_code,
            'country': student.country,
            'created_at': student.created_at.isoformat()
        }), 200
    
    if request.method == 'PUT':
        data = request.get_json()
        
        # Validate required fields
        if not data.get('full_name'):
            return jsonify({'error': 'Full name is required'}), 400
        if not data.get('email'):
            return jsonify({'error': 'Email is required'}), 400
        
        try:
            # Update profile fields
            student.full_name = data.get('full_name', student.full_name)
            student.email = data.get('email', student.email)
            student.phone = data.get('phone') or student.phone
            student.gender = data.get('gender') or student.gender
            student.dob = data.get('dob') or student.dob
            student.roll_number = data.get('roll_number') or student.roll_number
            student.address = data.get('address') or student.address
            student.city = data.get('city') or student.city
            student.state = data.get('state') or student.state
            student.postal_code = data.get('postal_code') or student.postal_code
            student.country = data.get('country') or student.country
            
            db.session.commit()
            
            return jsonify({
                'message': 'Profile updated successfully',
                'id': student.id,
                'username': student.username,
                'full_name': student.full_name,
                'email': student.email,
                'phone': student.phone,
                'dob': student.dob.isoformat() if student.dob else None,
                'gender': student.gender,
                'roll_number': student.roll_number,
                'address': student.address,
                'city': student.city,
                'state': student.state,
                'postal_code': student.postal_code,
                'country': student.country
            }), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': 'Failed to update profile: ' + str(e)}), 500

@app.route('/api/student/<int:user_id>/detailed-performance', methods=['GET'])
def student_detailed_performance(user_id):
    """Get comprehensive performance data with staff feedback and improvement suggestions"""
    try:
        conn = get_db()
        cur = conn.cursor(dictionary=True)
        
        # Get student ID
        cur.execute("SELECT id FROM students WHERE user_id=%s", (user_id,))
        s = cur.fetchone()
        if not s:
            cur.close(); conn.close()
            return jsonify({"error": "Student not found"}), 404
        sid = s['id']
        
        # Get subject-wise performance with grades and CGPA
        cur.execute("""
            SELECT c.code, c.title as subject_name, c.credits,
                   g.marks, g.grade, g.grade_point, g.semester,
                   COUNT(DISTINCT a.date) as total_classes,
                   SUM(CASE WHEN a.present = 1 THEN 1 ELSE 0 END) as classes_attended
            FROM courses c
            LEFT JOIN grades g ON c.id = g.course_id AND g.student_id = %s
            LEFT JOIN attendance a ON c.id = a.course_id AND a.student_id = %s
            GROUP BY c.id, g.marks, g.grade, g.grade_point, g.semester
            HAVING g.marks IS NOT NULL
            ORDER BY c.code
        """, (sid, sid))
        subjects = cur.fetchall()
        
        # Get overall attendance
        cur.execute("""
            SELECT COUNT(*) as total, SUM(present=1) as present 
            FROM attendance WHERE student_id=%s
        """, (sid,))
        att_data = cur.fetchone()
        total_classes = att_data['total'] or 0
        present_classes = att_data['present'] or 0
        attendance_percent = int((present_classes/total_classes)*100) if total_classes > 0 else 0
        
        # Calculate CGPA (cumulative across all semesters)
        cur.execute("""
            SELECT AVG(grade_point) as cgpa
            FROM grades WHERE student_id=%s
        """, (sid,))
        cgpa_data = cur.fetchone()
        overall_cgpa = cgpa_data['cgpa'] or 0
        
        # Calculate overall statistics
        cur.execute("""
            SELECT AVG(marks) as avg_marks, 
                   MIN(marks) as min_marks, 
                   MAX(marks) as max_marks,
                   COUNT(*) as subject_count
            FROM grades WHERE student_id=%s
        """, (sid,))
        stats = cur.fetchone()
        
        cur.close(); conn.close()
        
        # Process subjects data
        subjects_data = []
        weak_subjects = []
        strong_subjects = []
        
        for subj in subjects:
            total = subj['total_classes'] or 0
            attended = subj['classes_attended'] or 0
            att_percent = int((attended/total)*100) if total > 0 else 0
            
            marks = subj['marks'] or 0
            status = 'excellent' if marks >= 80 else 'good' if marks >= 60 else 'average' if marks >= 45 else 'poor'
            
            # Track weak and strong subjects
            if marks < 60:
                weak_subjects.append({'name': subj['subject_name'], 'marks': marks, 'attendance': att_percent})
            elif marks >= 80:
                strong_subjects.append({'name': subj['subject_name'], 'marks': marks})
            
            feedback = generate_subject_feedback(marks, att_percent, subj['grade'])
            
            subjects_data.append({
                'code': subj['code'],
                'subject_name': subj['subject_name'],
                'credits': subj['credits'] or 3,
                'marks': marks,
                'grade': subj['grade'] or 'N/A',
                'grade_point': subj['grade_point'] or 0,
                'cgpa': round(subj['grade_point'] or 0, 2),
                'attendance_percent': att_percent,
                'classes_attended': attended,
                'total_classes': total,
                'status': status,
                'staff_feedback': feedback,
                'semester': subj['semester'] or 1
            })
        
        # Generate personalized improvement suggestions
        suggestions = generate_improvement_suggestions(
            attendance_percent, 
            stats['avg_marks'] or 0, 
            overall_cgpa,
            weak_subjects,
            strong_subjects,
            stats['subject_count'] or 0
        )
        
        return jsonify({
            'ok': True,
            'subjects': subjects_data,
            'overall': {
                'attendance_percent': attendance_percent,
                'avg_marks': round(stats['avg_marks'] or 0, 2),
                'cgpa': round(overall_cgpa, 2)
            },
            'improvement_suggestions': suggestions
        })
        
    except Exception as e:
        logger.error(f"Detailed performance error: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500

def generate_improvement_suggestions(attendance, avg_marks, cgpa, weak_subjects, strong_subjects, total_subjects):
    """Generate personalized improvement suggestions based on performance"""
    suggestions = {
        'priority': 'high',  # high, medium, low
        'main_message': '',
        'action_items': [],
        'strengths': [],
        'areas_of_concern': []
    }
    
    # Determine priority level
    critical_issues = 0
    if attendance < 75:
        critical_issues += 1
    if avg_marks < 50:
        critical_issues += 1
    if cgpa < 5.0:
        critical_issues += 1
    
    if critical_issues >= 2:
        suggestions['priority'] = 'high'
        suggestions['main_message'] = '🚨 Urgent Action Required: Your performance needs immediate attention!'
    elif critical_issues == 1:
        suggestions['priority'] = 'medium'
        suggestions['main_message'] = '⚠️ Attention Needed: Focus on improving key areas of your performance.'
    else:
        suggestions['priority'] = 'low'
        suggestions['main_message'] = '✅ Good Progress: Keep up the momentum and aim for excellence!'
    
    # Attendance-based suggestions
    if attendance < 75:
        suggestions['areas_of_concern'].append({
            'issue': 'Low Attendance',
            'detail': f'Your attendance is {attendance}%, below the required 75%',
            'impact': 'May affect exam eligibility and overall understanding'
        })
        suggestions['action_items'].extend([
            '📅 Attend all remaining classes without fail',
            '⏰ Set daily reminders for class timings',
            '🤝 Form study groups to stay motivated',
            '💬 Speak with academic advisor about catching up'
        ])
    elif attendance < 85:
        suggestions['action_items'].append('📅 Aim to increase attendance above 85% for better learning')
    else:
        suggestions['strengths'].append(f'✨ Excellent attendance of {attendance}%')
    
    # Academic performance suggestions
    if avg_marks < 50:
        suggestions['areas_of_concern'].append({
            'issue': 'Below Average Performance',
            'detail': f'Average marks of {avg_marks:.1f}% need significant improvement',
            'impact': 'Risk of failing courses and low CGPA'
        })
        suggestions['action_items'].extend([
            '📚 Dedicate minimum 3-4 hours daily for studies',
            '👨‍🏫 Attend all doubt-clearing sessions',
            '📝 Complete assignments on time',
            '🎯 Focus on understanding concepts rather than memorizing'
        ])
    elif avg_marks < 60:
        suggestions['action_items'].extend([
            '📖 Increase study hours to at least 2-3 hours daily',
            '✍️ Practice more problems and previous year papers'
        ])
    elif avg_marks >= 80:
        suggestions['strengths'].append(f'🌟 Outstanding average marks of {avg_marks:.1f}%')
    
    # CGPA-based suggestions
    if cgpa < 5.0:
        suggestions['areas_of_concern'].append({
            'issue': 'Low CGPA',
            'detail': f'CGPA of {cgpa:.2f} is below satisfactory level',
            'impact': 'May affect future opportunities and placements'
        })
        suggestions['action_items'].append('🎯 Target minimum 7.0 CGPA through consistent effort')
    elif cgpa >= 8.0:
        suggestions['strengths'].append(f'🏆 Impressive CGPA of {cgpa:.2f}')
    
    # Subject-specific suggestions
    if weak_subjects:
        weak_list = ', '.join([f"{s['name']} ({s['marks']}%)" for s in weak_subjects[:3]])
        suggestions['areas_of_concern'].append({
            'issue': 'Weak Subjects Identified',
            'detail': f'{len(weak_subjects)} subject(s) need attention: {weak_list}',
            'impact': 'Dragging down overall performance'
        })
        suggestions['action_items'].extend([
            f'🎓 Focus extra 1-2 hours daily on: {", ".join([s["name"] for s in weak_subjects[:2]])}',
            '👥 Join subject-specific study groups or get tutoring',
            '📊 Analyze past mistakes and work on weak topics'
        ])
    
    if strong_subjects:
        strong_list = ', '.join([s['name'] for s in strong_subjects[:2]])
        suggestions['strengths'].append(f'💪 Strong performance in: {strong_list}')
    
    # General recommendations based on overall status
    if suggestions['priority'] == 'high':
        suggestions['action_items'].extend([
            '🚨 Meet with faculty advisor this week',
            '📋 Create a structured daily study timetable',
            '❌ Eliminate distractions during study hours'
        ])
    elif suggestions['priority'] == 'medium':
        suggestions['action_items'].extend([
            '📈 Review and revise notes after each class',
            '⚡ Participate actively in class discussions'
        ])
    else:
        suggestions['action_items'].extend([
            '🎯 Set higher goals and challenge yourself',
            '🤝 Help peers who are struggling',
            '🏅 Participate in co-curricular activities'
        ])
    
    # Add motivational message
    if suggestions['priority'] == 'high':
        suggestions['motivation'] = '💪 Remember: Every expert was once a beginner. Start today, improve gradually!'
    elif suggestions['priority'] == 'medium':
        suggestions['motivation'] = '🌱 You\'re on the right path. Stay consistent and you\'ll see great results!'
    else:
        suggestions['motivation'] = '🌟 Excellent work! Maintain this momentum and reach new heights!'
    
    return suggestions

def generate_subject_feedback(marks, attendance, grade):
    """Generate realistic staff feedback based on performance"""
    if marks >= 85 and attendance >= 85:
        feedbacks = [
            "Excellent work! Shows consistent dedication and understanding of the subject. Keep it up!",
            "Outstanding performance! Very active in class and demonstrates strong grasp of concepts.",
            "Exceptional student! Regularly participates and produces high-quality work.",
            "Remarkable progress! Always prepared and engaged during lectures."
        ]
    elif marks >= 70 and attendance >= 75:
        feedbacks = [
            "Good performance overall. Continue your steady effort and aim for excellence.",
            "Solid understanding of the subject. Focus on weak areas to improve further.",
            "Regular attendance and decent marks. Keep working consistently.",
            "Good work! With more practice, you can achieve even better results."
        ]
    elif marks >= 50 and attendance >= 65:
        feedbacks = [
            "Average performance. Need to focus more on understanding core concepts.",
            "Satisfactory work but can do much better. Attend all classes and study regularly.",
            "Room for improvement. Please seek help during doubt sessions.",
            "Needs more effort. Regular study and attendance will help improve performance."
        ]
    else:
        feedbacks = [
            "Performance needs significant improvement. Please meet me during office hours.",
            "Struggling with the subject. Strongly recommend extra tutoring and better attendance.",
            "Below expectations. Immediate action required to avoid failing the course.",
            "Critical situation. Must improve attendance and dedicate more study time."
        ]
    
    import random
    return random.choice(feedbacks)

if __name__ == "__main__":
    try:
        print("=" * 50)
        print("Starting College ERP Backend Server")
        print("URL: http://localhost:5000")
        print("=" * 50)
        app.run(debug=True, host="0.0.0.0", port=5000, use_reloader=True)
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        print(f"ERROR: {e}")
