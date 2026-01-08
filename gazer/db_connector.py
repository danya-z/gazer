import psycopg2
import pandas as pd

class DBConnector:
  def __init__(self, host, port, database, user, password):
    self.host = host
    self.port = port
    self.database = database
    self.user = user
    self.password = password
    self.conn = None

    def connect(self):
      self.conn = psycopg2.connect(
        host=self.host,
        port=self.port,
        database=self.database,
        user=self.user,
        password=self.password
      )

    def execute_query(self, sql):
      cur = self.conn.cursor()
      cur.execute(sql)
      results = cur.fetchall()
      columns = [desc[0] for desc in cur.description]
      cur.close()
      return pd.DataFrame(results, columns=columns)

    def execute_raw(self, sql):
      cur = self.conn.cursor()
      cur.execute(sql)
      results = cur.fetchall()
      cur.close()
      return results

    def close(self):
      if self.conn:
        self.conn.close()
