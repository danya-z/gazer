import psycopg2

class DBConnector:
  def __init__(self, host, port, database, user, password): # TODO: No type hints on parameters — add str annotations for clarity
    self.host = host
    self.port = port
    self.database = database
    self.user = user
    self.password = password # TODO: Password stored as plain attribute — consider clearing it after connect() succeeds, or at minimum marking it as private (_password)
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
    assert self.conn is not None, "Not connected to database" # TODO: assert can be disabled with python -O — use `if not self.conn: raise RuntimeError(...)` instead
    cur = self.conn.cursor() # TODO: Cursor is not closed if execute() or fetchall() raises — use a try/finally or `with self.conn.cursor() as cur:` context manager
    cur.execute(sql, params or ())
    results = cur.fetchall()
    cur.close()
    return results

  def execute_command(self, sql: str) -> int:
    """Execute INSERT/UPDATE/DELETE and return rowcount"""
    assert self.conn is not None, "Not connected to database" # TODO: Same assert issue — use a proper exception
    cur = self.conn.cursor() # TODO: Same cursor leak issue — if execute() or commit() raises, cursor is never closed. Use try/finally or context manager
    cur.execute(sql) # TODO: No parameterized query support — this method takes raw SQL with no params argument, making it vulnerable to SQL injection if user input is ever interpolated into the sql string
    rowcount = cur.rowcount
    self.conn.commit()
    cur.close()
    return rowcount

  def close(self):
    if self.conn:
      self.conn.close()
