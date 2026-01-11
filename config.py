"""
Configuration settings for the IP tracking web server.
"""
import os
import secrets

class Config:
    """Application configuration."""

    # Flask settings
    DEBUG = True
    HOST = '0.0.0.0'  # Listen on all interfaces
    PORT = 5000

    # Database settings
    DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'visits.db')

    # Admin authentication
    # Change this to a secure random token in production
    ADMIN_TOKEN = os.getenv('ADMIN_TOKEN', 'change_me_' + secrets.token_hex(8))

    # Logging preferences (console logging disabled - use Discord instead)
    LOG_TO_CONSOLE = False
    CONSOLE_VERBOSE = False

    # Discord Webhook
    DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1446831459024240694/xhfxSUVoAhaD0Eysu150mnqY7dLz7Qfpulu6dOkm4KotxZ6xXD3LKLn3U47k6pbOGcEV"
    SEND_TO_DISCORD = True  # Enable/disable Discord notifications

    # Security settings
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max request size

    # Application info
    APP_NAME = "My Website!"
    APP_VERSION = "1.0.0"

# Create config instance
config = Config()

# Print admin token on startup for convenience
if __name__ == "__main__":
    print(f"Admin Token: {config.ADMIN_TOKEN}")
    print(f"Access admin panel at: http://localhost:{config.PORT}/admin?token={config.ADMIN_TOKEN}")
