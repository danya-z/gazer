import atexit
from typing import cast
from textual import work
from textual.app import App
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Input, Label
from textual.containers import Horizontal
from textual.binding import Binding
from .core_connect import DBConnector
from .core_schema import SchemaInspector
from .core_sql_build import QueryBuilder
from .ui_sql_build import SQLBuilderScreen
from .ui_error import ErrorOverlay
from .mem_config import Config
from .mem_schema import save_cache

#Gazer App {{{
class GazerApp(App):
  """Main Gazer TUI application."""
  TITLE = "Gazer"
  SUB_TITLE = "Database Query Builder"
  CSS_PATH = "ui_gazer.tcss"
  BINDINGS = [
    Binding("escape", "quit", "Quit"),
  ]
  
  def __init__(self):
    super().__init__()
    self.config = Config()
    self.db: DBConnector | None = None
    self.schema_inspector: SchemaInspector | None = None
    self.query_builder: QueryBuilder | None = None

  def on_mount(self):
    """Show connection screen on startup."""
    self.push_screen(ConnectionScreen())
  

  def cleanup(self):
    """Synchronous cleanup for emergency shutdown"""
    if self.db is not None:
      try:
        self.db.close()
        self.log.info("Database connection closed (sync)")
      except Exception as e:
        self.log.error(f"Error closing database: {e}")

  async def action_quit(self):
    """Quit application"""
    self.cleanup()
    self.exit()
#}}}

# Connection Screen 
class ConnectionScreen(Screen):
  BINDINGS = [
    Binding("escape", "app.quit", "Quit"),
  ]

  # Compose and Call {{{
  def compose(self):
    yield Header()
    yield Static("Database Connection", id="title")
    yield Label(
      'Welcome to Gazer - the database query builder, written for bdi laboratory at Purdue.\n\n'
      'You can configure the connection settings by pressing ^s (Ctrl-S).\n'
      'Escape will bring you back, and ^c (Ctrl-C) will always kill the program.',
      id="welcome"
    )

    yield Label(f"Host:     {self.app.config.get_host()}")
    yield Label(f"Port:     {self.app.config.get_port()}")
    yield Label(f"Database: {self.app.config.get_database()}")

    yield Horizontal(
      Label("Username: "),
      Input(
        value=self.app.config.get_username(),
        placeholder="Enter username",
        classes="simple_input",
        id="username"
      )
    )
    yield Horizontal(
      Label("Password: "),
      Input(
        placeholder="Enter password",
        password=True,
        classes="simple_input",
        id="password"
      )
    )

    yield Static("", id="error_display")
    yield Footer()
  
  def on_mount(self):
    if self.app.config.get_username():
      self.query_one("#password", Input).focus()

  def on_input_submitted(self, event: Input.Submitted):
    if event.input.id == "username":
      password_input = self.query_one("#password", Input)
      password_input.focus()
    elif event.input.id == "password":
      self.attempt_connection()

  def attempt_connection(self):
    error_display = self.query_one("#error_display", Static)

    host = self.app.config.get_host()
    port = self.app.config.get_port()
    database = self.app.config.get_database()
    username = self.query_one("#username", Input).value
    password = self.query_one("#password", Input).value
    
    if not username:
      error_display.update("Username is required")
      return
    if not password:
      error_display.update("Password is required")
      return
    
    self.start_connecting_animation()
    self.connect_worker(host, port, database, username, password)
   # }}}

  # Connection animation {{{
  def start_connecting_animation(self):
    """Start animated 'Connecting...' message."""
    self._connecting = True
    self._animation_dots = 0
    self._animation_timer = self.set_interval(0.5, self.update_connecting_animation)
  
  def update_connecting_animation(self):
    """Update the connecting animation."""
    if not self._connecting:
      return

    error_display = self.query_one("#error_display", Static)
    animation_states = [
      "Connecting·..",
      "Connecting.·.",
      "Connecting..·",
    ]
    error_display.update(animation_states[self._animation_dots])
    self._animation_dots = (self._animation_dots + 1) % 3 

  def stop_connecting_animation(self):
    """Stop the connecting animation and clear message."""
    self._connecting = False
    self._animation_timer.stop()
    error_display = self.query_one("#error_display", Static)
    error_display.update("")
  # }}}

  # DB Connection {{{
  @work(exclusive=True, thread=True)
  def connect_worker(self, host: str, port: str, database: str, username: str, password: str):
    """Worker to handle the blocking database connection."""
    db = None
    try:
      db = DBConnector(host, port, database, username, password)
      db.connect(timeout=5)
    except Exception as e:
      if db is not None:
        try:
          db.close()
        except Exception:
          pass
      self.app.call_from_thread(self.show_error, e)
      return

    # Connection succeeded — fetch FK relationships (non-fatal if this fails)
    inspector = SchemaInspector(db)
    fk_list = []
    try:
      fk_list = inspector.fetch_all_foreign_keys()
      save_cache(host, database, fk_list)
    except Exception as e:
      error_msg = f"{type(e).__name__}: {e}"
      self.app.call_from_thread(
        self.show_schema_warning, error_msg
      )

    self.app.call_from_thread(self.connection_success, db, username, inspector, fk_list)

  def connection_success(self, db: DBConnector, username: str, inspector: SchemaInspector, fk_list: list):
    """Called on successful connection from main thread"""
    app = cast(GazerApp, self.app)

    self.stop_connecting_animation()
    self.app.config.set_username(username)
    app.db = db
    app.schema_inspector = inspector
    app.query_builder = QueryBuilder()
    app.query_builder.set_foreign_keys(fk_list)
    app.push_screen(SQLBuilderScreen(app.schema_inspector))

  def show_schema_warning(self, error_msg):
    """Show non-fatal schema fetch error. Connection still proceeds."""
    self.app.push_screen(ErrorOverlay(
      "Schema",
      "Failed to load FK relationships. Auto-joins will not be available.",
      error_msg,
    ))

  def show_error(self, exception):
    """Display error message screen."""
    self.stop_connecting_animation()
    error_category = "Connection"
    raw_error = str(exception)
    code_error = raw_error.lower()

    if "timeout" in code_error or "timed out" in code_error:
      user_msg = "Connection timeout - Are you on the VPN?"
    elif "authentication failed" in code_error:
      user_msg = "Authentication failed - Check password."
    elif "no pg_hba.conf entry for host" in code_error:
      user_msg = "Authentication failed - Check username."
    elif "could not translate host name" in code_error:
      user_msg = "Cannot reach host - Check VPN connection."
    else:
      user_msg = "Gazer does not recognize the error."

    self.app.push_screen(ErrorOverlay(error_category, user_msg, raw_error))
  #}}}

def main():
  app = GazerApp()
  atexit.register(app.cleanup)
  app.run()

if __name__ == '__main__':
  main()
