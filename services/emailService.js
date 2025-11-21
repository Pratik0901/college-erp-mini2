require('dotenv').config();
const nodemailer = require('nodemailer');
const crypto = require('crypto');

class EmailService {
  constructor() {
    this.transporter = this.createTransporter();
  }

  createTransporter() {
    // Choose authentication method based on available env vars
    if (process.env.EMAIL_APP_PASSWORD) {
      // App Password method
      return nodemailer.createTransporter({
        service: 'gmail',
        auth: {
          user: process.env.EMAIL_FROM,
          pass: process.env.EMAIL_APP_PASSWORD,
        },
        pool: true,
        maxConnections: 5,
        maxMessages: 100,
      });
    } else if (process.env.EMAIL_CLIENT_ID && process.env.EMAIL_CLIENT_SECRET) {
      // OAuth2 method
      return nodemailer.createTransporter({
        service: 'gmail',
        auth: {
          type: 'OAuth2',
          user: process.env.EMAIL_FROM,
          clientId: process.env.EMAIL_CLIENT_ID,
          clientSecret: process.env.EMAIL_CLIENT_SECRET,
          refreshToken: process.env.EMAIL_REFRESH_TOKEN,
        },
        pool: true,
        maxConnections: 5,
        maxMessages: 100,
      });
    } else {
      throw new Error('Email configuration missing. Please set either EMAIL_APP_PASSWORD or OAuth2 credentials.');
    }
  }

  async sendMail({ to, subject, html, text, attachments = [] }) {
    const mailOptions = {
      from: `"College Notification System" <${process.env.EMAIL_FROM}>`,
      to: Array.isArray(to) ? to.join(', ') : to,
      subject,
      text,
      html,
      attachments,
    };

    try {
      const info = await this.transporter.sendMail(mailOptions);
      console.log(`Email sent successfully: ${info.messageId}`);
      return { success: true, messageId: info.messageId };
    } catch (error) {
      console.error('Email send error:', error);
      throw error;
    }
  }

  async sendNotificationEmail({ to, title, message, senderName, senderRole }) {
    const html = this.generateNotificationTemplate({
      title,
      message,
      senderName,
      senderRole,
    });

    const text = `
${title}

${message}

Sent by: ${senderName} (${senderRole})

View in portal: ${process.env.FRONTEND_URL}/notifications
    `.trim();

    return this.sendMail({
      to,
      subject: `Notification: ${title}`,
      html,
      text,
    });
  }

  async sendOTPEmail({ to, otp, userName = '' }) {
    const html = this.generateOTPTemplate({ otp, userName });
    const text = `
Hi ${userName},

Your password reset OTP is: ${otp}

This OTP will expire in 10 minutes.

If you did not request this password reset, please ignore this email.
    `.trim();

    return this.sendMail({
      to,
      subject: 'Password Reset OTP - College Portal',
      html,
      text,
    });
  }

  generateNotificationTemplate({ title, message, senderName, senderRole }) {
    return `
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>New Notification</title>
  <style>
    body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }
    .header { background: #007bff; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }
    .content { background: #f8f9fa; padding: 30px; border: 1px solid #dee2e6; }
    .notification-body { background: white; padding: 20px; border-radius: 5px; margin: 15px 0; border-left: 4px solid #007bff; }
    .footer { background: #6c757d; color: white; padding: 15px; text-align: center; border-radius: 0 0 8px 8px; font-size: 0.9em; }
    .btn { display: inline-block; padding: 12px 24px; background: #007bff; color: white; text-decoration: none; border-radius: 5px; margin: 15px 0; }
    .sender-info { background: #e9ecef; padding: 10px; border-radius: 5px; margin-top: 15px; font-size: 0.9em; }
  </style>
</head>
<body>
  <div class="header">
    <h1>📢 New Notification</h1>
  </div>
  
  <div class="content">
    <h2>${title}</h2>
    
    <div class="notification-body">
      <p>${message.replace(/\n/g, '<br>')}</p>
    </div>
    
    <div class="sender-info">
      <strong>Sent by:</strong> ${senderName} (${senderRole})
    </div>
    
    <div style="text-align: center; margin: 20px 0;">
      <a href="${process.env.FRONTEND_URL}/notifications" class="btn">View in Portal</a>
    </div>
  </div>
  
  <div class="footer">
    <p>This is an automated email from College Notification System.<br>
    Please do not reply to this email.</p>
  </div>
</body>
</html>
    `;
  }

  generateOTPTemplate({ otp, userName }) {
    return `
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Password Reset OTP</title>
  <style>
    body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }
    .header { background: #dc3545; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }
    .content { background: #f8f9fa; padding: 30px; border: 1px solid #dee2e6; }
    .otp-box { background: white; padding: 20px; border-radius: 5px; margin: 20px 0; text-align: center; border: 2px solid #dc3545; }
    .otp { font-size: 36px; font-weight: bold; color: #dc3545; letter-spacing: 8px; margin: 10px 0; }
    .footer { background: #6c757d; color: white; padding: 15px; text-align: center; border-radius: 0 0 8px 8px; font-size: 0.9em; }
    .warning { background: #fff3cd; border: 1px solid #ffeaa7; color: #856404; padding: 15px; border-radius: 5px; margin: 15px 0; }
  </style>
</head>
<body>
  <div class="header">
    <h1>🔐 Password Reset Request</h1>
  </div>
  
  <div class="content">
    <p>Hi ${userName},</p>
    
    <p>You have requested to reset your password. Please use the following One-Time Password (OTP) to proceed:</p>
    
    <div class="otp-box">
      <div class="otp">${otp}</div>
      <p><small>Enter this code to reset your password</small></p>
    </div>
    
    <div class="warning">
      <p><strong>Important:</strong></p>
      <ul>
        <li>This OTP is valid for <strong>10 minutes only</strong></li>
        <li>Do not share this code with anyone</li>
        <li>If you did not request this, please ignore this email</li>
      </ul>
    </div>
  </div>
  
  <div class="footer">
    <p>This is an automated email from College Portal.<br>
    For support, contact your system administrator.</p>
  </div>
</body>
</html>
    `;
  }

  // Generate secure OTP
  generateOTP() {
    return crypto.randomInt(100000, 999999).toString();
  }

  // Hash OTP for storage
  hashOTP(otp) {
    return crypto.createHash('sha256').update(otp).digest('hex');
  }

  // Verify OTP
  verifyOTP(providedOTP, storedHash) {
    const providedHash = this.hashOTP(providedOTP);
    return providedHash === storedHash;
  }

  async testConnection() {
    try {
      await this.transporter.verify();
      console.log('Email service is ready');
      return true;
    } catch (error) {
      console.error('Email service connection failed:', error);
      return false;
    }
  }
}

module.exports = new EmailService();
