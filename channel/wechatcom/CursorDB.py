import sqlite3
from contextlib import closing

class CursorDB:
    def __init__(self, db_path='cursor.db'):
        self.db_path = db_path
        self._initialize_db()

    def _initialize_db(self):
        with closing(self._get_connection()) as conn, conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cursor (
                    open_kfid TEXT PRIMARY KEY,
                    next_cursor TEXT
                )
            ''')

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def get_next_cursor(self, open_kfid):
        with closing(self._get_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT next_cursor FROM cursor WHERE open_kfid = ?', (open_kfid,))
            result = cursor.fetchone()
            return result[0] if result else None

    def save_next_cursor(self, open_kfid, next_cursor):
        with closing(self._get_connection()) as conn, conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO cursor (open_kfid, next_cursor)
                VALUES (?, ?)
                ON CONFLICT(open_kfid) DO UPDATE SET next_cursor=excluded.next_cursor
            ''', (open_kfid, next_cursor))
