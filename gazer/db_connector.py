import psycopg2
from psycopg2.extras import DictCursor

class DBConnector:
  def __init__(self, host: str, port: str, database: str, user: str, password: str):
    self.host = host
    self.port = port
    self.database = database
    self.user = user
    self._password = password
    self.conn = None

  def connect(self, timeout: int = 5):
    """Connect to database with timeout"""
    self.conn = psycopg2.connect(
      host=self.host,
      port=self.port,
      database=self.database,
      user=self.user,
      password=self._password,
      connect_timeout=timeout
    )
    self._password = None

  def execute_query_raw(self, sql: str, params=None):
    """Execute SELECT query and return a set"""
    if not self.conn: raise RuntimeError("Not connected to database")
    with self.conn.cursor(cursor_factory=DictCursor) as cur:
      cur.execute(sql, params or ())
      results = cur.fetchall()

    return results

  def execute_command(self, sql: str, params=None) -> int:
    """Execute INSERT/UPDATE/DELETE and return rowcount"""
    if not self.conn: raise RuntimeError("Not connected to database")
    with self.conn.cursor(cursor_factory=DictCursor) as cur:
      cur.execute(sql, params or ())
      rowcount = cur.rowcount
      self.conn.commit()

    return rowcount

  def close(self):
    if self.conn:
      self.conn.close()
