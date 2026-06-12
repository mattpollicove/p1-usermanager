#!/usr/bin/env python3
"""Quick diagnostic script to test MySQL connectivity."""

import socket
import sys

# Test parameters - adjust these to match your setup
HOST = "192.168.4.172"
PORT = 3306

print(f"Testing connectivity to {HOST}:{PORT}...\n")

# 1. Test network connectivity with socket
print(f"1. Testing TCP connectivity to {HOST}:{PORT}")
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    result = sock.connect_ex((HOST, PORT))
    sock.close()
    if result == 0:
        print(f"   ✓ Port {PORT} is open and reachable\n")
    else:
        print(f"   ✗ Port {PORT} is NOT reachable (connection refused)\n")
        print("   TROUBLESHOOTING:")
        print("   - Is the MySQL service running on the remote server?")
        print("   - Is there a firewall blocking port 3306?")
        print("   - Is the IP address correct?")
        sys.exit(1)
except socket.timeout:
    print(f"   ✗ Connection timed out (can't reach host)\n")
    print("   TROUBLESHOOTING:")
    print("   - Verify the host IP is correct: ping 192.168.4.172")
    print("   - Check network routing and firewalls")
    sys.exit(1)
except Exception as e:
    print(f"   ✗ Error: {e}\n")
    sys.exit(1)

# 2. Test PyMySQL directly
print("2. Testing PyMySQL driver connection")
try:
    import pymysql
    import os
    
    # Load credentials from environment variables for security
    # Set these before running: export DB_USER=username DB_PASS=password DB_NAME=dbname
    db_user = os.environ.get("DB_USER", "your_username")
    db_pass = os.environ.get("DB_PASS", "your_password") 
    db_name = os.environ.get("DB_NAME", "your_database")
    
    if db_user == "your_username":
        print("   ⚠ Using default credentials - set DB_USER, DB_PASS, DB_NAME environment variables\n")
    
    conn = pymysql.connect(
        host=HOST,
        port=PORT,
        user=db_user,
        password=db_pass,
        database=db_name,
        connect_timeout=5,
        read_timeout=5,
        write_timeout=5,
    )
    print("   ✓ PyMySQL connection successful!")
    conn.close()
except pymysql.MySQLError as e:
    print(f"   ✗ PyMySQL error: {e}")
    print("\n   Common issues:")
    print("   - Wrong username/password")
    print("   - Database doesn't exist")
    print("   - User doesn't have % host access")
except Exception as e:
    print(f"   ✗ Error: {e}")

# 3. Test SQLAlchemy directly
print("\n3. Testing SQLAlchemy connection")
try:
    from sqlalchemy import create_engine, text
    
    # Replace credentials
    url = f"mysql+pymysql://your_username:your_password@{HOST}:{PORT}/your_database"
    engine = create_engine(
        url,
        connect_args={
            "connect_timeout": 5,
            "read_timeout": 5,
            "write_timeout": 5,
        }
    )
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        print("   ✓ SQLAlchemy connection successful!")
except Exception as e:
    print(f"   ✗ SQLAlchemy error: {e}")

print("\n✓ Diagnostics complete!")
