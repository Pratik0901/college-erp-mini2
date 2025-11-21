const emailService = require('./emailService');

class OTPService {
  // Mock OTP storage - replace with your actual database
  // In production, store in Redis or database table with expiry
  otpStorage = new Map();

  async getUserByEmail(email) {
    // Replace with your actual DB query
    // Should return user object or null
    /*
    const user = await db.query('SELECT * FROM users WHERE email = ?', [email]);
    return user[0] || null;
    */
    
    // Mock implementation - replace with your actual DB code
    return {
      id: 1,
      email: email,
      name: 'Test User'
    };
  }

  async storeOTP(userId, otpHash, expiresAt) {
    // Replace with your actual DB storage
    // Example:
    /*
    await db.query(
      'INSERT INTO password_reset_otps (user_id, otp_hash, expires_at) VALUES (?, ?, ?) ON DUPLICATE KEY UPDATE otp_hash = ?, expires_at = ?',
      [userId, otpHash, expiresAt, otpHash, expiresAt]
    );
    */
    
    // Mock storage - replace with actual DB
    this.otpStorage.set(userId.toString(), { otpHash, expiresAt });
  }

  async getStoredOTP(userId) {
    // Replace with your actual DB query
    // Should return { otpHash, expiresAt } or null
    /*
    const result = await db.query('SELECT otp_hash, expires_at FROM password_reset_otps WHERE user_id = ?', [userId]);
    return result[0] || null;
    */
    
    // Mock storage - replace with actual DB
    return this.otpStorage.get(userId.toString()) || null;
  }

  async clearOTP(userId) {
    // Replace with your actual DB delete
    /*
    await db.query('DELETE FROM password_reset_otps WHERE user_id = ?', [userId]);
    */
    
    // Mock storage - replace with actual DB
    this.otpStorage.delete(userId.toString());
  }

  async requestPasswordReset(email) {
    try {
      // 1. Verify user exists
      const user = await this.getUserByEmail(email);
      if (!user) {
        // For security, don't reveal if email exists or not
        return {
          success: true,
          message: 'If the email exists, an OTP has been sent.'
        };
      }

      // 2. Generate OTP
      const otp = emailService.generateOTP();
      const otpHash = emailService.hashOTP(otp);
      const expiresAt = new Date(Date.now() + 10 * 60 * 1000); // 10 minutes

      // 3. Store OTP in database
      await this.storeOTP(user.id, otpHash, expiresAt);

      // 4. Send OTP email
      await emailService.sendOTPEmail({
        to: email,
        otp,
        userName: user.name || ''
      });

      console.log(`Password reset OTP sent to ${email}`);
      
      return {
        success: true,
        message: 'If the email exists, an OTP has been sent.',
        // Don't include sensitive info in response
      };

    } catch (error) {
      console.error('Password reset request error:', error);
      throw new Error('Failed to process password reset request');
    }
  }

  async verifyOTP(email, providedOTP) {
    try {
      // 1. Get user
      const user = await this.getUserByEmail(email);
      if (!user) {
        return { success: false, message: 'Invalid request' };
      }

      // 2. Get stored OTP
      const storedOTPData = await this.getStoredOTP(user.id);
      if (!storedOTPData) {
        return { success: false, message: 'No OTP request found or OTP expired' };
      }

      // 3. Check expiry
      if (new Date() > storedOTPData.expiresAt) {
        await this.clearOTP(user.id);
        return { success: false, message: 'OTP has expired' };
      }

      // 4. Verify OTP
      const isValid = emailService.verifyOTP(providedOTP, storedOTPData.otpHash);
      if (!isValid) {
        return { success: false, message: 'Invalid OTP' };
      }

      // 5. OTP is valid - clear it and return success
      await this.clearOTP(user.id);
      
      return {
        success: true,
        message: 'OTP verified successfully',
        userId: user.id
      };

    } catch (error) {
      console.error('OTP verification error:', error);
      throw new Error('Failed to verify OTP');
    }
  }
}

module.exports = new OTPService();
