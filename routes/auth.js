const express = require('express');
const router = express.Router();
const otpService = require('../services/otpService');

// Request password reset OTP
router.post('/forgot-password', async (req, res) => {
  try {
    const { email } = req.body;
    
    if (!email) {
      return res.status(400).json({
        success: false,
        message: 'Email is required'
      });
    }

    // Validate email format
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
      return res.status(400).json({
        success: false,
        message: 'Invalid email format'
      });
    }

    const result = await otpService.requestPasswordReset(email);
    res.json(result);

  } catch (error) {
    console.error('Forgot password error:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to process password reset request',
      error: process.env.NODE_ENV === 'development' ? error.message : undefined
    });
  }
});

// Verify OTP for password reset
router.post('/verify-otp', async (req, res) => {
  try {
    const { email, otp } = req.body;
    
    if (!email || !otp) {
      return res.status(400).json({
        success: false,
        message: 'Email and OTP are required'
      });
    }

    // Validate OTP format (6 digits)
    if (!/^\d{6}$/.test(otp)) {
      return res.status(400).json({
        success: false,
        message: 'OTP must be 6 digits'
      });
    }

    const result = await otpService.verifyOTP(email, otp);
    
    if (result.success) {
      // In a real application, you might generate a temporary token here
      // that allows the user to reset their password
      res.json({
        ...result,
        resetToken: 'generate-secure-token-here' // Generate actual secure token
      });
    } else {
      res.status(400).json(result);
    }

  } catch (error) {
    console.error('Verify OTP error:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to verify OTP',
      error: process.env.NODE_ENV === 'development' ? error.message : undefined
    });
  }
});

// Test OTP sending (for development)
router.post('/test-otp', async (req, res) => {
  try {
    const { email } = req.body;
    
    if (!email) {
      return res.status(400).json({
        success: false,
        message: 'Email is required'
      });
    }

    const emailService = require('../services/emailService');
    const otp = emailService.generateOTP();
    
    await emailService.sendOTPEmail({
      to: email,
      otp,
      userName: 'Test User'
    });

    res.json({
      success: true,
      message: 'Test OTP sent successfully',
      otp: process.env.NODE_ENV === 'development' ? otp : undefined // Only show in development
    });

  } catch (error) {
    console.error('Test OTP error:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to send test OTP',
      error: process.env.NODE_ENV === 'development' ? error.message : undefined
    });
  }
});

module.exports = router;
