#!/usr/bin/env python3
"""Test the updated database utilities."""

from api import db_utils

host = "192.168.4.174"
port = 3306
user = "mattp"
password = "Ping-2026!"
database = "userdata"

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
