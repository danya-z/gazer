from __future__ import annotations
from typing import TYPE_CHECKING, cast
from enum import Enum, auto

from textual import events
from textual.app import ComposeResult
from textual import work
from textual.containers import Container, Vertical, ScrollableContainer
from textual.screen import Screen
from textual.widgets import Static, Input, Label, Header, Footer, OptionList

from .ui_error import ErrorOverlay

if TYPE_CHECKING:
  from .ui_main import GazerApp
  from .core_sql_build import QueryBuilder


class DropdownStage(Enum):
  """Which stage of the two-stage dropdown the user is in."""
  TABLE = auto()   # Choosing a table name
  COLUMN = auto()  # Choosing a column within a table


class SelectDropdown(OptionList):
  """Non-focusable dropdown overlay that appears below an input.
  Controlled entirely by the parent — never takes focus itself.
  Shows table names first, then column names after a dot is typed.
  """
  can_focus = False

  def __init__(self, **kwargs):
    super().__init__(**kwargs)
    self.stage: DropdownStage = DropdownStage.TABLE

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
    self._table_columns: dict[str, list[str]] = {}  # table_name -> [column_names]
    self._suppress_dropdown = False

  def compose(self) -> ComposeResult: # {{{
    """Create the layout structure."""
    yield Header()
    yield Static("Query Builder", id="title")

    with Container(id="main-container"):
      # Left side: Query builder (SELECT + FILTER) 
      with Vertical(id="builder-panel"):

        # Upper left: SELECT section
        with Container(id="select-section"):
          yield Label("SELECT:", classes="section-title")
          yield Input(
            placeholder="Type [table_name].column_name here",
            classes="inline-input",
            id="select-input"
          )
          yield SelectDropdown(id="select-dropdown")
          with ScrollableContainer(id="select-content", classes="content-area"):
            yield Static("Awaiting SELECT Input")

        # Lower left: FILTER section
        with Container(id="filter-section"):
          yield Label("FILTER:", classes="section-title")
          yield Input(
            placeholder="Type filters here",
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
  def on_input_changed(self, event: Input.Changed) -> None:
    """Update the dropdown as the user types in the select input."""
    if event.input.id != "select-input":
      return
    if self._suppress_dropdown:
      self._suppress_dropdown = False
      return
    self._update_dropdown(event.value)

  def on_input_submitted(self, event: Input.Submitted) -> None:
    """On Enter: if dropdown is open, pick the highlighted item.
    Otherwise, submit the input text to the query builder.
    """
    if event.input.id != "select-input":
      return

    dropdown = self.query_one("#select-dropdown", SelectDropdown)
    if self._is_dropdown_open() and dropdown.highlighted is not None:
      # Pick the highlighted dropdown item — fill input, don't submit yet
      event.stop()
      self._pick_highlighted()
    else:
      # No dropdown or nothing highlighted — submit to query builder
      self._close_dropdown()
      self._handle_select_input(event.value.strip())
      event.input.value = ""

  def on_key(self, event: events.Key) -> None:
    """Intercept Up/Down/Escape to control the dropdown from the input."""
    if not self.query_one("#select-input", Input).has_focus:
      return

    dropdown = self.query_one("#select-dropdown", SelectDropdown)
    if not self._is_dropdown_open():
      return

    if event.key == "down":
      event.stop()
      event.prevent_default()
      if dropdown.highlighted is None:
        dropdown.highlighted = 0
      elif dropdown.highlighted < dropdown.option_count - 1:
        dropdown.highlighted += 1
    elif event.key == "up":
      event.stop()
      event.prevent_default()
      if dropdown.highlighted is not None and dropdown.highlighted > 0:
        dropdown.highlighted -= 1
    elif event.key == "escape":
      event.stop()
      event.prevent_default()
      self._close_dropdown()

  def _pick_highlighted(self) -> None:
    """Pick the currently highlighted dropdown item and fill the input."""
    dropdown = self.query_one("#select-dropdown", SelectDropdown)
    select_input = self.query_one("#select-input", Input)

    if dropdown.highlighted is None:
      return
    option = dropdown.get_option_at_index(dropdown.highlighted)
    value = str(option.prompt)

    if dropdown.stage == DropdownStage.TABLE:
      # Fill input with "table." and switch to column stage
      select_input.value = f"{value}."
      # Move cursor to end
      select_input.cursor_position = len(select_input.value)
    elif dropdown.stage == DropdownStage.COLUMN:
      # Fill input with "table.column" (or bare column)
      # Suppress dropdown so on_input_changed doesn't reopen it
      self._suppress_dropdown = True
      table = select_input.value.split('.', 1)[0]
      if table:
        select_input.value = f"{table}.{value}"
      else:
        select_input.value = value
      # Move cursor to end
      select_input.cursor_position = len(select_input.value)
      self._close_dropdown()

  def _update_dropdown(self, text: str) -> None:
    """Populate and show/hide the dropdown based on current input text."""
    dropdown = self.query_one("#select-dropdown", SelectDropdown)
    section = self.query_one("#select-section")

    if not self._table_columns:
      section.remove_class("-dropdown-open")
      return

    if '.' in text and text.split('.', 1)[0]:
      # Stage 2: column suggestions for the given table
      table, col_prefix = text.split('.', 1)
      columns = self._table_columns.get(table, [])
      matches = [c for c in columns if c.lower().startswith(col_prefix.lower())]
      dropdown.stage = DropdownStage.COLUMN
    elif text.startswith('.'):
      # Bare column: "." prefix means skip table, show all columns
      col_prefix = text[1:]
      all_columns = list(self._column_lookup.keys())
      matches = [c for c in all_columns if c.lower().startswith(col_prefix.lower())]
      dropdown.stage = DropdownStage.COLUMN
    else:
      # Stage 1: table name suggestions (empty text shows all)
      tables = list(self._table_columns.keys())
      matches = [t for t in tables if t.lower().startswith(text.lower())]
      dropdown.stage = DropdownStage.TABLE

    dropdown.clear_options()
    if matches:
      for m in matches:
        dropdown.add_option(m)
      dropdown.highlighted = 0
      section.add_class("-dropdown-open")
    else:
      section.remove_class("-dropdown-open")

  def _is_dropdown_open(self) -> bool:
    """Check if the dropdown is currently visible."""
    return self.query_one("#select-section").has_class("-dropdown-open")

  def _close_dropdown(self) -> None:
    """Hide the dropdown."""
    self.query_one("#select-section").remove_class("-dropdown-open")

  def _resolve_column(self, text: str) -> tuple[str, str] | None:
    """Parse input into (table, column). Returns None on error.
    Accepts 'table.column' or bare 'column' (looked up from schema).
    """
    if '.' in text:
      table, column = text.split('.', 1)
      if not table:
        # Leading dot (e.g. ".column") — treat as bare column
        text = column
      else:
        if table not in self._table_columns:
          self.show_error("Select", f"Table '{table}' not found in schema.")
          return None
        if column not in self._table_columns[table]:
          self.show_error("Select", f"Column '{column}' not found in table '{table}'.")
          return None
        return table, column

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

    # Build table -> [column_name] map for dropdown
    self._table_columns: dict[str, list[str]] = {}
    for item in schema_data:
      self._table_columns[item['table']] = [
        col['name'] for col in item['columns']
      ]

    # Show all tables now that schema is ready (input is already focused)
    self._update_dropdown("")

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
