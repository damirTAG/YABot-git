import sqlite3
import json

# Read user IDs from JSON file
with open('user_ids.json', 'r') as f:
    user_ids = json.load(f)

# Connect to SQLite database (it will be created if it doesn't exist)
conn = sqlite3.connect('telegram-bot/yerzhanakh-py/database/users.db')
cursor = conn.cursor()

# Create table if it doesn't exist
cursor.execute('''CREATE TABLE IF NOT EXISTS users
                  (id INTEGER PRIMARY KEY, user_id INTEGER UNIQUE, username TEXT, fullname TEXT)''')

# Insert user IDs into the database
for user_id in user_ids:
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))

conn.commit()
conn.close()