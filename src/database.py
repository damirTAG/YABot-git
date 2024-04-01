import sqlite3
from datetime import datetime

class Database:
    def __init__(self, db_name) -> None:
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()

    def create_table(self, table_name, columns):
        query = f"CREATE TABLE IF NOT EXISTS {table_name} ({columns})"
        self.cursor.execute(query)
        self.conn.commit()
    
    def insert_data(self, table_name, data):
        self.cursor.execute(f"SELECT * FROM {table_name} WHERE user_id=?", (data[0],))
        if self.cursor.fetchone() is None:
            self.cursor.execute(f"INSERT INTO {table_name} VALUES (?, ?, ?)", data)
            self.conn.commit()
            return True
        else:
            return False

    def close(self):
        self.conn.close()