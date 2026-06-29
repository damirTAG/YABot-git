import logging
from contextlib import closing
from typing import Any

import psycopg2

from config.constants import CACHE_CHAT
from config.settings import DB_CONFIG
from utils import ConsoleColors


class DB_actions:
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
                    CREATE TABLE IF NOT EXISTS bot_settings (
                        chat_id BIGINT PRIMARY KEY,
                        voice_disabled BOOLEAN NOT NULL DEFAULT FALSE,
                        quote_disabled BOOLEAN NOT NULL DEFAULT FALSE,
                        tiktok_send_sound_videos_disabled BOOLEAN NOT NULL DEFAULT FALSE,
                        coins_converter_disabled BOOLEAN NOT NULL DEFAULT FALSE,
                        roll_disabled BOOLEAN NOT NULL DEFAULT FALSE,
                        gpt_disabled BOOLEAN NOT NULL DEFAULT FALSE,
                        joke_disabled BOOLEAN NOT NULL DEFAULT FALSE
                    )
                """)

                # Migration: add joke_disabled to pre-existing bot_settings tables.
                cursor.execute("""
                    ALTER TABLE bot_settings
                    ADD COLUMN IF NOT EXISTS joke_disabled BOOLEAN NOT NULL DEFAULT FALSE
                """)

                # Jokes (one per /joke poll) and their 0-10 votes.
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS jokes (
                        id SERIAL PRIMARY KEY,
                        chat_id BIGINT NOT NULL,
                        author_id BIGINT NOT NULL,
                        author_name VARCHAR(255),
                        joke_message_id BIGINT,
                        poll_message_id BIGINT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_jokes_chat_created
                    ON jokes (chat_id, created_at)
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS joke_votes (
                        id SERIAL PRIMARY KEY,
                        joke_id INTEGER NOT NULL REFERENCES jokes(id) ON DELETE CASCADE,
                        voter_id BIGINT NOT NULL,
                        score INTEGER NOT NULL,
                        voted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE (joke_id, voter_id)
                    )
                """)

                # Marker so the weekly leaderboard is posted at most once per chat/week.
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS joke_weekly_runs (
                        chat_id BIGINT NOT NULL,
                        week_end DATE NOT NULL,
                        posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (chat_id, week_end)
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
                        "INSERT INTO video_cache (chat_id, message_id, video_link) VALUES (%s, %s, %s)",
                        (CACHE_CHAT, cached_msg_id, url),
                    )
                    conn.commit()
                    self.logger.info(f"{ConsoleColors.OKGREEN}{url} cached{ConsoleColors.ENDC}")
                    return True
        except psycopg2.Error as e:
            self.logger.error(f"Error saving to cache: {e}")
            return False

    def get_cached_media(self, url: str) -> tuple[int, int] | None:
        """Get cached media by URL."""
        try:
            with closing(self._get_connection()) as conn:
                with closing(conn.cursor()) as cursor:
                    cursor.execute(
                        "SELECT chat_id, message_id FROM video_cache WHERE video_link = %s", (url,)
                    )
                    result = cursor.fetchone()
                    if result:
                        self.logger.info(
                            f"{ConsoleColors.OKGREEN}Sending cached{ConsoleColors.ENDC}"
                        )
                        return result[0], result[1]
                    return None
        except psycopg2.Error as e:
            self.logger.error(f"Error getting cached media: {e}")
            return None

    def toggle_setting(self, chat_id: int, setting: str) -> bool:
        try:
            with closing(self._get_connection()) as conn:
                with closing(conn.cursor()) as cursor:
                    cursor.execute(
                        f"SELECT {setting} FROM bot_settings WHERE chat_id = %s", (chat_id,)
                    )
                    row = cursor.fetchone()

                    current = row[0] if row else False
                    new = not current

                    cursor.execute(
                        f"""
                        INSERT INTO bot_settings (chat_id, {setting})
                        VALUES (%s, %s)
                        ON CONFLICT (chat_id)
                        DO UPDATE SET {setting} = %s
                    """,
                        (chat_id, new, new),
                    )

                    conn.commit()
                    return new
        except Exception as e:
            self.logger.error(f"Error toggling setting {setting}: {e}")
            return False

    def get_setting(self, chat_id: int, setting: str) -> bool:
        try:
            with closing(self._get_connection()) as conn:
                with closing(conn.cursor()) as cursor:
                    cursor.execute("""
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_name = 'bot_settings'
                    """)
                    columns = {row[0] for row in cursor.fetchall()}

                    if setting not in columns:
                        self.logger.error(f"Unknown setting requested: {setting}")
                        return False

                    cursor.execute(
                        f"SELECT {setting} FROM bot_settings WHERE chat_id = %s", (chat_id,)
                    )
                    row = cursor.fetchone()

                    return row[0] if row else False

        except Exception as e:
            self.logger.error(f"Error reading setting `{setting}`: {e}")
            return False

    def execute_query(self, query: str, parameters: tuple = (), fetch_all: bool = True) -> Any:
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

    def add_user(
        self, user_id: int, username: str = None, first_name: str = None, last_name: str = None
    ) -> None:
        """Add or update a user in the database."""
        query = """
        INSERT INTO users (user_id, username, first_name, last_name)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (user_id) 
        DO UPDATE SET username = %s, first_name = %s, last_name = %s
        """
        self.execute_query(
            query, (user_id, username, first_name, last_name, username, first_name, last_name)
        )

    def get_all_users(self, limit: int = 10, offset: int = 0) -> list[dict[str, Any]]:
        """Get users with pagination."""
        try:
            with closing(self._get_connection()) as conn:
                with closing(conn.cursor()) as cursor:
                    cursor.execute(
                        """
                        SELECT user_id, username, first_name, last_name, joined_at
                        FROM users
                        ORDER BY joined_at DESC
                        LIMIT %s OFFSET %s
                    """,
                        (limit, offset),
                    )

                    users = []
                    for row in cursor.fetchall():
                        users.append(
                            {
                                "user_id": row[0],
                                "username": row[1],
                                "first_name": row[2],
                                "last_name": row[3],
                                "joined_at": row[4],
                            }
                        )

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

    def get_user_details(self, user_id: int) -> dict[str, Any] | None:
        """Get detailed information about a specific user."""
        try:
            with closing(self._get_connection()) as conn:
                with closing(conn.cursor()) as cursor:
                    cursor.execute(
                        """
                        SELECT user_id, username, first_name, last_name, joined_at
                        FROM users
                        WHERE user_id = %s
                    """,
                        (user_id,),
                    )

                    user_row = cursor.fetchone()
                    if not user_row:
                        return None

                    cursor.execute("SELECT COUNT(*) FROM commands WHERE user_id = %s", (user_id,))
                    command_count = cursor.fetchone()[0]

                    cursor.execute("SELECT COUNT(*) FROM user_saved WHERE user_id = %s", (user_id,))
                    saved_files = cursor.fetchone()[0]

                    cursor.execute(
                        """
                        SELECT command, used_at FROM commands
                        WHERE user_id = %s
                        ORDER BY used_at DESC
                        LIMIT 5
                    """,
                        (user_id,),
                    )

                    recent_commands = []
                    for row in cursor.fetchall():
                        recent_commands.append({"command": row[0], "used_at": row[1]})

                    return {
                        "user_id": user_row[0],
                        "username": user_row[1],
                        "first_name": user_row[2],
                        "last_name": user_row[3],
                        "joined_at": user_row[4],
                        "command_count": command_count,
                        "saved_files": saved_files,
                        "recent_commands": recent_commands,
                    }
        except psycopg2.Error as e:
            self.logger.error(f"Error getting user details: {e}")
            return None

    def add_chat(self, chat_id: str) -> None:
        """Add or update a chat in the database."""
        query = "INSERT INTO chats (chat_id) VALUES (%s) ON CONFLICT (chat_id) DO NOTHING"
        self.execute_query(query, (chat_id,))

    def log_command(self, user_id: int, command: str) -> None:
        """Log a command usage in the database."""
        query = (
            "INSERT INTO commands (user_id, command, used_at) VALUES (%s, %s, CURRENT_TIMESTAMP)"
        )
        self.execute_query(query, (user_id, command))

    def save_file(self, user_id: int, file_id: str, file_type: str) -> None:
        """Record a file saved by a user."""
        query = "INSERT INTO user_saved (user_id, file_id, type, saved_at) VALUES (%s, %s, %s, CURRENT_TIMESTAMP)"
        self.execute_query(query, (user_id, file_id, file_type))

    def get_file_by_id(self, file_id: int) -> dict[str, Any] | None:
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
            "user_id": result[4],
        }

    def get_user_saved_files(
        self, user_id: int, page: int = 0, items_per_page: int = 5
    ) -> list[dict[str, Any]]:
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
            files.append({"id": row[0], "file_id": row[1], "type": row[2], "saved_at": row[3]})

        return files

    def get_stats(self) -> dict[str, Any]:
        """Get comprehensive statistics from the database."""
        stats = {}

        # User and chat counts
        stats["user_count"] = self.execute_query("SELECT COUNT(*) FROM users")[0][0]
        stats["chat_count"] = self.execute_query("SELECT COUNT(*) FROM chats")[0][0]

        # Top commands
        stats["top_commands"] = self.execute_query("""
            SELECT command, COUNT(*) FROM commands 
            GROUP BY command 
            ORDER BY COUNT(*) DESC 
            LIMIT 10
        """)

        # Recent active users
        stats["recent_users"] = self.execute_query("""
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
        stats["active_users"] = self.execute_query("""
            SELECT users.username, users.first_name, users.last_name, COUNT(commands.id) as cmd_count 
            FROM users 
            JOIN commands ON users.user_id = commands.user_id 
            GROUP BY users.user_id, users.username, users.first_name, users.last_name
            ORDER BY cmd_count DESC 
            LIMIT 10
        """)

        # Saved files stats
        stats["total_saved_files"] = self.execute_query("SELECT COUNT(*) FROM user_saved")[0][0]

        # Top file savers
        stats["top_savers"] = self.execute_query("""
            SELECT users.username, users.first_name, users.last_name, COUNT(user_saved.file_id) as file_count
            FROM users 
            JOIN user_saved ON users.user_id = user_saved.user_id
            GROUP BY users.user_id, users.username, users.first_name, users.last_name
            ORDER BY file_count DESC
            LIMIT 10
        """)

        return stats

    def get_user_stats(self, user_id: int) -> dict[str, Any]:
        """Get statistics for a specific user."""
        user_stats = {}

        # Basic user info
        user_info = self.execute_query(
            """
            SELECT username, first_name, last_name, joined_at
            FROM users
            WHERE user_id = %s
        """,
            (user_id,),
        )

        if not user_info:
            return {"error": "User not found"}

        user_stats["username"] = user_info[0][0]
        user_stats["first_name"] = user_info[0][1]
        user_stats["last_name"] = user_info[0][2]
        user_stats["joined_at"] = user_info[0][3]

        # Command count
        user_stats["command_count"] = self.execute_query(
            "SELECT COUNT(*) FROM commands WHERE user_id = %s", (user_id,)
        )[0][0]

        # Top commands used
        user_stats["top_commands"] = self.execute_query(
            """
            SELECT command, COUNT(*) 
            FROM commands 
            WHERE user_id = %s
            GROUP BY command 
            ORDER BY COUNT(*) DESC 
            LIMIT 5
        """,
            (user_id,),
        )

        # Saved files count
        user_stats["saved_files_count"] = self.execute_query(
            "SELECT COUNT(*) FROM user_saved WHERE user_id = %s", (user_id,)
        )[0][0]

        return user_stats

    def get_activity_timeline(self, days: int = 30) -> list[tuple[str, int]]:
        """Get command activity over a specified number of days."""
        return self.execute_query(
            """
            SELECT DATE(used_at) as day, COUNT(*) as count
            FROM commands
            WHERE used_at >= CURRENT_DATE - INTERVAL '%s days'
            GROUP BY DATE(used_at)
            ORDER BY day
        """,
            (days,),
        )

    def search_users(self, search_term: str) -> list[dict[str, Any]]:
        """Search users by username or user_id."""
        try:
            with closing(self._get_connection()) as conn:
                with closing(conn.cursor()) as cursor:
                    # Try to convert search term to integer for ID search
                    try:
                        user_id = int(search_term)
                        # Search by exact user_id or username containing the term
                        cursor.execute(
                            """
                            SELECT user_id, username, first_name, last_name, joined_at
                            FROM users
                            WHERE user_id = %s OR username ILIKE %s
                            ORDER BY 
                                CASE WHEN user_id = %s THEN 1 ELSE 2 END,
                                joined_at DESC
                            LIMIT 20
                        """,
                            (user_id, f"%{search_term}%", user_id),
                        )
                    except ValueError:
                        # Search only by username if not a number
                        cursor.execute(
                            """
                            SELECT user_id, username, first_name, last_name, joined_at
                            FROM users
                            WHERE username ILIKE %s OR first_name ILIKE %s OR last_name ILIKE %s
                            ORDER BY joined_at DESC
                            LIMIT 20
                        """,
                            (f"%{search_term}%", f"%{search_term}%", f"%{search_term}%"),
                        )

                    users = []
                    for row in cursor.fetchall():
                        users.append(
                            {
                                "user_id": row[0],
                                "username": row[1],
                                "first_name": row[2],
                                "last_name": row[3],
                                "joined_at": row[4],
                            }
                        )

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
                "pg_dump",
                f"--host={self.db_config['host']}",
                f"--port={self.db_config['port']}",
                f"--username={self.db_config['user']}",
                f"--dbname={self.db_config['dbname']}",
                "--no-password",
                "--clean",
                "--create",
            ]

            # Set password via environment variable
            import os

            env = os.environ.copy()
            env["PGPASSWORD"] = self.db_config["password"]

            with open(backup_path, "w") as f:
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

    # ----------------------------------------------------------------- jokes --

    def create_joke(
        self, chat_id: int, author_id: int, author_name: str, joke_message_id: int
    ) -> int | None:
        """Create a joke poll row and return its id."""
        try:
            with closing(self._get_connection()) as conn:
                with closing(conn.cursor()) as cursor:
                    cursor.execute(
                        """
                        INSERT INTO jokes (chat_id, author_id, author_name, joke_message_id)
                        VALUES (%s, %s, %s, %s)
                        RETURNING id
                        """,
                        (chat_id, author_id, author_name, joke_message_id),
                    )
                    joke_id = cursor.fetchone()[0]
                    conn.commit()
                    return joke_id
        except psycopg2.Error as e:
            self.logger.error(f"Error creating joke: {e}")
            return None

    def set_joke_poll_message(self, joke_id: int, poll_message_id: int) -> None:
        """Store the id of the bot's poll message for a joke."""
        try:
            with closing(self._get_connection()) as conn:
                with closing(conn.cursor()) as cursor:
                    cursor.execute(
                        "UPDATE jokes SET poll_message_id = %s WHERE id = %s",
                        (poll_message_id, joke_id),
                    )
                    conn.commit()
        except psycopg2.Error as e:
            self.logger.error(f"Error setting joke poll message: {e}")

    def get_joke(self, joke_id: int) -> dict[str, Any] | None:
        """Fetch a joke by id."""
        try:
            with closing(self._get_connection()) as conn:
                with closing(conn.cursor()) as cursor:
                    cursor.execute(
                        """
                        SELECT id, chat_id, author_id, author_name, joke_message_id, poll_message_id
                        FROM jokes WHERE id = %s
                        """,
                        (joke_id,),
                    )
                    row = cursor.fetchone()
                    if not row:
                        return None
                    return {
                        "id": row[0],
                        "chat_id": row[1],
                        "author_id": row[2],
                        "author_name": row[3],
                        "joke_message_id": row[4],
                        "poll_message_id": row[5],
                    }
        except psycopg2.Error as e:
            self.logger.error(f"Error getting joke {joke_id}: {e}")
            return None

    def upsert_vote(self, joke_id: int, voter_id: int, score: int) -> None:
        """Record (or change) a voter's 0-10 rating for a joke."""
        try:
            with closing(self._get_connection()) as conn:
                with closing(conn.cursor()) as cursor:
                    cursor.execute(
                        """
                        INSERT INTO joke_votes (joke_id, voter_id, score)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (joke_id, voter_id)
                        DO UPDATE SET score = %s, voted_at = CURRENT_TIMESTAMP
                        """,
                        (joke_id, voter_id, score, score),
                    )
                    conn.commit()
        except psycopg2.Error as e:
            self.logger.error(f"Error upserting vote: {e}")

    def get_joke_vote_summary(self, joke_id: int) -> tuple[int, float]:
        """Return (vote_count, average_score) for a joke."""
        try:
            with closing(self._get_connection()) as conn:
                with closing(conn.cursor()) as cursor:
                    cursor.execute(
                        "SELECT COUNT(*), COALESCE(AVG(score), 0) FROM joke_votes WHERE joke_id = %s",
                        (joke_id,),
                    )
                    row = cursor.fetchone()
                    return int(row[0]), round(float(row[1]), 1)
        except psycopg2.Error as e:
            self.logger.error(f"Error getting joke summary: {e}")
            return 0, 0.0

    def get_weekly_awards(self, chat_id: int, min_voters: int = 3) -> dict[str, Any]:
        """Compute weekly award winners for a chat over the last 7 days.

        Returns keys: best, bullshit, most_active, funniest, total_jokes.
        `best`/`bullshit` rank authors by average score over their qualifying
        jokes (>= min_voters distinct voters); `most_active` ranks by jokes
        posted; `funniest` is the single highest-rated qualifying joke.
        """
        awards: dict[str, Any] = {
            "best": None,
            "bullshit": None,
            "most_active": None,
            "funniest": None,
            "total_jokes": 0,
        }
        try:
            with closing(self._get_connection()) as conn:
                with closing(conn.cursor()) as cursor:
                    cursor.execute(
                        """
                        SELECT COUNT(*) FROM jokes
                        WHERE chat_id = %s AND created_at >= NOW() - INTERVAL '7 days'
                        """,
                        (chat_id,),
                    )
                    awards["total_jokes"] = int(cursor.fetchone()[0])
                    if awards["total_jokes"] == 0:
                        return awards

                    # Per-author averages over qualifying jokes (>= min_voters).
                    cursor.execute(
                        """
                        WITH window_jokes AS (
                            SELECT id, author_id, author_name
                            FROM jokes
                            WHERE chat_id = %s AND created_at >= NOW() - INTERVAL '7 days'
                        ),
                        qualifying AS (
                            SELECT wj.id, wj.author_id, wj.author_name
                            FROM window_jokes wj
                            JOIN joke_votes v ON v.joke_id = wj.id
                            GROUP BY wj.id, wj.author_id, wj.author_name
                            HAVING COUNT(v.id) >= %s
                        )
                        SELECT q.author_id, MAX(q.author_name),
                               AVG(v.score) AS avg_score, COUNT(DISTINCT q.id) AS jokes
                        FROM qualifying q
                        JOIN joke_votes v ON v.joke_id = q.id
                        GROUP BY q.author_id
                        ORDER BY avg_score DESC
                        """,
                        (chat_id, min_voters),
                    )
                    author_rows = cursor.fetchall()
                    if author_rows:
                        top = author_rows[0]
                        bottom = author_rows[-1]
                        awards["best"] = {
                            "author_id": top[0],
                            "author_name": top[1],
                            "avg": round(float(top[2]), 1),
                            "jokes": int(top[3]),
                        }
                        # Only call out "bullshit" if it's a different person.
                        if bottom[0] != top[0]:
                            awards["bullshit"] = {
                                "author_id": bottom[0],
                                "author_name": bottom[1],
                                "avg": round(float(bottom[2]), 1),
                                "jokes": int(bottom[3]),
                            }

                    # Most active: most jokes posted (any votes).
                    cursor.execute(
                        """
                        SELECT author_id, MAX(author_name), COUNT(*) AS jokes
                        FROM jokes
                        WHERE chat_id = %s AND created_at >= NOW() - INTERVAL '7 days'
                        GROUP BY author_id
                        ORDER BY jokes DESC
                        LIMIT 1
                        """,
                        (chat_id,),
                    )
                    row = cursor.fetchone()
                    if row:
                        awards["most_active"] = {
                            "author_id": row[0],
                            "author_name": row[1],
                            "jokes": int(row[2]),
                        }

                    # Funniest single joke (>= min_voters).
                    cursor.execute(
                        """
                        SELECT j.author_id, j.author_name,
                               AVG(v.score) AS avg_score, COUNT(v.id) AS voters
                        FROM jokes j
                        JOIN joke_votes v ON v.joke_id = j.id
                        WHERE j.chat_id = %s AND j.created_at >= NOW() - INTERVAL '7 days'
                        GROUP BY j.id, j.author_id, j.author_name
                        HAVING COUNT(v.id) >= %s
                        ORDER BY avg_score DESC
                        LIMIT 1
                        """,
                        (chat_id, min_voters),
                    )
                    row = cursor.fetchone()
                    if row:
                        awards["funniest"] = {
                            "author_id": row[0],
                            "author_name": row[1],
                            "avg": round(float(row[2]), 1),
                            "voters": int(row[3]),
                        }
            return awards
        except psycopg2.Error as e:
            self.logger.error(f"Error computing weekly awards: {e}")
            return awards

    def get_chat_leaderboard(
        self, chat_id: int, min_voters: int = 3, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Current-week author ranking by average score over qualifying jokes."""
        try:
            with closing(self._get_connection()) as conn:
                with closing(conn.cursor()) as cursor:
                    cursor.execute(
                        """
                        WITH window_jokes AS (
                            SELECT id, author_id, author_name
                            FROM jokes
                            WHERE chat_id = %s AND created_at >= NOW() - INTERVAL '7 days'
                        ),
                        qualifying AS (
                            SELECT wj.id, wj.author_id, wj.author_name
                            FROM window_jokes wj
                            JOIN joke_votes v ON v.joke_id = wj.id
                            GROUP BY wj.id, wj.author_id, wj.author_name
                            HAVING COUNT(v.id) >= %s
                        )
                        SELECT q.author_id, MAX(q.author_name),
                               AVG(v.score) AS avg_score, COUNT(DISTINCT q.id) AS jokes
                        FROM qualifying q
                        JOIN joke_votes v ON v.joke_id = q.id
                        GROUP BY q.author_id
                        ORDER BY avg_score DESC
                        LIMIT %s
                        """,
                        (chat_id, min_voters, limit),
                    )
                    return [
                        {
                            "author_id": r[0],
                            "author_name": r[1],
                            "avg": round(float(r[2]), 1),
                            "jokes": int(r[3]),
                        }
                        for r in cursor.fetchall()
                    ]
        except psycopg2.Error as e:
            self.logger.error(f"Error getting chat leaderboard: {e}")
            return []

    def get_user_joke_stats(self, chat_id: int, user_id: int) -> dict[str, Any]:
        """Joke stats for one user in one chat (this week + all time)."""
        stats: dict[str, Any] = {
            "jokes_week": 0,
            "avg_week": None,
            "jokes_all": 0,
            "avg_all": None,
            "votes_received": 0,
            "best_avg": None,
            "worst_avg": None,
        }
        try:
            with closing(self._get_connection()) as conn:
                with closing(conn.cursor()) as cursor:
                    cursor.execute(
                        """
                        SELECT COUNT(*) FROM jokes
                        WHERE chat_id = %s AND author_id = %s
                          AND created_at >= NOW() - INTERVAL '7 days'
                        """,
                        (chat_id, user_id),
                    )
                    stats["jokes_week"] = int(cursor.fetchone()[0])

                    cursor.execute(
                        """
                        SELECT AVG(v.score)
                        FROM jokes j JOIN joke_votes v ON v.joke_id = j.id
                        WHERE j.chat_id = %s AND j.author_id = %s
                          AND j.created_at >= NOW() - INTERVAL '7 days'
                        """,
                        (chat_id, user_id),
                    )
                    row = cursor.fetchone()
                    if row and row[0] is not None:
                        stats["avg_week"] = round(float(row[0]), 1)

                    cursor.execute(
                        "SELECT COUNT(*) FROM jokes WHERE chat_id = %s AND author_id = %s",
                        (chat_id, user_id),
                    )
                    stats["jokes_all"] = int(cursor.fetchone()[0])

                    cursor.execute(
                        """
                        SELECT AVG(v.score), COUNT(v.id)
                        FROM jokes j JOIN joke_votes v ON v.joke_id = j.id
                        WHERE j.chat_id = %s AND j.author_id = %s
                        """,
                        (chat_id, user_id),
                    )
                    row = cursor.fetchone()
                    if row and row[0] is not None:
                        stats["avg_all"] = round(float(row[0]), 1)
                        stats["votes_received"] = int(row[1])

                    # Best / worst joke (by per-joke average) all-time in this chat.
                    cursor.execute(
                        """
                        SELECT AVG(v.score) AS avg_score
                        FROM jokes j JOIN joke_votes v ON v.joke_id = j.id
                        WHERE j.chat_id = %s AND j.author_id = %s
                        GROUP BY j.id
                        ORDER BY avg_score DESC
                        """,
                        (chat_id, user_id),
                    )
                    joke_avgs = [round(float(r[0]), 1) for r in cursor.fetchall()]
                    if joke_avgs:
                        stats["best_avg"] = joke_avgs[0]
                        stats["worst_avg"] = joke_avgs[-1]
            return stats
        except psycopg2.Error as e:
            self.logger.error(f"Error getting user joke stats: {e}")
            return stats

    def get_active_joke_chats(self) -> list[int]:
        """Chats that had at least one joke in the last 7 days."""
        try:
            with closing(self._get_connection()) as conn:
                with closing(conn.cursor()) as cursor:
                    cursor.execute(
                        """
                        SELECT DISTINCT chat_id FROM jokes
                        WHERE created_at >= NOW() - INTERVAL '7 days'
                        """
                    )
                    return [int(r[0]) for r in cursor.fetchall()]
        except psycopg2.Error as e:
            self.logger.error(f"Error getting active joke chats: {e}")
            return []

    def weekly_run_exists(self, chat_id: int, week_end: str) -> bool:
        """Whether the weekly leaderboard was already posted for this chat/week."""
        try:
            with closing(self._get_connection()) as conn:
                with closing(conn.cursor()) as cursor:
                    cursor.execute(
                        "SELECT 1 FROM joke_weekly_runs WHERE chat_id = %s AND week_end = %s",
                        (chat_id, week_end),
                    )
                    return cursor.fetchone() is not None
        except psycopg2.Error as e:
            self.logger.error(f"Error checking weekly run: {e}")
            return False

    def mark_weekly_run(self, chat_id: int, week_end: str) -> None:
        """Mark the weekly leaderboard as posted for this chat/week."""
        try:
            with closing(self._get_connection()) as conn:
                with closing(conn.cursor()) as cursor:
                    cursor.execute(
                        """
                        INSERT INTO joke_weekly_runs (chat_id, week_end)
                        VALUES (%s, %s)
                        ON CONFLICT (chat_id, week_end) DO NOTHING
                        """,
                        (chat_id, week_end),
                    )
                    conn.commit()
        except psycopg2.Error as e:
            self.logger.error(f"Error marking weekly run: {e}")
