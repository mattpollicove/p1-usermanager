#!/usr/bin/env python3
"""Test the updated database utilities."""

import os
from api import db_utils

# Load from environment variables for security
# Set these before running: export DB_HOST=host DB_USER=user DB_PASS=pass DB_NAME=dbname
host = os.environ.get("DB_HOST", "localhost")
port = int(os.environ.get("DB_PORT", "3306"))
user = os.environ.get("DB_USER", "testuser")
password = os.environ.get("DB_PASS", "testpass")
database = os.environ.get("DB_NAME", "testdb")

if user == "testuser":
    print("⚠ WARNING: Using default test credentials")
    print("Set environment variables: DB_HOST, DB_USER, DB_PASS, DB_NAME\n")

print("Testing database connection with timeouts...")
success, err = db_utils.test_connection("MariaDB/MySQL", host, port, database, user, password)
print(f"Connection: {'✓ Success' if success else '✗ Failed'}")
if err:
    print(f"Error: {err}")

if success:
    print("\nTesting table discovery...")
    try:
        tables = db_utils.get_table_names("MariaDB/MySQL", host, port, database, user, password)
        print(f"Found tables: {tables}")
        
        if tables:
            first_table = tables[0]
            print(f"\nFetching sample from first table '{first_table}'...")
            sample = db_utils.get_table_sample("MariaDB/MySQL", host, port, database, user, password, first_table)
            if sample:
                print(f"Sample record: {sample}")
            else:
                print(f"Table '{first_table}' is empty")
    except Exception as e:
        print(f"Error: {e}")

print("\n✓ Test complete!")
