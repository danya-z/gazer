import psycopg2

class DBConnector:
  def __init__(self, host, port, database, user, password):
    self.host = host
    self.port = port
    self.database = database
    self.user = user
    self.password = password
    self.conn = None

  def connect(self, timeout: int = 5):
    """Connect to database with timeout"""
    self.conn = psycopg2.connect(
      host=self.host,
      port=self.port,
      database=self.database,
      user=self.user,
      password=self.password,
      connect_timeout=timeout
    )

  def execute_query_raw(self, sql, params=None):
    """Execute SELECT query and return a set"""
    assert self.conn is not None, "Not connected to database"
    cur = self.conn.cursor()
    cur.execute(sql, params or ())
    results = cur.fetchall()
    cur.close()
    return results

  def execute_command(self, sql: str) -> int:
    """Execute INSERT/UPDATE/DELETE and return rowcount"""
    assert self.conn is not None, "Not connected to database"
    cur = self.conn.cursor()
    cur.execute(sql)
    rowcount = cur.rowcount
    self.conn.commit()
    cur.close()
    return rowcount

  def close(self):
    if self.conn:
      self.conn.close()
