import psycopg2
import logging
from typing import List, Tuple, Dict, Any, Optional
from contextlib import closing
from config.constants import CACHE_CHAT
from config.settings import DB_CONFIG
from utils import ConsoleColors


class DB_actions():
    def __init__(self):
        self.logger = logging.getLogger()

    def _get_connection(self):
        """Create and return a database connection."""
        try:
            return psycopg2.connect(**DB_CONFIG)
        except psycopg2.Error as e:
            self.logger.error(f"Database connection error: {e}")
            raise

    def init_db(self):
        """Initialize database tables."""
        with closing(self._get_connection()) as conn:
            with closing(conn.cursor()) as cursor:
                # Users table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        user_id BIGINT PRIMARY KEY,
                        username VARCHAR(255),
                        first_name VARCHAR(255),
                        last_name VARCHAR(255),
                        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Commands table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS commands (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT REFERENCES users(user_id),
                        command VARCHAR(255),
                        used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Messages table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS messages (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT REFERENCES users(user_id),
                        message TEXT,
                        sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # User saved files table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS user_saved (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT REFERENCES users(user_id),
                        file_id VARCHAR(255),
                        type VARCHAR(100),
                        saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Chats table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS chats (
                        id SERIAL PRIMARY KEY,
                        chat_id VARCHAR(255) UNIQUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Voice settings table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS voice_settings (
                        chat_id BIGINT PRIMARY KEY,
                        voice_disabled BOOLEAN NOT NULL DEFAULT FALSE
                    )
                """)

                # Audio cache table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS audio_cache (
                        id SERIAL PRIMARY KEY,
                        chat_id BIGINT,
                        message_id BIGINT,
                        audio_link TEXT
                    )
                """)

                # Video cache table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS video_cache (
                        id SERIAL PRIMARY KEY,
                        chat_id BIGINT,
                        message_id BIGINT,
                        video_link TEXT
                    )
                """)

                conn.commit()
                self.logger.info("Database initialized successfully")

    def save_to_cache(self, cached_msg_id: int, url: str) -> bool:
        """Save video URL to cache."""
        try:
            with closing(self._get_connection()) as conn:
                with closing(conn.cursor()) as cursor:
                    cursor.execute(
                        'INSERT INTO video_cache (chat_id, message_id, video_link) VALUES (%s, %s, %s)',
                        (CACHE_CHAT, cached_msg_id, url)
                    )
                    conn.commit() 
                    self.logger.info(f'{ConsoleColors.OKGREEN}{url} cached{ConsoleColors.ENDC}')
                    return True
        except psycopg2.Error as e:
            self.logger.error(f"Error saving to cache: {e}")
            return False

    def get_cached_media(self, url: str) -> Optional[Tuple[int, int]]:
        """Get cached media by URL."""
        try:
            with closing(self._get_connection()) as conn:
                with closing(conn.cursor()) as cursor:
                    cursor.execute(
                        'SELECT chat_id, message_id FROM video_cache WHERE video_link = %s', (url,)
                    )
                    result = cursor.fetchone()
                    if result:
                        self.logger.info(f'{ConsoleColors.OKGREEN}Sending cached{ConsoleColors.ENDC}')
                        return result[0], result[1]
                    return None
        except psycopg2.Error as e:
            self.logger.error(f"Error getting cached media: {e}")
            return None

    def is_voice_disabled(self, chat_id: int) -> bool:
        """Check if voice is disabled for a chat."""
        try:
            with closing(self._get_connection()) as conn:
                with closing(conn.cursor()) as cursor:
                    cursor.execute('SELECT voice_disabled FROM voice_settings WHERE chat_id = %s', (chat_id,))
                    result = cursor.fetchone()
                    if result:
                        return result[0]
                    return False
        except psycopg2.Error as e:
            self.logger.error(f"Error checking voice setting: {e}")
            return False

    def toggle_voice_setting(self, chat_id: int) -> bool:
        """Toggle voice setting for a chat."""
        current_setting = self.is_voice_disabled(chat_id)
        new_setting = not current_setting
        
        try:
            with closing(self._get_connection()) as conn:
                with closing(conn.cursor()) as cursor:
                    cursor.execute("""
                        INSERT INTO voice_settings (chat_id, voice_disabled) 
                        VALUES (%s, %s)
                        ON CONFLICT (chat_id) 
                        DO UPDATE SET voice_disabled = %s
                    """, (chat_id, new_setting, new_setting))
                    conn.commit()
            return new_setting
        except psycopg2.Error as e:
            self.logger.error(f"Error toggling voice setting: {e}")
            return current_setting
        
    def execute_query(
        self, 
        query: str, 
        parameters: tuple = (), 
        fetch_all: bool = True
    ) -> Any:
        """Execute a query and return the results."""
        try:
            query = query.replace("?", "%s")

            with closing(self._get_connection()) as conn:
                with closing(conn.cursor()) as cursor:
                    cursor.execute(query, parameters)
                    if query.strip().upper().startswith(("SELECT", "WITH")):
                        return cursor.fetchall() if fetch_all else cursor.fetchone()
                    else:
                        conn.commit()
                        return True
        except psycopg2.Error as e:
            self.logger.error(f"Database query error: {e}")
            self.logger.error(f"Query: {query}, Parameters: {parameters}")
            raise
    
    def add_user(self, user_id: int, username: str = None, first_name: str = None, last_name: str = None) -> None:
        """Add or update a user in the database."""
        query = '''
        INSERT INTO users (user_id, username, first_name, last_name)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (user_id) 
        DO UPDATE SET username = %s, first_name = %s, last_name = %s
        '''
        self.execute_query(query, (user_id, username, first_name, last_name, username, first_name, last_name))
    
    def get_all_users(self, limit: int = 10, offset: int = 0) -> List[Dict[str, Any]]:
        """Get users with pagination."""
        try:
            with closing(self._get_connection()) as conn:
                with closing(conn.cursor()) as cursor:
                    cursor.execute("""
                        SELECT user_id, username, first_name, last_name, joined_at
                        FROM users
                        ORDER BY joined_at DESC
                        LIMIT %s OFFSET %s
                    """, (limit, offset))
                    
                    users = []
                    for row in cursor.fetchall():
                        users.append({
                            'user_id': row[0],
                            'username': row[1],
                            'first_name': row[2],
                            'last_name': row[3],
                            'joined_at': row[4]
                        })
                        
                    return users
        except psycopg2.Error as e:
            self.logger.error(f"Error getting users: {e}")
            return []
            
    def get_total_users_count(self) -> int:
        """Get total number of users."""
        try:
            with closing(self._get_connection()) as conn:
                with closing(conn.cursor()) as cursor:
                    cursor.execute("SELECT COUNT(*) FROM users")
                    return cursor.fetchone()[0]
        except psycopg2.Error as e:
            self.logger.error(f"Error getting user count: {e}")
            return 0
            
    def get_user_details(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific user."""
        try:
            with closing(self._get_connection()) as conn:
                with closing(conn.cursor()) as cursor:
                    cursor.execute("""
                        SELECT user_id, username, first_name, last_name, joined_at
                        FROM users
                        WHERE user_id = %s
                    """, (user_id,))
                            
                    user_row = cursor.fetchone()
                    if not user_row:
                        return None

                    cursor.execute("SELECT COUNT(*) FROM commands WHERE user_id = %s", (user_id,))
                    command_count = cursor.fetchone()[0]
                            
                    cursor.execute("SELECT COUNT(*) FROM user_saved WHERE user_id = %s", (user_id,))
                    saved_files = cursor.fetchone()[0]

                    cursor.execute("""
                        SELECT command, used_at FROM commands
                        WHERE user_id = %s
                        ORDER BY used_at DESC
                        LIMIT 5
                    """, (user_id,))
                            
                    recent_commands = []
                    for row in cursor.fetchall():
                        recent_commands.append({
                            'command': row[0],
                            'used_at': row[1]
                        })
                            
                    return {
                        'user_id': user_row[0],
                        'username': user_row[1],
                        'first_name': user_row[2],
                        'last_name': user_row[3],
                        'joined_at': user_row[4],
                        'command_count': command_count,
                        'saved_files': saved_files,
                        'recent_commands': recent_commands
                    }
        except psycopg2.Error as e:
            self.logger.error(f"Error getting user details: {e}")
            return None

    def add_chat(self, chat_id: str) -> None:
        """Add or update a chat in the database."""
        query = 'INSERT INTO chats (chat_id) VALUES (%s) ON CONFLICT (chat_id) DO NOTHING'
        self.execute_query(query, (chat_id,))
    
    def log_command(self, user_id: int, command: str) -> None:
        """Log a command usage in the database."""
        query = 'INSERT INTO commands (user_id, command, used_at) VALUES (%s, %s, CURRENT_TIMESTAMP)'
        self.execute_query(query, (user_id, command))
    
    def save_file(self, user_id: int, file_id: str, file_type: str) -> None:
        """Record a file saved by a user."""
        query = 'INSERT INTO user_saved (user_id, file_id, type, saved_at) VALUES (%s, %s, %s, CURRENT_TIMESTAMP)'
        self.execute_query(query, (user_id, file_id, file_type))

    def get_file_by_id(self, file_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific saved file by its database ID."""
        query = """
            SELECT us.id, us.file_id, us.type, us.saved_at, us.user_id
            FROM user_saved us
            WHERE us.id = %s
        """
        
        result = self.execute_query(query, (file_id,), fetch_all=False)
        
        if not result:
            return None
            
        return {
            "id": result[0],
            "file_id": result[1],
            "type": result[2],
            "saved_at": result[3],
            "user_id": result[4]
        }

    def get_user_saved_files(self, user_id: int, page: int = 0, items_per_page: int = 5) -> List[Dict[str, Any]]:
        """Get saved files for a specific user with pagination."""
        offset = page * items_per_page
        
        query = """
            SELECT us.id, us.file_id, us.type, us.saved_at
            FROM user_saved us
            WHERE us.user_id = %s
            ORDER BY us.saved_at DESC
            LIMIT %s OFFSET %s
        """
        
        results = self.execute_query(query, (user_id, items_per_page, offset))
        
        if not results:
            return []
        
        files = []
        for row in results:
            files.append({
                "id": row[0],
                "file_id": row[1],
                "type": row[2],
                "saved_at": row[3]
            })
            
        return files

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics from the database."""
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
            SELECT * FROM (
                SELECT DISTINCT ON (u.user_id)
                    u.username, 
                    u.first_name, 
                    u.last_name, 
                    c.command, 
                    c.used_at
                FROM users u
                JOIN commands c ON u.user_id = c.user_id
                ORDER BY u.user_id, c.used_at DESC
            ) t
            ORDER BY t.used_at DESC
            LIMIT 10;
        """)
        
        # Most active users
        stats['active_users'] = self.execute_query("""
            SELECT users.username, users.first_name, users.last_name, COUNT(commands.id) as cmd_count 
            FROM users 
            JOIN commands ON users.user_id = commands.user_id 
            GROUP BY users.user_id, users.username, users.first_name, users.last_name
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
            GROUP BY users.user_id, users.username, users.first_name, users.last_name
            ORDER BY file_count DESC
            LIMIT 10
        """)
        
        return stats
    
    def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """Get statistics for a specific user."""
        user_stats = {}
        
        # Basic user info
        user_info = self.execute_query("""
            SELECT username, first_name, last_name, joined_at
            FROM users
            WHERE user_id = %s
        """, (user_id,))
        
        if not user_info:
            return {"error": "User not found"}
            
        user_stats['username'] = user_info[0][0]
        user_stats['first_name'] = user_info[0][1]
        user_stats['last_name'] = user_info[0][2]
        user_stats['joined_at'] = user_info[0][3]
        
        # Command count
        user_stats['command_count'] = self.execute_query(
            "SELECT COUNT(*) FROM commands WHERE user_id = %s", (user_id,)
        )[0][0]
        
        # Top commands used
        user_stats['top_commands'] = self.execute_query("""
            SELECT command, COUNT(*) 
            FROM commands 
            WHERE user_id = %s
            GROUP BY command 
            ORDER BY COUNT(*) DESC 
            LIMIT 5
        """, (user_id,))
        
        # Saved files count
        user_stats['saved_files_count'] = self.execute_query(
            "SELECT COUNT(*) FROM user_saved WHERE user_id = %s", (user_id,)
        )[0][0]
        
        return user_stats
    
    def get_activity_timeline(self, days: int = 30) -> List[Tuple[str, int]]:
        """Get command activity over a specified number of days."""
        return self.execute_query("""
            SELECT DATE(used_at) as day, COUNT(*) as count
            FROM commands
            WHERE used_at >= CURRENT_DATE - INTERVAL '%s days'
            GROUP BY DATE(used_at)
            ORDER BY day
        """, (days,))
    
    def search_users(self, search_term: str) -> List[Dict[str, Any]]:
        """Search users by username or user_id."""
        try:
            with closing(self._get_connection()) as conn:
                with closing(conn.cursor()) as cursor:
                    # Try to convert search term to integer for ID search
                    try:
                        user_id = int(search_term)
                        # Search by exact user_id or username containing the term
                        cursor.execute("""
                            SELECT user_id, username, first_name, last_name, joined_at
                            FROM users
                            WHERE user_id = %s OR username ILIKE %s
                            ORDER BY 
                                CASE WHEN user_id = %s THEN 1 ELSE 2 END,
                                joined_at DESC
                            LIMIT 20
                        """, (user_id, f"%{search_term}%", user_id))
                    except ValueError:
                        # Search only by username if not a number
                        cursor.execute("""
                            SELECT user_id, username, first_name, last_name, joined_at
                            FROM users
                            WHERE username ILIKE %s OR first_name ILIKE %s OR last_name ILIKE %s
                            ORDER BY joined_at DESC
                            LIMIT 20
                        """, (f"%{search_term}%", f"%{search_term}%", f"%{search_term}%"))
                    
                    users = []
                    for row in cursor.fetchall():
                        users.append({
                            'user_id': row[0],
                            'username': row[1],
                            'first_name': row[2],
                            'last_name': row[3],
                            'joined_at': row[4]
                        })
                        
                    return users
        except psycopg2.Error as e:
            self.logger.error(f"Error searching users: {e}")
            return []

    def backup_database(self, backup_path: str) -> bool:
        """Create a backup of the database using pg_dump."""
        import subprocess
        try:
            # Use pg_dump for PostgreSQL backup
            cmd = [
                'pg_dump',
                f"--host={self.db_config['host']}",
                f"--port={self.db_config['port']}",
                f"--username={self.db_config['user']}",
                f"--dbname={self.db_config['dbname']}",
                '--no-password',
                '--clean',
                '--create'
            ]
            
            # Set password via environment variable
            import os
            env = os.environ.copy()
            env['PGPASSWORD'] = self.db_config['password']
            
            with open(backup_path, 'w') as f:
                result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, env=env)
                
            if result.returncode == 0:
                self.logger.info(f"Database backup created successfully: {backup_path}")
                return True
            else:
                self.logger.error(f"Backup failed: {result.stderr.decode()}")
                return False
                
        except Exception as e:
            self.logger.error(f"Database backup error: {e}")
            return False