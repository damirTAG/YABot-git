import sqlite3
from datetime import datetime
from typing import Union, Optional


class Database:
    def __init__(self, db_name) -> None:
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()

    def create_table(self, table_name, columns):
        query = f"CREATE TABLE IF NOT EXISTS {table_name} ({columns})"
        self.cursor.execute(query)
        self.conn.commit()
    
    def insert_data(self, 
                table_name: str = None, 
                col: Optional[str] = '*',
                data: Union[str, int, tuple] = None, 
                method: Optional[str] = None):
    
        if table_name == 'prayer_users':
            try:
                self.cursor.execute(f"SELECT {col} FROM {table_name} WHERE user_id=?", (data[0],))
                if self.cursor.fetchone() is None:
                    self.cursor.execute(f"INSERT INTO {table_name} VALUES (?, ?, ?)", data)
                    self.conn.commit()
                    return True
                else:
                    return False
            except sqlite3.IntegrityError:
                self.cursor.execute(f"UPDATE {table_name} SET city=? WHERE user_id=?", (data[2], data[1]))
                self.conn.commit()
                return True
        elif table_name == 'users':
            self.cursor.execute(f"INSERT INTO {table_name} (user_id, username, fullname) VALUES (?, ?, ?)", data)
            self.conn.commit()
            return True
        else:
            self.cursor.execute(f"INSERT INTO {table_name} VALUES (?, ?, ?)", data)
            self.conn.commit()
            return True

    def get_data(
            self, 
            table_name: Union[str] = None, 
            col: Optional[str] = '*',
            data: Union[str] = None, 
            method: Union[str] = None) -> dict:
        self.cursor.execute(f'SELECT {col} FROM {table_name} WHERE user_id = ?', (data,))
        if method == 'fetchone':
            _return = self.cursor.fetchone()
            return _return[0] if _return else None
        elif method == 'fetchall':
            _return = self.cursor.fetchall()
            return _return
        elif method == 'fetchmany':
            _return = self.cursor.fetchmany()
            return _return

    def get_pray_data(self):
        self.cursor.execute("SELECT user_id, city FROM prayer_users")
        data = self.cursor.fetchall()
        return data

    def close(self):
        self.conn.close()