const express = require('express');
const router = express.Router();
const notificationService = require('../services/notificationService');

// Middleware to validate request (add your authentication middleware)
const validateRequest = (req, res, next) => {
  const { senderId, senderRole, recipientStudentIds, title, message } = req.body;
  
  if (!senderId || !senderRole || !recipientStudentIds || !title || !message) {
    return res.status(400).json({
      success: false,
      message: 'Missing required fields: senderId, senderRole, recipientStudentIds, title, message'
    });
  }

  if (!Array.isArray(recipientStudentIds) || recipientStudentIds.length === 0) {
    return res.status(400).json({
      success: false,
      message: 'recipientStudentIds must be a non-empty array'
    });
  }

  if (!['admin', 'staff'].includes(senderRole)) {
    return res.status(400).json({
      success: false,
      message: 'senderRole must be either "admin" or "staff"'
    });
  }

  next();
};

// Send notification (saves to DB, creates in-app notification, and sends email)
router.post('/send', validateRequest, async (req, res) => {
  try {
    const { senderId, senderRole, recipientStudentIds, title, message } = req.body;

    const result = await notificationService.sendNotification({
      senderId,
      senderRole,
      recipientStudentIds,
      title,
      message
    });

    res.json(result);

  } catch (error) {
    console.error('Send notification error:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to send notification',
      error: process.env.NODE_ENV === 'development' ? error.message : undefined
    });
  }
});

// Test email sending (for development/testing)
router.post('/test-email', async (req, res) => {
  try {
    const { to, title = 'Test Notification', message = 'This is a test message.' } = req.body;
    
    if (!to) {
      return res.status(400).json({
        success: false,
        message: 'Email address (to) is required'
      });
    }

    const emailService = require('../services/emailService');
    await emailService.sendNotificationEmail({
      to,
      title,
      message,
      senderName: 'Test Admin',
      senderRole: 'admin'
    });

    res.json({
      success: true,
      message: 'Test email sent successfully'
    });

  } catch (error) {
    console.error('Test email error:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to send test email',
      error: process.env.NODE_ENV === 'development' ? error.message : undefined
    });
  }
});

module.exports = router;
