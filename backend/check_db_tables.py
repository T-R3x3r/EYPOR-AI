import sqlite3
import os

# Check multiple possible database locations
possible_paths = [
    '../project_data.db',
    '../../project_data.db', 
    'project_data.db',
    os.path.join(os.getcwd(), 'project_data.db'),
    os.path.join(os.getcwd(), '..', 'project_data.db')
]

db_path = None
for path in possible_paths:
    if os.path.exists(path):
        db_path = path
        print(f"Found database at: {db_path}")
        break

if not db_path:
    print("Database not found. Searched in:")
    for path in possible_paths:
        print(f"  - {path}")
    exit(1)

# Connect and get tables
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print("\nTables in database:")
for table in tables:
    print(f"  - {table[0]}")

# Get schema for each table
print("\nTable schemas:")
for table in tables:
    table_name = table[0]
    print(f"\n{table_name}:")
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    for col in columns:
        print(f"  - {col[1]} ({col[2]})")

conn.close() 