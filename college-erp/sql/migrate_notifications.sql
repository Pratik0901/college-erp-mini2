USE college_erp;

-- Inspect current structure
SHOW COLUMNS FROM notifications;

-- Add sender_user_id if missing
ALTER TABLE notifications ADD COLUMN sender_user_id INT NULL;
ALTER TABLE notifications
  ADD CONSTRAINT fk_notifications_sender
  FOREIGN KEY (sender_user_id) REFERENCES users(id) ON DELETE SET NULL;

-- Add target_user_id if missing
ALTER TABLE notifications ADD COLUMN target_user_id INT NULL;
ALTER TABLE notifications
  ADD CONSTRAINT fk_notifications_target
  FOREIGN KEY (target_user_id) REFERENCES users(id) ON DELETE CASCADE;

-- Verify
SHOW COLUMNS FROM notifications;
SELECT id, title, sender_user_id, target_user_id, created_at FROM notifications LIMIT 10;
