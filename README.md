# College Notification System with Email Integration

A complete notification system that sends both in-app notifications and emails to students when admin/staff create notifications.

## Features

- 📧 Email notifications via Gmail SMTP
- 🔐 Secure authentication (App Password or OAuth2)
- 📱 OTP-based password reset
- 🎨 Beautiful HTML email templates
- ⚡ Batch email sending with error handling
- 🛡️ Security best practices
- 🧪 Testing utilities

## Quick Setup

### 1. Install Dependencies

```bash
npm install
```

### 2. Environment Configuration

Copy `.env.example` to `.env` and configure your Gmail settings:

```bash
cp .env.example .env
```

Choose one authentication method:

#### Option A: App Password (Recommended for development)

1. Enable 2-Step Verification on `pratikmg09@gmail.com`
2. Generate an App Password: Google Account → Security → App passwords → Create app password for Mail
3. Add to `.env`:

```env
EMAIL_FROM=pratikmg09@gmail.com
EMAIL_APP_PASSWORD=your_16_character_app_password
```

#### Option B: OAuth2 (Recommended for production)

1. Create Google Cloud project
2. Enable Gmail API
3. Create OAuth 2.0 Client ID credentials
4. Get refresh token via OAuth 2 Playground
5. Add to `.env`:

```env
EMAIL_FROM=pratikmg09@gmail.com
EMAIL_CLIENT_ID=your-client-id
EMAIL_CLIENT_SECRET=your-client-secret
EMAIL_REFRESH_TOKEN=your-refresh-token
```

### 3. Test Email Configuration

```bash
npm run test-email
```

### 4. Integration

Add to your main app:

```javascript
const notificationRoutes = require('./routes/notifications');
const authRoutes = require('./routes/auth');

app.use('/api/notifications', notificationRoutes);
app.use('/api/auth', authRoutes);
```

## API Endpoints

### Send Notification

```http
POST /api/notifications/send
Content-Type: application/json

{
  "senderId": 1,
  "senderRole": "admin",
  "recipientStudentIds": [1, 2, 3],
  "title": "Important Update",
  "message": "Please check your schedule for tomorrow."
}
```

### Request Password Reset

```http
POST /api/auth/forgot-password
Content-Type: application/json

{
  "email": "student@example.com"
}
```

### Verify OTP

```http
POST /api/auth/verify-otp
Content-Type: application/json

{
  "email": "student@example.com",
  "otp": "123456"
}
```

## Database Integration

Update these functions in `services/notificationService.js` and `services/otpService.js`:

```javascript
// Replace mock implementations with your actual DB queries
async getStudentEmailsByIds(studentIds) {
  // Your DB query to get student emails
}

async getSenderInfo(senderId, senderRole) {
  // Your DB query to get sender name
}

async saveNotificationToDB(notificationData) {
  // Your DB save logic
}
```

## Email Templates

The system includes beautiful HTML email templates for:

- **Notifications**: Professional layout with sender info and portal links
- **OTP**: Secure styling with expiry warnings

Templates are in `services/emailService.js` and can be customized.

## Security Features

- Environment variable configuration
- Email address validation
- OTP expiry (10 minutes)
- Rate limiting ready
- No sensitive data in API responses
- Secure OTP hashing

## Testing

### Test Email Functionality
```bash
npm run test-email
```

### Test Individual Components
```javascript
const emailService = require('./services/emailService');
const notificationService = require('./services/notificationService');
const otpService = require('./services/otpService');

// Test connection
await emailService.testConnection();

// Send test notification
await notificationService.sendNotification({...});

// Test OTP flow
await otpService.requestPasswordReset('test@example.com');
```

## Production Considerations

### High Volume Sending

For large numbers of students, consider:

- **Transactional Email Services**: SendGrid, Mailgun, Amazon SES
- **Queue System**: Redis + Bull for async email processing
- **Rate Limiting**: Respect Gmail's sending limits

### Monitoring

- Log email failures for retry
- Monitor bounce rates
- Track delivery status
- Set up alerting for service failures

### Scaling

```javascript
// Example with Bull queue
const Queue = require('bull');
const emailQueue = new Queue('email sending');

emailQueue.process(async (job) => {
  const { emailData } = job.data;
  await emailService.sendMail(emailData);
});

// Queue emails instead of sending directly
await emailQueue.add('send-notification', { emailData });
```

## Troubleshooting

### Common Issues

1. **Authentication Failed**
   - Verify App Password is correct (16 characters, no spaces)
   - Ensure 2FA is enabled on Gmail account
   - Check OAuth2 credentials if using OAuth2

2. **Emails Not Sending**
   - Run connection test: `await emailService.testConnection()`
   - Check Gmail sending limits
   - Verify recipient email addresses

3. **Rate Limiting**
   - Gmail limits: ~2,000 emails/day for regular accounts
   - Implement queue system for high volume
   - Consider transactional email service

### Debug Mode

Set `NODE_ENV=development` to see detailed error messages in API responses.

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review Gmail SMTP documentation
3. Test with the provided test scripts
4. Check server logs for detailed error messages

## License

MIT License - feel free to use in your projects.
