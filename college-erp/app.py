"""
Main entry point for College ERP System
Run this file from the college-erp root directory
"""
import sys
import os
from pathlib import Path

# Add Backend directory to Python path
backend_dir = Path(__file__).parent / 'Backend'
sys.path.insert(0, str(backend_dir))

# Import the Flask app from Backend
try:
    from Backend.app import app, logger, UPLOAD_FOLDER
    
    if __name__ == '__main__':
        logger.info("="*60)
        logger.info("🚀 Starting College ERP Backend Server")
        logger.info("="*60)
        logger.info(f"📍 Server: http://127.0.0.1:5000")
        logger.info(f"📁 Upload Folder: {UPLOAD_FOLDER}")
        logger.info(f"🗄️  Database: college_erp @ 127.0.0.1")
        logger.info(f"📂 Working Directory: {Path.cwd()}")
        logger.info(f"📂 Backend Directory: {backend_dir}")
        logger.info("="*60)
        
        try:
            # Run the Flask application
            app.run(debug=True, host='127.0.0.1', port=5000, use_reloader=True)
        except Exception as e:
            logger.error(f"❌ Failed to start server: {e}")
            raise
            
except ImportError as e:
    print(f"❌ Error: Could not import Backend application")
    print(f"   Make sure the Backend folder exists and contains app.py")
    print(f"   Error details: {e}")
    sys.exit(1)
