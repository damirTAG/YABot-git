import sqlite3

def create_database():
    conn = sqlite3.connect('telegram-bot/yerzhanakh-py/database/prayer_times.db')
    cursor = conn.cursor()

    # Create prayer_users table
    cursor.execute('''CREATE TABLE IF NOT EXISTS prayer_users (
                        id INTEGER PRIMARY KEY,
                        user_id INTEGER UNIQUE,
                        city TEXT
                    )''')
    
    conn.commit()
    conn.close()

def insert_user_data(user_ids, city):
    conn = sqlite3.connect('telegram-bot/yerzhanakh-py/database/prayer_times.db')
    cursor = conn.cursor()

    for user_id in user_ids:
        cursor.execute("INSERT OR IGNORE INTO prayer_users (user_id, city) VALUES (?, ?)", (user_id, city))

    conn.commit()
    conn.close()

if __name__ == '__main__':
    create_database()

    user_ids = [1038468423, 419481001, 688911314]
    city = 'Almaty'
    insert_user_data(user_ids, city)

    print(f"Data inserted successfully for users: {user_ids} with city: {city}")
