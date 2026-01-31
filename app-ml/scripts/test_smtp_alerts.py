#!/usr/bin/env python3
"""
SMTP Alerting Verification Script

This script tests SMTP email configuration for Airflow alerts.
It sends a test email to verify the SMTP setup is working correctly.

Usage:
    python scripts/test_smtp_alerts.py [--to email@example.com]
"""

import argparse
import logging
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_smtp_config():
    """Get SMTP configuration from environment variables."""
    config = {
        'host': os.getenv('AIRFLOW__SMTP__SMTP_HOST', 'smtp.gmail.com'),
        'port': int(os.getenv('AIRFLOW__SMTP__SMTP_PORT', '587')),
        'starttls': os.getenv('AIRFLOW__SMTP__SMTP_STARTTLS', 'true').lower() == 'true',
        'ssl': os.getenv('AIRFLOW__SMTP__SMTP_SSL', 'false').lower() == 'true',
        'user': os.getenv('AIRFLOW__SMTP__SMTP_USER'),
        'password': os.getenv('AIRFLOW__SMTP__SMTP_PASSWORD'),
        'from_email': os.getenv('AIRFLOW__SMTP__SMTP_MAIL_FROM', 'airflow@demand-forecasting.local')
    }
    
    # Check required fields
    missing_fields = []
    if not config['user']:
        missing_fields.append('AIRFLOW__SMTP__SMTP_USER')
    if not config['password']:
        missing_fields.append('AIRFLOW__SMTP__SMTP_PASSWORD')
    
    if missing_fields:
        logger.error(f"❌ Missing required SMTP configuration: {missing_fields}")
        logger.info("💡 Add these to your .env file:")
        for field in missing_fields:
            logger.info(f"   {field}=your_value")
        return None
    
    return config

def test_smtp_connection(config):
    """Test SMTP server connection."""
    logger.info(f"🔍 Testing SMTP connection to {config['host']}:{config['port']}")
    
    try:
        # Create SMTP session
        if config['ssl']:
            server = smtplib.SMTP_SSL(config['host'], config['port'])
        else:
            server = smtplib.SMTP(config['host'], config['port'])
            
        # Enable debug output
        server.set_debuglevel(1)
        
        # Start TLS if required
        if config['starttls'] and not config['ssl']:
            server.starttls()
            logger.info("✅ TLS started")
        
        # Login
        server.login(config['user'], config['password'])
        logger.info("✅ SMTP login successful")
        
        # Close connection
        server.quit()
        logger.info("✅ SMTP connection test passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ SMTP connection failed: {e}")
        return False

def send_test_email(config, to_email):
    """Send a test email."""
    logger.info(f"📧 Sending test email to {to_email}")
    
    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = config['from_email']
        msg['To'] = to_email
        msg['Subject'] = "[TEST] Demand Forecasting - SMTP Alert Verification"
        
        # Email body
        body = f"""
        <html>
        <body>
            <h2>🎉 SMTP Alert Test Successful!</h2>
            
            <p>This is a test email from the Demand Forecasting ML system.</p>
            
            <h3>Test Details:</h3>
            <ul>
                <li><strong>Timestamp:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</li>
                <li><strong>SMTP Host:</strong> {config['host']}</li>
                <li><strong>SMTP Port:</strong> {config['port']}</li>
                <li><strong>TLS:</strong> {'Enabled' if config['starttls'] else 'Disabled'}</li>
                <li><strong>SSL:</strong> {'Enabled' if config['ssl'] else 'Disabled'}</li>
            </ul>
            
            <h3>Next Steps:</h3>
            <p>If you received this email, your SMTP configuration is working correctly!</p>
            <p>The system can now send alerts for:</p>
            <ul>
                <li>Dataset monitoring (stale data alerts)</li>
                <li>DAG failures</li>
                <li>Data drift detection</li>
                <li>Automated retraining notifications</li>
            </ul>
            
            <hr>
            <p><small>This is an automated test from the Demand Forecasting ML System.</small></p>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(body, 'html'))
        
        # Create SMTP session
        if config['ssl']:
            server = smtplib.SMTP_SSL(config['host'], config['port'])
        else:
            server = smtplib.SMTP(config['host'], config['port'])
        
        # Start TLS if required
        if config['starttls'] and not config['ssl']:
            server.starttls()
        
        # Login and send
        server.login(config['user'], config['password'])
        server.send_message(msg)
        server.quit()
        
        logger.info(f"✅ Test email sent successfully to {to_email}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to send test email: {e}")
        return False

def test_airflow_email_function():
    """Test Airflow's email sending function."""
    logger.info("🔍 Testing Airflow email function...")
    
    try:
        from airflow.utils.email import send_email
        
        # Test email content
        subject = "[AIRFLOW TEST] SMTP Alert Verification"
        html_content = f"""
        <h2>Airflow Email Test</h2>
        <p>This is a test sent using Airflow's email utility.</p>
        <p>Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        """
        
        # Get alert emails from environment
        alert_emails = os.getenv("AIRFLOW_ALERT_EMAIL", "test@example.com").split(",")
        
        # Send test email
        send_email(
            to=alert_emails,
            subject=subject,
            html_content=html_content
        )
        
        logger.info(f"✅ Airflow email function test successful. Sent to: {alert_emails}")
        return True
        
    except ImportError:
        logger.warning("⚠️ Airflow not available in this environment")
        return None
    except Exception as e:
        logger.error(f"❌ Airflow email function test failed: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Test SMTP alerting configuration")
    parser.add_argument("--to", help="Override recipient email for testing")
    args = parser.parse_args()
    
    logger.info("🚀 Starting SMTP Alert Verification")
    logger.info("=" * 50)
    
    # Get SMTP configuration
    config = get_smtp_config()
    if not config:
        return 1
    
    # Test connection
    logger.info("\n📋 Step 1: Testing SMTP Connection")
    logger.info("-" * 30)
    connection_ok = test_smtp_connection(config)
    
    if not connection_ok:
        logger.error("💥 SMTP connection failed. Please check your configuration.")
        return 1
    
    # Send test email
    logger.info("\n📋 Step 2: Sending Test Email")
    logger.info("-" * 30)
    
    # Determine recipient
    if args.to:
        recipient = args.to
    else:
        # Use alert emails from environment
        recipient = os.getenv("AIRFLOW_ALERT_EMAIL", "test@example.com").split(",")[0]
    
    email_ok = send_test_email(config, recipient)
    
    # Test Airflow email function (if available)
    logger.info("\n📋 Step 3: Testing Airflow Email Function")
    logger.info("-" * 30)
    airflow_ok = test_airflow_email_function()
    
    # Summary
    logger.info("\n" + "=" * 50)
    logger.info("📊 SMTP VERIFICATION SUMMARY")
    logger.info("=" * 50)
    
    results = [
        ("SMTP Connection", connection_ok),
        ("Test Email", email_ok),
    ]
    
    if airflow_ok is not None:
        results.append(("Airflow Email Function", airflow_ok))
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{test_name}: {status}")
        if result:
            passed += 1
    
    logger.info(f"\n🎯 Overall: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 SMTP alerting is working correctly!")
        logger.info("📧 The system can now send email alerts for monitoring and failures.")
        return 0
    else:
        logger.error("💥 Some SMTP tests failed. Please check the configuration.")
        logger.info("📖 Common issues:")
        logger.info("   - Incorrect SMTP username/password")
        logger.info("   - Firewall blocking SMTP ports")
        logger.info("   - SMTP server requiring app-specific passwords")
        logger.info("   - TLS/SSL configuration mismatch")
        return 1

if __name__ == "__main__":
    exit(main())
