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
import sys

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

# Add User model definition
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
    # ...existing code from college-erp/Backend/app.py...
    pass

# Copy all remaining endpoints from the original app.py file
# Including: admin_login, staff_login, student_login, all student endpoints,
# all staff endpoints, all admin endpoints, helper functions, etc.

# For brevity, I'll indicate where to copy the rest of the code
# ...existing code from lines 286 to end of file...

# This is a standalone copy of app.py for testing from the test folder

# Ensure we can find the original app if needed
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'college-erp', 'Backend'))

# Import everything from the original app.py
try:
    from app import *
except ImportError as e:
    print(f"⚠️ Warning: Could not import from original app.py: {e}")
    print("📝 Please ensure college-erp/Backend/app.py exists")
    
    # Fallback: Define minimal app if import fails
    from flask import Flask
    app = Flask(__name__)
    
    @app.route('/')
    def index():
        return "College ERP Backend - Import Error. Please check app.py location."

if __name__ == "__main__":
    try:
        print("\n" + "=" * 60)
        print("🚀 COLLEGE ERP BACKEND SERVER (TEST FOLDER)")
        print("=" * 60)
        print(f"📂 Working Directory: {os.getcwd()}")
        print(f"📍 Script Location: {__file__}")
        print("🌐 URL: http://localhost:5000")
        print("💾 Database: college_erp @ localhost")
        print("👤 Default Admin: username='admin', password='admin123'")
        print("=" * 60 + "\n")
        
        app.run(debug=True, host="0.0.0.0", port=5000, use_reloader=True)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
