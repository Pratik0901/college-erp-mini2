-- Create the database
CREATE DATABASE IF NOT EXISTS college_erp;
USE college_erp;

-- Users table
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('student', 'staff', 'admin') NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Students table
DROP TABLE IF EXISTS students;
CREATE TABLE students (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT UNIQUE NOT NULL,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    roll_no VARCHAR(20) UNIQUE NOT NULL,
    course VARCHAR(100) NOT NULL,
    semester INT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX idx_students_username ON students(username);

-- Optional migration (execute manually if needed):
-- ALTER TABLE students ADD COLUMN username VARCHAR(50) UNIQUE;
-- ALTER TABLE students ADD COLUMN password_hash VARCHAR(255);

-- Staff table
CREATE TABLE staff (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT UNIQUE NOT NULL,
    dept VARCHAR(100) NOT NULL,
    designation VARCHAR(100) NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Courses table
CREATE TABLE courses (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(20) UNIQUE NOT NULL,
    title VARCHAR(100) NOT NULL,
    credits INT DEFAULT 3
);

-- Attendance table
CREATE TABLE attendance (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    course_id INT NOT NULL,
    date DATE NOT NULL,
    present BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
    UNIQUE KEY unique_attendance (student_id, course_id, date)
);

-- Grades table
CREATE TABLE grades (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    course_id INT NOT NULL,
    marks DECIMAL(5,2),
    grade VARCHAR(5),
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
    UNIQUE KEY unique_grade (student_id, course_id)
);

-- Fees table
CREATE TABLE fees (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    status ENUM('pending', 'paid') DEFAULT 'pending',
    due_date DATE,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
);

-- Complaints table
CREATE TABLE complaints (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    subject VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    status ENUM('open', 'in_progress', 'resolved') DEFAULT 'open',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Study Materials table
CREATE TABLE study_materials (
    id INT AUTO_INCREMENT PRIMARY KEY,
    course_id INT NOT NULL,
    title VARCHAR(200) NOT NULL,
    filename VARCHAR(255) NOT NULL,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
);

-- Notifications table
CREATE TABLE notifications (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    body TEXT NOT NULL,
    target_role ENUM('all', 'student', 'staff', 'admin') DEFAULT 'all',
    sender_user_id INT NULL,
    target_user_id INT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sender_user_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (target_user_id) REFERENCES users(id) ON DELETE CASCADE
);
-- Migration (run manually if table exists):
-- ALTER TABLE notifications ADD COLUMN target_user_id INT NULL;
-- ALTER TABLE notifications ADD CONSTRAINT fk_notifications_target FOREIGN KEY (target_user_id) REFERENCES users(id) ON DELETE CASCADE;

-- Index on role to speed up queries
CREATE INDEX idx_users_role ON users(role);

-- Reset users; keep only single admin (password: admin123)
DELETE FROM users;
INSERT INTO users (username, password_hash, role, full_name, email) VALUES
('admin', '$2b$12$KIXxENohs4B9lnZ/8wQGteW/6Z9YuqbWtaXDpUe1koRaSPaQUWf6e', 'admin', 'System Administrator', 'admin@college.edu');

-- =========================
-- MIGRATION: Notifications
-- =========================
-- 1) Stop the running Flask app.
-- 2) Open MySQL (CLI: mysql -u root, or phpMyAdmin).
-- 3) Select DB:
--    USE college_erp;
-- 4) Inspect current columns:
--    SHOW COLUMNS FROM notifications;
-- 5) If sender_user_id missing:
--    ALTER TABLE notifications ADD COLUMN sender_user_id INT NULL;
--    ALTER TABLE notifications ADD CONSTRAINT fk_notifications_sender FOREIGN KEY (sender_user_id)
--      REFERENCES users(id) ON DELETE SET NULL;
-- 6) If target_user_id missing:
--    ALTER TABLE notifications ADD COLUMN target_user_id INT NULL;
--    ALTER TABLE notifications ADD CONSTRAINT fk_notifications_target FOREIGN KEY (target_user_id)
--      REFERENCES users(id) ON DELETE CASCADE;
-- 7) Verify:
--    SHOW COLUMNS FROM notifications;
--    SELECT id,title,sender_user_id,target_user_id FROM notifications LIMIT 5;
-- 8) Restart Flask app.
-- 9) Test sending:
--    POST /api/notification with JSON:
--    {"title":"Test","body":"Hello","target_role":"student","sender_user_id":1}
--    Optional direct:
--    {"title":"Direct","body":"Hello user","target_role":"student","target_user_id":5,"sender_user_id":1}
-- 10) Check retrieval:
--    GET /api/user/5/notifications
-- =========================
