import psycopg2
from psycopg2.extras import DictCursor


class DBConnector: # {{{
  """Manages a single PostgreSQL connection with query execution."""

  def __init__(self, host: str, port: str, database: str, user: str, password: str) -> None:
    self.host = host
    self.port = port
    self.database = database
    self.user = user
    self._password = password
    self.conn: psycopg2.extensions.connection | None = None

  def connect(self, timeout: int = 5) -> None:
    """Connect to database with timeout."""
    self.conn = psycopg2.connect(
      host=self.host,
      port=self.port,
      database=self.database,
      user=self.user,
      password=self._password,
      connect_timeout=timeout
    )
    self._password = None

  def execute_query_raw(self, sql: str, params: tuple | list | None = None) -> list[dict]:
    """Execute a SELECT query and return rows as a list of DictRows."""
    if not self.conn:
      raise RuntimeError("Not connected to database")
    with self.conn.cursor(cursor_factory=DictCursor) as cur:
      cur.execute(sql, params if params is not None else ())
      return cur.fetchall()

  def execute_command(self, sql: str, params: tuple | list | None = None) -> int:
    """Execute INSERT/UPDATE/DELETE and return rowcount."""
    if not self.conn:
      raise RuntimeError("Not connected to database")
    with self.conn.cursor() as cur:
      cur.execute(sql, params if params is not None else ())
      rowcount = cur.rowcount
      self.conn.commit()
    return rowcount

  def close(self) -> None:
    """Close the database connection."""
    if self.conn:
      self.conn.close()
# }}}
