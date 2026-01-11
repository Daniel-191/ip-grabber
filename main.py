"""
Educational IP Tracking Web Server
A Flask application that logs visitor IP addresses for educational purposes.
"""
from flask import Flask, request, render_template, jsonify, redirect, url_for, send_file
from datetime import datetime
import os
import requests
import threading
from config import config
from database import init_db, log_visit, get_visits, get_stats, export_to_csv

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = config.MAX_CONTENT_LENGTH


def get_client_ip(request):
    """
    Extract the real client IP address, handling proxies and tunneling services.

    When using ngrok or other tunneling services, the actual client IP is passed
    in the X-Forwarded-For header. This function handles that case.

    Priority order:
    1. X-Forwarded-For (first IP in chain) - for proxies/ngrok
    2. X-Real-IP - alternative proxy header
    3. request.remote_addr - direct connection

    Args:
        request: Flask request object

    Returns:
        str: The client's IP address
    """
    # X-Forwarded-For can contain multiple IPs: "client, proxy1, proxy2"
    # We want the first one (original client)
    forwarded_for = request.headers.get('X-Forwarded-For')
    if forwarded_for:
        # Take the first IP from the chain
        return forwarded_for.split(',')[0].strip()

    # Alternative header used by some proxies
    real_ip = request.headers.get('X-Real-IP')
    if real_ip:
        return real_ip

    # Direct connection (no proxy)
    return request.remote_addr


def send_discord_webhook(ip_address, user_agent, referer, path, method, forwarded_for, timestamp):
    """
    Send visitor information to Discord webhook with a nice embed.
    Runs in a separate thread to avoid blocking the request.

    Args:
        ip_address: Visitor's IP address
        user_agent: Browser/device information
        referer: Where the visitor came from
        path: URL path accessed
        method: HTTP method
        forwarded_for: Full X-Forwarded-For header
        timestamp: ISO 8601 formatted timestamp
    """
    if not config.SEND_TO_DISCORD or not config.DISCORD_WEBHOOK_URL:
        return

    try:
        # Parse user agent to get browser info
        browser_info = "Unknown"
        os_info = "Unknown"

        if user_agent:
            ua_lower = user_agent.lower()
            # Detect browser
            if 'chrome' in ua_lower and 'edg' not in ua_lower:
                browser_info = "Chrome"
            elif 'firefox' in ua_lower:
                browser_info = "Firefox"
            elif 'safari' in ua_lower and 'chrome' not in ua_lower:
                browser_info = "Safari"
            elif 'edg' in ua_lower:
                browser_info = "Edge"
            elif 'opera' in ua_lower or 'opr' in ua_lower:
                browser_info = "Opera"

            # Detect OS
            if 'windows' in ua_lower:
                os_info = "Windows"
            elif 'mac' in ua_lower:
                os_info = "macOS"
            elif 'linux' in ua_lower:
                os_info = "Linux"
            elif 'android' in ua_lower:
                os_info = "Android"
            elif 'iphone' in ua_lower or 'ipad' in ua_lower:
                os_info = "iOS"

        # Format timestamp for Discord
        dt = datetime.fromisoformat(timestamp)
        formatted_time = dt.strftime('%Y-%m-%d %H:%M:%S')
        unix_timestamp = int(dt.timestamp())

        # Create embed
        embed = {
            "title": "🌐 New Visitor Detected!",
            "color": 0x5865F2,  # Discord blurple color
            "fields": [
                {
                    "name": "🌍 IP Address",
                    "value": f"`{ip_address}`",
                    "inline": True
                },
                {
                    "name": "🕐 Visit Time",
                    "value": f"<t:{unix_timestamp}:F>",
                    "inline": True
                },
                {
                    "name": "🌐 Browser",
                    "value": browser_info,
                    "inline": True
                },
                {
                    "name": "💻 Operating System",
                    "value": os_info,
                    "inline": True
                },
                {
                    "name": "📍 Path Visited",
                    "value": f"`{path}`",
                    "inline": True
                },
                {
                    "name": "🔧 HTTP Method",
                    "value": method,
                    "inline": True
                }
            ],
            "footer": {
                "text": "IP Tracker • Educational Purpose"
            },
            "timestamp": timestamp
        }

        # Add referer if available
        if referer:
            embed["fields"].append({
                "name": "🔗 Referrer",
                "value": referer[:1024],  # Discord field value limit
                "inline": False
            })
        else:
            embed["fields"].append({
                "name": "🔗 Referrer",
                "value": "Direct Visit (No Referrer)",
                "inline": False
            })

        # Add full user agent
        if user_agent:
            embed["fields"].append({
                "name": "🖥️ Full User Agent",
                "value": f"```{user_agent[:1000]}```",  # Discord has limits
                "inline": False
            })

        # Add X-Forwarded-For if available
        if forwarded_for:
            embed["fields"].append({
                "name": "🔄 Proxy Chain (X-Forwarded-For)",
                "value": f"`{forwarded_for}`",
                "inline": False
            })

        # Prepare the webhook payload
        # Send IP both in message content AND in embed
        payload = {
            "content": f"**New Visit from IP:** `{ip_address}`",
            "embeds": [embed],
            "username": "IP Tracker Bot"
        }

        # Send to Discord
        response = requests.post(
            config.DISCORD_WEBHOOK_URL,
            json=payload,
            timeout=10
        )

        if response.status_code != 204:
            print(f"[WARNING] Discord webhook returned status {response.status_code}")

    except Exception as e:
        print(f"[ERROR] Failed to send Discord webhook: {e}")


@app.before_request
def log_visitor():
    """
    Middleware that runs before each request to log visitor information.
    This automatically captures all visits to any route.
    """
    # Don't log static file requests
    if request.path.startswith('/static'):
        return

    # Extract visitor information
    ip_address = get_client_ip(request)
    timestamp = datetime.now().isoformat()
    user_agent = request.headers.get('User-Agent')
    referer = request.headers.get('Referer')
    path = request.path
    method = request.method
    forwarded_for = request.headers.get('X-Forwarded-For')

    # Log to database
    try:
        log_visit(
            ip_address=ip_address,
            timestamp=timestamp,
            user_agent=user_agent,
            referer=referer,
            request_path=path,
            request_method=method,
            forwarded_for=forwarded_for
        )
    except Exception as e:
        print(f"Error logging visit to database: {e}")

    # Console logging removed - check Discord for visitor notifications

    # Send to Discord webhook in a separate thread (non-blocking)
    if config.SEND_TO_DISCORD:
        webhook_thread = threading.Thread(
            target=send_discord_webhook,
            args=(ip_address, user_agent, referer, path, method, forwarded_for, timestamp),
            daemon=True
        )
        webhook_thread.start()


@app.route('/')
def index():
    """Landing page that visitors see."""
    return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hello</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            background: #ffffff;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
        }
        .message {
            font-size: 48px;
            color: #333;
            text-align: center;
            animation: fadeIn 1s ease-in;
        }
        @keyframes fadeIn {
            from {
                opacity: 0;
                transform: translateY(-20px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
    </style>
</head>
<body>
    <div class="message">hello</div>
</body>
</html>'''


@app.route('/admin')
def admin():
    """
    Admin panel for viewing logged visitor data.
    Protected by token authentication.
    """
    # Check authentication token
    token = request.args.get('token')
    if token != config.ADMIN_TOKEN:
        return "Unauthorized. Please provide a valid token.", 401

    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = 50
    offset = (page - 1) * per_page

    # Get visits and statistics
    visits = get_visits(limit=per_page, offset=offset)
    stats = get_stats()

    return render_template('admin.html', visits=visits, stats=stats, page=page, token=token)


@app.route('/api/stats')
def api_stats():
    """
    JSON endpoint for getting visit statistics.
    """
    # Optional token protection (you can enable this if desired)
    # token = request.args.get('token')
    # if token != config.ADMIN_TOKEN:
    #     return jsonify({'error': 'Unauthorized'}), 401

    stats = get_stats()
    return jsonify(stats)


@app.route('/api/visits')
def api_visits():
    """
    JSON endpoint for getting recent visits.
    """
    limit = request.args.get('limit', 20, type=int)
    limit = min(limit, 100)  # Cap at 100

    visits = get_visits(limit=limit)
    return jsonify(visits)


@app.route('/admin/export')
def export():
    """
    Export all visit data to CSV file.
    Requires admin token.
    """
    token = request.args.get('token')
    if token != config.ADMIN_TOKEN:
        return "Unauthorized", 401

    # Create exports directory if it doesn't exist
    export_dir = os.path.join(os.path.dirname(__file__), 'exports')
    os.makedirs(export_dir, exist_ok=True)

    # Generate filename with timestamp
    filename = f"visits_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    filepath = os.path.join(export_dir, filename)

    # Export to CSV
    try:
        count = export_to_csv(filepath)
        return send_file(
            filepath,
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        return f"Error exporting data: {e}", 500


@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'app_name': config.APP_NAME,
        'version': config.APP_VERSION,
        'timestamp': datetime.now().isoformat()
    })


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return index(), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    return "Internal Server Error", 500


def print_startup_info():
    """Print useful information when the server starts."""
    print("\n" + "="*60)
    print(f"  {config.APP_NAME} v{config.APP_VERSION}")
    print("="*60)
    print(f"\n[OK] Server starting on http://{config.HOST}:{config.PORT}")
    print(f"[OK] Admin panel: http://localhost:{config.PORT}/admin?token={config.ADMIN_TOKEN}")

    # Discord webhook status
    if config.SEND_TO_DISCORD and config.DISCORD_WEBHOOK_URL:
        print(f"[OK] Discord webhooks: ENABLED")
    else:
        print(f"[INFO] Discord webhooks: DISABLED")

    print(f"\n[INFO] To expose via ngrok, run in another terminal:")
    print(f"       ngrok http {config.PORT}")
    print("\n[WARNING] Educational use only. Ensure proper consent for tracking.\n")


if __name__ == '__main__':
    # Initialize database
    init_db()

    # Print startup information
    print_startup_info()

    # Run the Flask development server
    app.run(
        host=config.HOST,
        port=config.PORT,
        debug=config.DEBUG
    )
