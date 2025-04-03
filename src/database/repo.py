import sqlite3, logging

from typing                 import List, Tuple, Dict, Any
from contextlib             import closing
from config.constants     import CACHE_CHAT
from utils                import ConsoleColors


class DB_actions():
    def __init__(self):
        self.logger = logging.getLogger()

    def _get_connection(self, db_path = 'stats.db'):
        """Create and return a database connection."""
        try:
            return sqlite3.connect(db_path)
        except sqlite3.Error as e:
            self.logger.error(f"Database connection error: {e}")
            raise

    def init_db(self):
        conn = sqlite3.connect("stats.db")
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS commands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                command TEXT,
                used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                message TEXT,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_saved (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                file_id INTEGER,
                type TEXT,
                saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS voice_settings (
                chat_id INTEGER PRIMARY KEY,
                voice_disabled INTEGER NOT NULL DEFAULT 0
            )
        ''')
        conn.commit()

        conn = sqlite3.connect('cache.db')
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS audio_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                message_id INTEGER,
                audio_link TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS video_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                message_id INTEGER,
                video_link TEXT
            )
        ''')

    def save_to_cache(self, cached_msg_id, url, db_path: str = 'cache.db') -> bool:
        with closing(self._get_connection(db_path)) as conn:
            with closing(conn.cursor()) as cursor:
                cursor.execute(
                    'INSERT INTO video_cache (chat_id, message_id, video_link) VALUES (?, ?, ?)',(CACHE_CHAT, cached_msg_id, url)
                )
                conn.commit() 
                self.logger.info(f'{ConsoleColors.OKGREEN}{url} cached{ConsoleColors.ENDC}')

    def get_cached_media(self, url, db_path: str = 'cache.db'):
        with closing(self._get_connection(db_path)) as conn:
            with closing(conn.cursor()) as cursor:
                cursor.execute(
                    'SELECT chat_id, message_id FROM video_cache WHERE video_link = ?', (url,)
                )
                result = cursor.fetchone()
                if result:
                    self.logger.info(f'{ConsoleColors.OKGREEN}Sending cached{ConsoleColors.ENDC}')
                    return result[0], result[1]
                return None
                    

    def is_voice_disabled(self, chat_id):
        with closing(self._get_connection('stats.db')) as conn:
            with closing(conn.cursor()) as cursor:
                cursor.execute('SELECT voice_disabled FROM voice_settings WHERE chat_id = ?', (chat_id,))
                result = cursor.fetchone()
                if result:
                    return bool(result[0])
                return False

    def toggle_voice_setting(self, chat_id):
        current_setting = self.is_voice_disabled(chat_id)
        new_setting = not current_setting
        
        with closing(self._get_connection('stats.db')) as conn:
            with closing(conn.cursor()) as cursor:
                cursor.execute('''
                    INSERT INTO voice_settings (chat_id, voice_disabled) 
                    VALUES (?, ?)
                    ON CONFLICT(chat_id) 
                    DO UPDATE SET voice_disabled = ?
                ''', (chat_id, int(new_setting), int(new_setting)))
                conn.commit()
        
        return new_setting
        
    def execute_query(self, query: str, parameters: tuple = (), db_path: str = 'stats.db') -> List[Tuple]:
        """
        Execute a query and return the results.
        
        Args:
            query: SQL query string
            parameters: Parameters for the query
            
        Returns:
            List of query results
        """
        try:
            with closing(self._get_connection(db_path)) as conn:
                with closing(conn.cursor()) as cursor:
                    cursor.execute(query, parameters)
                    if query.strip().upper().startswith(("SELECT", "PRAGMA", "WITH")):
                        return cursor.fetchall()
                    else:
                        conn.commit()
                        return []
        except sqlite3.Error as e:
            self.logger.error(f"Database query error: {e}")
            self.logger.error(f"Query: {query}, Parameters: {parameters}")
            raise
    
    def add_user(self, user_id: int, username: str = None, first_name: str = None, last_name: str = None) -> None:
        """
        Add or update a user in the database.
        
        Args:
            user_id: Telegram user ID
            username: Telegram username
            first_name: User's first name
            last_name: User's last name
        """
        query = '''
        INSERT INTO users (user_id, username, first_name, last_name)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) 
        DO UPDATE SET username=?, first_name=?, last_name=?
        '''
        self.execute_query(query, (user_id, username, first_name, last_name, username, first_name, last_name))
    
    def add_chat(self, chat_id: int) -> None:
        """
        Add or update a chat in the database.
        
        Args:
            chat_id: Telegram chat ID
        """
        query = '''
        INSERT INTO chats (chat_id)
        VALUES (?)
        '''
        self.execute_query(query, (chat_id))
    
    def log_command(self, user_id: int, command: str) -> None:
        """
        Log a command usage in the database.
        
        Args:
            user_id: User who used the command
            chat_id: Chat where command was used
            command: The command that was used
        """
        query = '''
        INSERT INTO commands (user_id, command, used_at)
        VALUES (?, ?, datetime('now'))
        '''
        self.execute_query(query, (user_id, command))
    
    def save_file(self, user_id: int, file_id: str, file_type: str) -> None:
        """
        Record a file saved by a user.
        
        Args:
            user_id: User who saved the file
            file_id: Telegram file ID
            file_type: Type of file (photo, video, document, etc.)
        """
        query = '''
        INSERT INTO user_saved (user_id, file_id, type, saved_at)
        VALUES (?, ?, ?, datetime('now'))
        '''
        self.execute_query(query, (user_id, file_id, file_type))
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics from the database.
        
        Returns:
            Dictionary with various statistics
        """
        stats = {}
        
        # User and chat counts
        stats['user_count'] = self.execute_query("SELECT COUNT(*) FROM users")[0][0]
        stats['chat_count'] = self.execute_query("SELECT COUNT(*) FROM chats")[0][0]
        
        # Top commands
        stats['top_commands'] = self.execute_query("""
            SELECT command, COUNT(*) FROM commands 
            GROUP BY command 
            ORDER BY COUNT(*) DESC 
            LIMIT 10
        """)
        
        # Recent active users
        stats['recent_users'] = self.execute_query("""
            SELECT users.username, users.first_name, users.last_name, commands.command, commands.used_at
            FROM users 
            JOIN commands ON users.user_id = commands.user_id 
            WHERE commands.used_at = (
                SELECT MAX(used_at) FROM commands WHERE commands.user_id = users.user_id
            ) 
            GROUP BY users.user_id 
            ORDER BY MAX(commands.used_at) DESC 
            LIMIT 10
        """)
        
        # Most active users
        stats['active_users'] = self.execute_query("""
            SELECT users.username, users.first_name, users.last_name, COUNT(commands.id) as cmd_count 
            FROM users 
            JOIN commands ON users.user_id = commands.user_id 
            GROUP BY users.user_id 
            ORDER BY cmd_count DESC 
            LIMIT 10
        """)
        
        # Saved files stats
        stats['total_saved_files'] = self.execute_query("SELECT COUNT(*) FROM user_saved")[0][0]
        
        # Top file savers
        stats['top_savers'] = self.execute_query("""
            SELECT users.username, users.first_name, users.last_name, COUNT(user_saved.file_id) as file_count
            FROM users 
            JOIN user_saved ON users.user_id = user_saved.user_id
            GROUP BY users.user_id
            ORDER BY file_count DESC
            LIMIT 10
        """)
        
        return stats
    
    def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """
        Get statistics for a specific user.
        
        Args:
            user_id: The user to get stats for
            
        Returns:
            Dictionary with user-specific statistics
        """
        user_stats = {}
        
        # Basic user info
        user_info = self.execute_query("""
            SELECT username, first_name, last_name, joined_at
            FROM users
            WHERE user_id = ?
        """, (user_id,))
        
        if not user_info:
            return {"error": "User not found"}
            
        user_stats['username'] = user_info[0][0]
        user_stats['first_name'] = user_info[0][1]
        user_stats['last_name'] = user_info[0][2]
        user_stats['joined_at'] = user_info[0][3]
        
        # Command count
        user_stats['command_count'] = self.execute_query("""
            SELECT COUNT(*) FROM commands WHERE user_id = ?
        """, (user_id,))[0][0]
        
        # Top commands used
        user_stats['top_commands'] = self.execute_query("""
            SELECT command, COUNT(*) 
            FROM commands 
            WHERE user_id = ?
            GROUP BY command 
            ORDER BY COUNT(*) DESC 
            LIMIT 5
        """, (user_id,))
        
        # Saved files count
        user_stats['saved_files_count'] = self.execute_query("""
            SELECT COUNT(*) FROM user_saved WHERE user_id = ?
        """, (user_id,))[0][0]
        
        return user_stats
    
    def get_activity_timeline(self, days: int = 30) -> List[Tuple[str, int]]:
        """
        Get command activity over a specified number of days.
        
        Args:
            days: Number of past days to include
            
        Returns:
            List of (date, command_count) tuples
        """
        return self.execute_query("""
            SELECT date(used_at) as day, COUNT(*) as count
            FROM commands
            WHERE used_at >= date('now', ?)
            GROUP BY day
            ORDER BY day
        """, (f'-{days} days',))
    
    def backup_database(self, backup_path: str) -> bool:
        """
        Create a backup of the database.
        
        Args:
            backup_path: Path to save the backup
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with closing(self._get_connection()) as conn:
                with open(backup_path, 'w') as f:
                    for line in conn.iterdump():
                        f.write(f'{line}\n')
            return True
        except Exception as e:
            self.logger.error(f"Database backup error: {e}")
            return False