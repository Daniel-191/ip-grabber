"""
Database module for storing and retrieving visitor information.
Uses SQLite for simplicity and portability.
"""
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import csv
from config import config


def get_connection():
    """Create and return a database connection."""
    conn = sqlite3.connect(config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row  # Return rows as dictionaries
    return conn


def init_db():
    """Initialize the database and create tables if they don't exist."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS visits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip_address TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            user_agent TEXT,
            referer TEXT,
            request_path TEXT,
            request_method TEXT,
            forwarded_for TEXT
        )
    ''')

    conn.commit()
    conn.close()
    print(f"[OK] Database initialized at {config.DATABASE_PATH}")


def log_visit(
    ip_address: str,
    timestamp: str,
    user_agent: Optional[str] = None,
    referer: Optional[str] = None,
    request_path: str = '/',
    request_method: str = 'GET',
    forwarded_for: Optional[str] = None
) -> int:
    """
    Log a visitor to the database.

    Args:
        ip_address: The visitor's IP address
        timestamp: ISO 8601 formatted timestamp
        user_agent: Browser/device user agent string
        referer: The referer header (where they came from)
        request_path: The URL path they accessed
        request_method: HTTP method (GET, POST, etc.)
        forwarded_for: Full X-Forwarded-For header value

    Returns:
        The ID of the newly inserted record
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO visits (
            ip_address, timestamp, user_agent, referer,
            request_path, request_method, forwarded_for
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (ip_address, timestamp, user_agent, referer, request_path, request_method, forwarded_for))

    visit_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return visit_id


def get_visits(limit: int = 100, offset: int = 0) -> List[Dict]:
    """
    Retrieve visitor records from the database.

    Args:
        limit: Maximum number of records to return
        offset: Number of records to skip (for pagination)

    Returns:
        List of visit records as dictionaries
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT * FROM visits
        ORDER BY timestamp DESC
        LIMIT ? OFFSET ?
    ''', (limit, offset))

    visits = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return visits


def get_stats() -> Dict:
    """
    Calculate and return statistics about visits.

    Returns:
        Dictionary containing various statistics
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Total visits
    cursor.execute('SELECT COUNT(*) as count FROM visits')
    total_visits = cursor.fetchone()['count']

    # Unique IP addresses
    cursor.execute('SELECT COUNT(DISTINCT ip_address) as count FROM visits')
    unique_ips = cursor.fetchone()['count']

    # Most recent visit
    cursor.execute('SELECT timestamp FROM visits ORDER BY timestamp DESC LIMIT 1')
    recent = cursor.fetchone()
    most_recent = recent['timestamp'] if recent else None

    # First visit
    cursor.execute('SELECT timestamp FROM visits ORDER BY timestamp ASC LIMIT 1')
    first = cursor.fetchone()
    first_visit = first['timestamp'] if first else None

    # Top IPs
    cursor.execute('''
        SELECT ip_address, COUNT(*) as visit_count
        FROM visits
        GROUP BY ip_address
        ORDER BY visit_count DESC
        LIMIT 5
    ''')
    top_ips = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return {
        'total_visits': total_visits,
        'unique_ips': unique_ips,
        'most_recent_visit': most_recent,
        'first_visit': first_visit,
        'top_ips': top_ips
    }


def get_unique_ips() -> List[str]:
    """
    Get a list of all unique IP addresses that have visited.

    Returns:
        List of unique IP address strings
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT DISTINCT ip_address FROM visits ORDER BY ip_address')
    ips = [row['ip_address'] for row in cursor.fetchall()]

    conn.close()
    return ips


def export_to_csv(filepath: str) -> int:
    """
    Export all visit data to a CSV file.

    Args:
        filepath: Path where the CSV file should be saved

    Returns:
        Number of records exported
    """
    visits = get_visits(limit=999999)  # Get all records

    with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
        if not visits:
            return 0

        fieldnames = visits[0].keys()
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        writer.writerows(visits)

    return len(visits)


def search_visits(
    ip_address: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100
) -> List[Dict]:
    """
    Search for visits matching specific criteria.

    Args:
        ip_address: Filter by IP address (partial match)
        start_date: Filter visits after this date (ISO format)
        end_date: Filter visits before this date (ISO format)
        limit: Maximum number of results

    Returns:
        List of matching visit records
    """
    conn = get_connection()
    cursor = conn.cursor()

    query = 'SELECT * FROM visits WHERE 1=1'
    params = []

    if ip_address:
        query += ' AND ip_address LIKE ?'
        params.append(f'%{ip_address}%')

    if start_date:
        query += ' AND timestamp >= ?'
        params.append(start_date)

    if end_date:
        query += ' AND timestamp <= ?'
        params.append(end_date)

    query += ' ORDER BY timestamp DESC LIMIT ?'
    params.append(limit)

    cursor.execute(query, params)
    visits = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return visits


if __name__ == "__main__":
    # Test the database module
    print("Initializing database...")
    init_db()

    print("\nLogging test visit...")
    visit_id = log_visit(
        ip_address="127.0.0.1",
        timestamp=datetime.now().isoformat(),
        user_agent="Test User Agent",
        referer="https://test.com",
        request_path="/",
        request_method="GET",
        forwarded_for="127.0.0.1"
    )
    print(f"[OK] Logged visit with ID: {visit_id}")

    print("\nRetrieving visits...")
    visits = get_visits(limit=5)
    print(f"[OK] Found {len(visits)} visits")

    print("\nGetting statistics...")
    stats = get_stats()
    print(f"[OK] Total visits: {stats['total_visits']}")
    print(f"[OK] Unique IPs: {stats['unique_ips']}")
