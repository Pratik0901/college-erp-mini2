const emailService = require('./emailService');

class NotificationService {
  // Assuming you have these DB functions - adapt to your actual DB layer
  async getStudentEmailsByIds(studentIds) {
    // Replace with your actual DB query
    // Should return array of objects like: [{ id, email, name }, ...]
    // Example implementation:
    /*
    const students = await db.query(
      'SELECT id, email, name FROM students WHERE id IN (?)',
      [studentIds]
    );
    return students.filter(student => student.email && this.isValidEmail(student.email));
    */
    
    // Mock implementation - replace with your actual DB code
    return studentIds.map(id => ({
      id,
      email: `student${id}@example.com`, // Replace with actual email from DB
      name: `Student ${id}` // Replace with actual name from DB
    }));
  }

  async getSenderInfo(senderId, senderRole) {
    // Replace with your actual DB query to get sender name
    // Example implementation:
    /*
    if (senderRole === 'admin') {
      const admin = await db.query('SELECT name FROM admins WHERE id = ?', [senderId]);
      return admin[0]?.name || 'Administrator';
    } else if (senderRole === 'staff') {
      const staff = await db.query('SELECT name FROM staff WHERE id = ?', [senderId]);
      return staff[0]?.name || 'Staff Member';
    }
    */
    
    // Mock implementation - replace with your actual DB code
    return `${senderRole.charAt(0).toUpperCase() + senderRole.slice(1)} User`;
  }

  async saveNotificationToDB(notificationData) {
    // Replace with your actual DB save logic
    // Example:
    /*
    await db.query(
      'INSERT INTO notifications (sender_id, sender_role, title, message, recipients, created_at) VALUES (?, ?, ?, ?, ?, ?)',
      [notificationData.senderId, notificationData.senderRole, notificationData.title, 
       notificationData.message, JSON.stringify(notificationData.recipients), new Date()]
    );
    */
    
    console.log('Notification saved to DB:', notificationData);
  }

  isValidEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  }

  async sendNotification({ senderId, senderRole, recipientStudentIds, title, message }) {
    try {
      // 1. Save notification to database
      await this.saveNotificationToDB({
        senderId,
        senderRole,
        title,
        message,
        recipients: recipientStudentIds,
        createdAt: new Date()
      });

      // 2. Get sender information
      const senderName = await this.getSenderInfo(senderId, senderRole);

      // 3. Get student email addresses
      const students = await this.getStudentEmailsByIds(recipientStudentIds);
      const validStudents = students.filter(student => 
        student.email && this.isValidEmail(student.email)
      );

      if (validStudents.length === 0) {
        console.warn('No valid email addresses found for notification recipients');
        return {
          success: true,
          message: 'Notification saved but no emails sent (no valid email addresses)',
          emailsSent: 0,
          totalRecipients: recipientStudentIds.length
        };
      }

      // 4. Send emails (batch process for better error handling)
      const emailResults = await this.sendBatchEmails({
        students: validStudents,
        title,
        message,
        senderName,
        senderRole
      });

      const successCount = emailResults.filter(result => result.success).length;
      const failedCount = emailResults.length - successCount;

      if (failedCount > 0) {
        console.error(`Failed to send ${failedCount} out of ${emailResults.length} emails`);
      }

      return {
        success: true,
        message: `Notification sent successfully`,
        emailsSent: successCount,
        emailsFailed: failedCount,
        totalRecipients: recipientStudentIds.length
      };

    } catch (error) {
      console.error('Notification service error:', error);
      throw new Error(`Failed to send notification: ${error.message}`);
    }
  }

  async sendBatchEmails({ students, title, message, senderName, senderRole }) {
    const emailPromises = students.map(async (student) => {
      try {
        await emailService.sendNotificationEmail({
          to: student.email,
          title,
          message,
          senderName,
          senderRole
        });
        return { success: true, studentId: student.id, email: student.email };
      } catch (error) {
        console.error(`Failed to send email to ${student.email}:`, error);
        return { success: false, studentId: student.id, email: student.email, error: error.message };
      }
    });

    return Promise.allSettled(emailPromises).then(results => 
      results.map(result => result.status === 'fulfilled' ? result.value : { 
        success: false, 
        error: result.reason?.message || 'Unknown error' 
      })
    );
  }
}

module.exports = new NotificationService();
