# pyright: reportMissingImports=false

import datetime
try:
    from flask_sqlalchemy import SQLAlchemy
except ImportError:
    SQLAlchemy = None  # type: ignore

db = SQLAlchemy()

class Staff(db.Model):
    __tablename__ = 'staff'
    
    id = db.Column(db.Integer, primary_key=True)
    staff_id = db.Column(db.String(50), unique=True, nullable=False)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(100), nullable=False)
    total_students = db.Column(db.Integer, default=0)
    total_courses = db.Column(db.Integer, default=0)
    courses = db.Column(db.JSON, default=[])  # Store courses as JSON
    created_at = db.Column(db.DateTime, default=datetime.datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)
    
    def __repr__(self):
        return f'<Staff {self.username}>'

# ...existing models...
