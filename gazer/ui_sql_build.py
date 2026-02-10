from __future__ import annotations
from typing import TYPE_CHECKING, cast

from textual.app import ComposeResult
from textual import work
from textual.containers import Container, Vertical, ScrollableContainer
from textual.screen import Screen
from textual.widgets import Static, Input, Label, Header, Footer

from .ui_error import ErrorOverlay

if TYPE_CHECKING:
  from .ui_main import GazerApp
  from .core_sql_build import QueryBuilder

class SQLBuilderScreen(Screen):
  """Screen for building SQL queries with SELECT, FILTER, and SCHEMA panels."""

  BINDINGS = [
    ("escape", "app.pop_screen", "Back"),
  ]

  def __init__(self, schema_inspector):
    """Initialize, with a SchemaInspector instance."""
    super().__init__()
    self.inspector = schema_inspector
    self._schema_data: list[dict] = []
    self._column_lookup: dict[str, list[str]] = {}  # column_name -> [table_names]

  def compose(self) -> ComposeResult: # {{{
    """Create the layout structure."""
    yield Header()
    yield Static("Query Builder", id="title")

    with Container(id="main-container"):
      # Left side: Query builder (SELECT + FILTER) 
      with Vertical(id="builder-panel"):

        # Upper left: SELECT Screen
        with Container(id="select-section"):
          yield Label("SELECT:", classes="section-title")
          yield Input(
            placeholder="type selection here",
            classes="inline-input",
            id="select-input"
          )
          with ScrollableContainer(id="select-content", classes="content-area"):
            yield Static("Awaiting SELECT Input")

        # Lower left: FILTER Screen
        with Container(id="filter-section"):
          yield Label("FILTER:", classes="section-title")
          yield Input(
            placeholder="type filters here",
            classes="inline-input",
            id="filter-input"
          )
          with ScrollableContainer(id="filter-content", classes="content-area"):
            yield Static("Awaiting FILTER Input")
      
      # Right side: Schema browser 
      with Container(id="schema-panel"):
        yield Label("SCHEMA:", classes="section-title")
        with ScrollableContainer(id="schema-content"):
          yield Static("Fetching Schema...")

    yield Footer()
  # }}}

  def on_mount(self) -> None:
    """Called when screen is mounted."""
    self.query_one("#select-input", Input).focus()
    self.load_schema()

  # Input Handling {{{
  def on_input_submitted(self, event: Input.Submitted) -> None:
    if event.input.id == "select-input":
      self._handle_select_input(event.value.strip())
      event.input.value = ""

  def _resolve_column(self, text: str) -> tuple[str, str] | None:
    """Parse input into (table, column). Returns None on error.
    Accepts 'table.column' or bare 'column' (looked up from schema).
    """
    if '.' in text:
      parts = text.split('.', 1)
      return parts[0], parts[1]

    # Bare column — look up in schema
    tables = self._column_lookup.get(text, [])
    if len(tables) == 0:
      self.show_error("Select", f"Column '{text}' not found in any table.")
      return None
    if len(tables) > 1:
      self.show_error(
        "Select",
        f"Column '{text}' is ambiguous — found in: {', '.join(tables)}. Use table.column.",
      )
      return None
    return tables[0], text

  def _handle_select_input(self, text: str) -> None:
    if not text:
      return

    resolved = self._resolve_column(text)
    if resolved is None:
      return
    table, column = resolved

    app = cast("GazerApp", self.app)
    query_builder = cast("QueryBuilder", app.query_builder)

    # First column sets the FROM table
    if query_builder._table is None:
      query_builder.set_table(table)

    query_builder.add_column(column, table)
    self.refresh_display()
  # }}}

  # Loading and Displaying Schema {{{
  @work(exclusive=True, thread=True)
  def load_schema(self) -> None: 
    """Load schema data from the database in a background thread."""
    try:
      tables = self.inspector.get_tables()
      schema_data = []
      for table in tables:
        columns = self.inspector.get_columns(table)
        schema_data.append({
          'table': table,
          'columns': columns
        })

      self.app.call_from_thread(self.display_schema, schema_data)

    except Exception as e:
      error_msg = f"{type(e).__name__}: {e}"
      self.app.call_from_thread(self.show_error, "Schema", error_msg)

  def display_schema(self, schema_data: list) -> None:
    """Display the schema in the schema panel."""
    # Store for column lookups
    self._schema_data = schema_data
    self._column_lookup = {}
    for item in schema_data:
      for col in item['columns']:
        self._column_lookup.setdefault(col['name'], []).append(item['table'])

    container = self.query_one("#schema-content", ScrollableContainer)
    container.remove_children()

    for item in schema_data:
      table_name = item['table']
      columns = item['columns']

      container.mount(Static(table_name, classes="table-name"))
      for i, col in enumerate(columns):
        connector = "└─" if i == len(columns) - 1 else "├─"
        col_str = f"  {connector} {col['name']}; {col['udt_name']}"
        if col['is_primary_key']:
          col_str += "; PK"
        if col['is_foreign_key']:
          col_str += f"; FK→{col['fk_table']}.{col['fk_column']}"

        container.mount(Static(col_str))
      container.mount(Static(""))
  # }}}

  # Displaying Query State {{{
  def refresh_display(self) -> None:
    """Update SELECT and FILTER panels from the query builder state."""
    app = cast("GazerApp", self.app)
    query_builder = cast("QueryBuilder", app.query_builder)

    state = query_builder.get_state()
    self._display_select(state)
    self._display_filters(state)

  def _display_select(self, state: dict) -> None:
    """Render current table and columns in the SELECT panel."""
    container = self.query_one("#select-content", ScrollableContainer)
    container.remove_children()

    columns = state['columns']

    if not columns:
      container.mount(Static("Awaiting SELECT Input"))
      return

    for col in columns:
      container.mount(Static(f"  - {col}"))

  def _display_filters(self, state: dict) -> None:
    """Render current filters in the FILTER panel."""
    container = self.query_one("#filter-content", ScrollableContainer)
    container.remove_children()

    root = state['root_group']
    if root.is_empty():
      container.mount(Static("Awaiting FILTER Input"))
      return

    lines = self._format_filter_tree(root)
    for line in lines:
      container.mount(Static(line))

  def _format_filter_tree(self, group, indent=0) -> list[str]:
    """Recursively format a FilterGroup into display lines."""
    from .core_sql_build import Filter, FilterGroup
    lines = []
    prefix = "  " * indent
    children = group.children

    for i, child in enumerate(children):
      connector = "└─" if i == len(children) - 1 else "├─"

      if isinstance(child, Filter):
        lines.append(f"{prefix}{connector} {child}")
      elif isinstance(child, FilterGroup):
        lines.append(f"{prefix}{connector} {child.logic}")
        lines.extend(self._format_filter_tree(child, indent + 1))

    return lines
  # }}}

  def show_error(self, category: str, user_msg: str, technical: str = "") -> None:
    """Show an error overlay."""
    self.app.push_screen(ErrorOverlay(category, user_msg, technical or user_msg))

  def safe_build(self):
    """Build the query, catching errors and showing them to the user.
    Returns (sql, params) on success, None on failure.
    """
    app = cast("GazerApp", self.app)
    query_builder = cast("QueryBuilder", app.query_builder)
    try:
      return query_builder.build()
    except (ValueError, RuntimeError) as e:
      self.show_error("Query", str(e))
      return None
