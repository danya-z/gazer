import atexit
from typing import cast

from textual import work
from textual.app import App, ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Input, Label
from textual.containers import Horizontal
from textual.binding import Binding
from textual.theme import Theme

from .core_connect import DBConnector
from .core_schema import SchemaInspector
from .core_sql_build import QueryBuilder
from .ui_sql_build import SQLBuilderScreen
from .ui_selection_panel import SchemaData
from .ui_error import ErrorOverlay
from .mem_config import Config
from .mem_schema import save_cache, load_cache


def _build_schema_data(schema_data_raw: list[dict],
                       enum_values: dict[str, list[str]] | None = None) -> SchemaData:
  """Build a SchemaData from raw column dicts."""
  table_columns: dict[str, list[str]] = {}
  column_lookup: dict[str, list[str]] = {}
  column_types: dict[str, str] = {}
  for item in schema_data_raw:
    table = item['table']
    col_names = []
    for col in item['columns']:
      col_names.append(col['name'])
      column_lookup.setdefault(col['name'], []).append(table)
      column_types[f"{table}.{col['name']}"] = col['udt_name']
    table_columns[table] = col_names
  return SchemaData(
    table_columns=table_columns,
    column_lookup=column_lookup,
    column_types=column_types,
    enum_values=enum_values or {},
  )


# GazerApp {{{
class GazerApp(App):
  """Main Gazer TUI application."""
  TITLE = "Gazer"
  SUB_TITLE = "Database Query Builder"
  CSS_PATH = "ui_gazer.tcss"
  ENABLE_COMMAND_PALETTE = False
  BINDINGS = [
    Binding("escape", "quit", "Quit"),
    Binding("ctrl+c", "app.quit", "Quit", show=False, priority=True),
  ]

  def __init__(self) -> None:
    super().__init__()
    self.register_theme(Theme(
      name="vscode-dark",
      primary="#2472c8",
      secondary="#11a8cd",
      background="#1e1e1e",
      foreground="#cccccc",
      surface="#252526",
      panel="#2d2d2d",
      accent="#3b8eea",
      error="#f14c4c",
      warning="#e5e510",
      success="#0dbc79",
      dark=True,
      variables={
        "border": "#3b8eea",
        "border-blurred": "#666666",
        "footer-background": "#252526",
        "footer-key-foreground": "#3b8eea",
        "input-cursor-background": "#cccccc",
        "input-cursor-foreground": "#1e1e1e",
        "scrollbar": "#666666",
      },
    ))
    self.theme = "vscode-dark"
    self.config = Config()
    self.db: DBConnector | None = None
    self.schema_inspector: SchemaInspector | None = None
    self.query_builder: QueryBuilder | None = None
    self.schema: SchemaData | None = None
    self.schema_data_raw: list[dict] = []
    self.fk_list: list[dict] = []

  def on_mount(self) -> None:
    """Show connection screen on startup."""
    self.push_screen(ConnectionScreen())

  def cleanup(self) -> None:
    """Synchronous cleanup for emergency shutdown."""
    if self.db is not None:
      try:
        self.db.close()
        self.log.info("Database connection closed (sync)")
      except Exception as e:
        self.log.error(f"Error closing database: {e}")

  async def action_quit(self) -> None:
    """Quit application."""
    self.cleanup()
    self.exit()
# }}}


# ConnectionScreen {{{
class ConnectionScreen(Screen):
  # Compose {{{
  def compose(self) -> ComposeResult:
    app = cast(GazerApp, self.app)

    yield Header()
    yield Static("Database Connection", id="title")
    yield Label(
      'Welcome to Gazer - the database query builder, written for bdi laboratory at Purdue.\n\n'
      'You can configure the connection settings by pressing ^s (Ctrl-S).\n'
      'Escape will bring you back, and ^c (Ctrl-C) will always kill the program.',
      id="welcome"
    )

    yield Label(f"Host:     {app.config.get_host()}")
    yield Label(f"Port:     {app.config.get_port()}")
    yield Label(f"Database: {app.config.get_database()}")

    yield Horizontal(
      Label("Username: "),
      Input(
        value=app.config.get_username(),
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

  def on_mount(self) -> None:
    app = cast(GazerApp, self.app)
    if app.config.get_username():
      self.query_one("#password", Input).focus()

  def on_input_submitted(self, event: Input.Submitted) -> None:
    if event.input.id == "username":
      self.query_one("#password", Input).focus()
    elif event.input.id == "password":
      self.attempt_connection()

  def attempt_connection(self) -> None:
    app = cast(GazerApp, self.app)
    error_display = self.query_one("#error_display", Static)

    host = app.config.get_host()
    port = app.config.get_port()
    database = app.config.get_database()
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

  # Connection Animation {{{
  def start_connecting_animation(self) -> None:
    """Start animated loading message."""
    self._connecting: bool = True
    self._animation_dots: int = 0
    self._animation_label: str = "Connecting"
    self._animation_timer = self.set_interval(0.5, self.update_connecting_animation)

  def update_connecting_animation(self) -> None:
    """Update the loading animation."""
    if not self._connecting:
      return

    error_display = self.query_one("#error_display", Static)
    dots = ["·..", ".·.", "..·"]
    error_display.update(f"{self._animation_label}{dots[self._animation_dots]}")
    self._animation_dots = (self._animation_dots + 1) % 3

  def _set_animation_label(self, label: str) -> None:
    """Change the loading animation text."""
    self._animation_label = label

  def stop_connecting_animation(self) -> None:
    """Stop the connecting animation and clear message."""
    self._connecting = False
    self._animation_timer.stop()
    self.query_one("#error_display", Static).update("")
  # }}}

  # DB Connection {{{
  @work(exclusive=True, thread=True)
  def connect_worker(self, host: str, port: str, database: str,
                     username: str, password: str) -> None:
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

    # Connection succeeded — resolve schema: memory > disk > DB
    app = cast(GazerApp, self.app)
    inspector = SchemaInspector(db)
    fk_list: list[dict] = []
    schema_data_raw: list[dict] = []
    schema: SchemaData | None = None

    if app.schema is not None:
      # In-memory cache (reconnect within same session)
      fk_list = app.fk_list
      schema = app.schema
      schema_data_raw = app.schema_data_raw
    else:
      self.app.call_from_thread(self._set_animation_label, "Fetching schema")
      # Try disk cache
      cached = load_cache(host, database)
      if cached and cached.get("schema_data"):
        fk_list = cached["foreign_keys"]
        schema_data_raw = cached["schema_data"]
        # Enum values aren't cached to disk — fetch them
        disk_enums: dict[str, list[str]] = {}
        for item in schema_data_raw:
          for col in item['columns']:
            udt = col['udt_name']
            if col['type'] == 'USER-DEFINED' and udt not in disk_enums:
              try:
                disk_enums[udt] = inspector.get_enum_values(udt)
              except Exception:
                pass
        schema = _build_schema_data(schema_data_raw, disk_enums)
      else:
        # Fetch from DB
        try:
          fk_list = inspector.fetch_all_foreign_keys()
        except Exception as e:
          error_msg = f"{type(e).__name__}: {e}"
          self.app.call_from_thread(self.show_schema_warning, error_msg)

        try:
          tables = inspector.get_tables()
          for table in tables:
            columns = inspector.get_columns(table)
            schema_data_raw.append({'table': table, 'columns': columns})

          enum_values: dict[str, list[str]] = {}
          for item in schema_data_raw:
            for col in item['columns']:
              udt = col['udt_name']
              if col['type'] == 'USER-DEFINED' and udt not in enum_values:
                enum_values[udt] = inspector.get_enum_values(udt)

          schema = _build_schema_data(schema_data_raw, enum_values)
          save_cache(host, database, fk_list, schema_data_raw)
        except Exception as e:
          error_msg = f"{type(e).__name__}: {e}"
          self.app.call_from_thread(self.show_schema_warning, error_msg)

    self.app.call_from_thread(
      self.connection_success, db, username, inspector, fk_list,
      schema, schema_data_raw,
    )

  def connection_success(self, db: DBConnector, username: str,
                         inspector: SchemaInspector, fk_list: list[dict],
                         schema: SchemaData | None,
                         schema_data_raw: list[dict]) -> None:
    """Called on successful connection from main thread."""
    app = cast(GazerApp, self.app)

    self.stop_connecting_animation()
    app.config.set_username(username)
    app.db = db
    app.schema_inspector = inspector
    app.schema = schema
    app.schema_data_raw = schema_data_raw
    app.fk_list = fk_list
    app.query_builder = QueryBuilder()
    app.query_builder.set_foreign_keys(fk_list)
    app.push_screen(SQLBuilderScreen())

  def show_schema_warning(self, error_msg: str) -> None:
    """Show non-fatal schema fetch error. Connection still proceeds."""
    self.app.push_screen(ErrorOverlay(
      "Schema",
      "Failed to load FK relationships. Auto-joins will not be available.",
      error_msg,
    ))

  def show_error(self, exception: Exception) -> None:
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
  # }}}
# }}}


def main() -> None:
  app = GazerApp()
  atexit.register(app.cleanup)
  app.run()


if __name__ == '__main__':
  main()
