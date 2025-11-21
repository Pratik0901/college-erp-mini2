require('dotenv').config();
const emailService = require('../services/emailService');
const notificationService = require('../services/notificationService');
const otpService = require('../services/otpService');

async function testEmailService() {
  console.log('🧪 Testing Email Service...\n');

  try {
    // Test connection
    console.log('1. Testing email service connection...');
    const isConnected = await emailService.testConnection();
    if (!isConnected) {
      throw new Error('Email service connection failed');
    }
    console.log('✅ Email service connection successful\n');

    // Test basic email
    console.log('2. Testing basic email...');
    await emailService.sendMail({
      to: 'test@example.com', // Change to your test email
      subject: 'Test Email',
      html: '<h1>Test Email</h1><p>This is a test email.</p>',
      text: 'Test Email - This is a test email.'
    });
    console.log('✅ Basic email test successful\n');

    // Test notification email
    console.log('3. Testing notification email...');
    await emailService.sendNotificationEmail({
      to: 'test@example.com', // Change to your test email
      title: 'Test Notification',
      message: 'This is a test notification message.\nIt can have multiple lines.',
      senderName: 'Test Admin',
      senderRole: 'admin'
    });
    console.log('✅ Notification email test successful\n');

    // Test OTP email
    console.log('4. Testing OTP email...');
    const otp = emailService.generateOTP();
    await emailService.sendOTPEmail({
      to: 'test@example.com', // Change to your test email
      otp,
      userName: 'Test User'
    });
    console.log(`✅ OTP email test successful (OTP: ${otp})\n`);

    console.log('🎉 All email tests passed!');

  } catch (error) {
    console.error('❌ Email test failed:', error.message);
    process.exit(1);
  }
}

async function testNotificationFlow() {
  console.log('\n📢 Testing Notification Flow...\n');

  try {
    const result = await notificationService.sendNotification({
      senderId: 1,
      senderRole: 'admin',
      recipientStudentIds: [1, 2, 3],
      title: 'Test Notification Flow',
      message: 'This is testing the complete notification flow including email sending.'
    });

    console.log('✅ Notification flow test result:', result);
  } catch (error) {
    console.error('❌ Notification flow test failed:', error.message);
  }
}

async function testOTPFlow() {
  console.log('\n🔐 Testing OTP Flow...\n');

  try {
    // Test OTP request
    console.log('1. Testing OTP request...');
    await otpService.requestPasswordReset('test@example.com');
    console.log('✅ OTP request successful\n');

    // Note: In a real test, you'd retrieve the OTP from your test database
    console.log('2. OTP verification test skipped (requires actual OTP from email)');
    
  } catch (error) {
    console.error('❌ OTP flow test failed:', error.message);
  }
}

async function runAllTests() {
  try {
    await testEmailService();
    await testNotificationFlow();
    await testOTPFlow();
    
    console.log('\n🎉 All tests completed!');
    process.exit(0);
  } catch (error) {
    console.error('\n❌ Test suite failed:', error.message);
    process.exit(1);
  }
}

if (require.main === module) {
  runAllTests();
}

module.exports = {
  testEmailService,
  testNotificationFlow,
  testOTPFlow
};
