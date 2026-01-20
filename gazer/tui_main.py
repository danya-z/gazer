from typing import cast
from textual import work # For threads
from textual.app import App, ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Input, TabbedContent, TabPane, Label
from textual.containers import Container, Vertical, Horizontal
from textual.binding import Binding

from db_connector import DBConnector
from schema_inspector import SchemaInspector
from query_builder import QueryBuilder
from memory import Config

#Gazer App {{{
class GazerApp(App):
  """Main Gazer TUI application."""
  TITLE = "Gazer"
  SUB_TITLE = "Database Query Builder"
  CSS_PATH = "gazer.tcss"
  BINDINGS = [
    Binding("escape", "quit", "Quit"),
  ]
  
  def __init__(self):
    super().__init__()
    self.db: DBConnector | None = None
    self.schema: SchemaInspector | None = None
    self.query_builder: QueryBuilder | None = None

  def on_mount(self):
    """Show connection screen on startup."""
    self.push_screen(ConnectionScreen())
  

  def cleanup_sync(self):
    """Synchronous cleanup for emergency shutdown"""
    if self.db is not None:
      try:
        self.db.close()
        self.log.info("Database connection closed (sync)")
      except Exception as e:
        self.log.error(f"Error closing database: {e}")

  async def cleanup(self):
    """Clean up database connection"""
    self.cleanup_sync()
  
  async def action_quit(self):
    """Quit application"""
    await self.cleanup()
    self.exit()
#}}}

# Connection Screen {{{
class ConnectionScreen(Screen):
  BINDINGS = [
    Binding("escape", "app.quit", "Quit"),
    # TODO, connection settings 
  ]

  def __init__(self):
    super().__init__()
    self.config = Config()

  def compose(self):
    yield Header()
    yield Static("Database Connection", id="title")
    yield Label(
      'Welcome to Gazer - the database query builder, written for bdi laboratory at Purdue.\n\n'
      'You can configure the connection settings by pressing ^s (Ctrl-S).\n'
      'Escape will bring you back, and ^c (Ctrl-C) will always kill the program.',
      id="welcome"
    )

    yield Label(f"Host:     {self.config.get_host()}")
    yield Label(f"Port:     {self.config.get_port()}")
    yield Label(f"Database: {self.config.get_database()}")

    yield Horizontal(
      Label("Username: "),
      Input(
        value=self.config.get_username(),
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
  
  def on_input_submitted(self, event: Input.Submitted):
    if event.input.id == "username":
      password_input = self.query_one("#password", Input)
      password_input.focus()
    elif event.input.id == "password":
      self.attempt_connection()

  def attempt_connection(self):
    error_display = self.query_one("#error_display", Static)

    host = self.config.get_host()
    port = self.config.get_port()
    database = self.config.get_database()
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

  # Connection animation {{{
  def start_connecting_animation(self):
    """Start animated 'Connecting...' message."""
    self._connecting = True
    self._animation_dots = 0
    self.set_interval(0.5, self.update_connecting_animation)
  
  def update_connecting_animation(self):
    """Update the connecting animation."""
    if not self._connecting:
      return

    error_display = self.query_one("#error_display", Static)
    self._animation_dots = (self._animation_dots) % 3 + 1
    dots = "." * self._animation_dots
    error_display.update(f"Connecting{dots}")

  def stop_connecting_animation(self):
    """Stop the connecting animation and clear message."""
    self._connecting = False
    error_display = self.query_one("#error_display", Static)
    error_display.update("")
  # }}}

  # DB Conection {{{
  # Runs in parallel to everything else
  @work(exclusive=True, thread=True)
  async def connect_worker(self, host: str, port: str, database: str, username:str, password: str):
    """Worker to handle the blocking database connection."""
    db = None
    try:
      db = DBConnector(host, port, database, username, password)
      db.connect()
      # Success
      self.app.call_from_thread(self.connection_success, db, username)
      
    except Exception as e:
      # Cleanup on failure
      if db is not None:
        try:
          db.close()
        except:
          pass
      self.app.call_from_thread(self.show_error, e)

  def connection_success(self, db: DBConnector, username: str):
    """Called on successful connection from main thread"""
    app = cast(GazerApp, self.app)

    self.stop_connecting_animation()
    self.config.set_username(username)
    app.db = db
    app.schema = SchemaInspector(db)
    app.query_builder = QueryBuilder()
    app.push_screen(QueryBuilderScreen())

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
      user_msg = "Cannot reach host - Check VPN connectio."
    else:
      user_msg = "Gazer does not recognize the error."

    self.app.push_screen(ErrorScreen(error_category, user_msg, raw_error))
  #}}}

#}}}

# Error Screen {{{
class ErrorScreen(Screen):
  """Screen for displaying and copying error messages"""
  BINDINGS = [
    Binding("escape", "app.pop_screen", "Back"),
    Binding("c", "copy_error", "Copy Error"),
  ]
  
  def __init__(self, error_category, user_message, technical_details):
    super().__init__()
    self.error_category = error_category
    self.user_message = user_message
    self.technical_details = technical_details
  
  def compose(self):
    yield Header()
    yield Static(f"{self.error_category} Error", id="title")
    
    yield Vertical(
      Static(f"{self.user_message}", classes="user-error"),
      Static("Technical Details:", classes="error-label"),
      Static(self.technical_details, id="error_details", classes="technical-error"),
      Static("Press 'c' to copy error (technical details) to clipboard", id="copy_hint", classes="hint"),
    )
    
    yield Footer()
  
  def action_copy_error(self):
    """Copy error to clipboard."""
    import pyperclip
    pyperclip.copy(self.technical_details)
    self.query_one("#copy_hint", Static).update(
      f"✓ Copied to clipboard!"
    )
#}}}

# SQL Builder Screen {{{
class CommandHistoryWidget(Static): # {{{
  """Shows committed commands (SELECT, FILTERS, JOINS)"""
  def __init__(self):
    super().__init__(id="command-history-panel")
    self.selections = []
    self.filters = []
    self.joins = []

  def render(self) -> str:
    lines = ["\033[1mSELECT:\033[0m"]
    if self.selections:
      for selection in self.selections:
        lines.append(f"  ✓ {selection}")
      else:
        lines.append("  (none)")

      lines.append("\n\033[1mFILTERS:\033[0m")
      if self.filters: # TODO Grouping
        for i, filter in enumerate(self.filters, 1):
          lines.append(f"  {i}. {filter}")
      else:
        lines.append("  (none)")

    return "\n".join(lines)

  def add_selection(self, column: str):
    self.selections.append(column)
    self.refresh()

  def add_filter(self, filter_expr: str):
    self.filters.append(filter_expr)
    self.refresh()
# }}}

class SchemaWidget(Static): # {{{
  """Shows database schema"""
  def __init__(self):
    super().__init__(id="schema-panel")
    self.schema = {
      "experiments": [
        ("id", "int4", "PK"),
        ("name", "text", ""),
        ("date", "date", ""),
        ("status", "experiment_status", "ENUM"),
      ],
      "trials": [
        ("id", "int4", "PK"),
        ("experiment_id", "int4", "FK→experiments"),
        ("value", "numeric", ""),
      ]
    }

  def render(self) -> str:
    lines = []
    for i, (table, columns) in enumerate(self.schema.items(), 1):
      lines.append(f"{i}: {table}")
      for col_name, col_type, extra in columns:
        extra_str = f"  ({extra})" if extra else ""
        lines.append(f"  - {col_name:<15} {col_type:<12}{extra_str}")
      lines.append("")
    return "\n".join(lines)
# }}}

class QueryBuilderScreen(Screen): # {{{
  """Main query-builder interface"""
  BINDINGS = [
    Binding("ctrl+s", "toggle_sql", "Toggle Direct SQL Mode"),
    Binding("escape", "app.pop_screen", "Back"),
  ]

  def __init__(self):
    super().__init__()
    self.show_sql = False

  def compose(self) -> ComposeResult:
    with Container(id="main-container"):
      yield Header()
      yield Footer()

      # Top bar
      yield Static("Gazer Query Builder", id="title")

      # Main content area
      with Horizontal(id="main-content"):
        yield CommandHistoryWidget()
        yield SchemaWidget()

      # Bottom: Command input
      yield Input(placeholder="Enter command (e.g., 'add experiments.id')", id="command-input")
      yield Static("Commands: select <table>.<column> | filter <condition>", id="help-bar")

  def action_toggle_sql(self):
    """Toggle direct SQL mode"""
    # TODO 
    return ()

  def on_input_submitted(self, event: Input.Submitted):
    """TODO Handle command submission"""
    return
# }}}
# }}}

def main():
  app = GazerApp()
  try:
    app.run()
  except KeyboardInterrupt:
    app.cleanup_sync()

if __name__ == '__main__':
  main()
