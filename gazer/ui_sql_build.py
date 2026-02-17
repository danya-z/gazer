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

# Constants and enums {{{
# Operator suggestions by column type category
OPERATORS_BY_TYPE = {
  "numeric": ["=", "!=", "<", ">", "<=", ">=", "BETWEEN", "IN", "IS NULL", "IS NOT NULL"],
  "text":    ["=", "!=", "LIKE", "ILIKE", "NOT LIKE", "NOT ILIKE", "IN", "IS NULL", "IS NOT NULL"],
  "bool":    ["=", "IS NULL", "IS NOT NULL"],
  "enum":    ["=", "!=", "IN", "IS NULL", "IS NOT NULL"],
  "date":    ["=", "!=", "<", ">", "<=", ">=", "BETWEEN", "IS NULL", "IS NOT NULL"],
}

# Map PostgreSQL udt_name to type category
TYPE_CATEGORIES = {
  "int2": "numeric", "int4": "numeric", "int8": "numeric",
  "float4": "numeric", "float8": "numeric", "numeric": "numeric",
  "varchar": "text", "text": "text", "bpchar": "text", "char": "text",
  "bool": "bool",
  "date": "date", "timestamp": "date", "timestamptz": "date", "time": "date",
}


class DropdownStage(Enum):
  """Stages the dropdown can be in."""
  TABLE = auto()     # Choosing a table name
  COLUMN = auto()    # Choosing a column within a table
  OPERATOR = auto()  # Choosing a filter operator
  VALUE = auto()     # Choosing/entering a filter value
# }}}

class Dropdown(OptionList): # {{{
  """Non-focusable dropdown overlay that appears below an input.
  Controlled by the parent screen via update() and pick_highlighted().

  Two modes:
    "select" — TABLE → COLUMN, then done.
    "filter" — TABLE → COLUMN → OPERATOR → VALUE, then done.
  """
  can_focus = False

  def __init__(self, mode: str = "select", **kwargs):
    super().__init__(**kwargs)
    self.mode = mode
    self.stage: DropdownStage = DropdownStage.TABLE
    self._suppress = False

    # Schema data (set via set_schema)
    self._table_columns: dict[str, list[str]] = {}
    self._column_lookup: dict[str, list[str]] = {}
    self._column_types: dict[str, str] = {}   # "table.column" -> udt_name
    self._enum_values: dict[str, list[str]] = {}  # udt_name -> [values]

    # Filter construction state (filter mode only)
    self._picked_column: str = ""       # "table.column"
    self._picked_type: str = ""         # udt_name
    self._picked_operator: str = ""

  def set_schema(self, table_columns, column_lookup,
                 column_types=None, enum_values=None):
    """Provide schema data for suggestions."""
    self._table_columns = table_columns
    self._column_lookup = column_lookup
    self._column_types = column_types or {}
    self._enum_values = enum_values or {}

  # Open / Close {{{
  def open(self) -> None:
    """Show the dropdown by adding -dropdown-open to parent section."""
    section = self.parent
    if section is not None:
      section.add_class("-dropdown-open")

  def close(self) -> None:
    """Hide the dropdown."""
    section = self.parent
    if section is not None:
      section.remove_class("-dropdown-open")

  @property
  def is_open(self) -> bool:
    section = self.parent
    return section is not None and section.has_class("-dropdown-open")
  # }}}

  # Navigation {{{
  def move_highlight(self, direction: int) -> None:
    """Move the highlight up (-1) or down (+1)."""
    if self.option_count == 0:
      return
    if self.highlighted is None:
      self.highlighted = 0
    else:
      new = self.highlighted + direction
      if 0 <= new < self.option_count:
        self.highlighted = new
  # }}}

  # Update options based on input text {{{
  def update(self, text: str) -> None:
    """Populate the dropdown based on current input text and stage."""
    if self._suppress:
      self._suppress = False
      return

    if self.stage in (DropdownStage.TABLE, DropdownStage.COLUMN):
      self._update_column_stage(text)
    elif self.stage == DropdownStage.OPERATOR:
      self._update_operator_stage(text)
    elif self.stage == DropdownStage.VALUE:
      self._update_value_stage(text)

  def _update_column_stage(self, text: str) -> None:
    """Show table or column suggestions based on input text."""
    if not self._table_columns:
      self.close()
      return

    if '.' in text and text.split('.', 1)[0]:
      table, col_prefix = text.split('.', 1)
      columns = self._table_columns.get(table, [])
      matches = [c for c in columns if c.lower().startswith(col_prefix.lower())]
      self.stage = DropdownStage.COLUMN
    elif text.startswith('.'):
      col_prefix = text[1:]
      all_columns = list(self._column_lookup.keys())
      matches = [c for c in all_columns if c.lower().startswith(col_prefix.lower())]
      self.stage = DropdownStage.COLUMN
    else:
      tables = list(self._table_columns.keys())
      matches = [t for t in tables if t.lower().startswith(text.lower())]
      self.stage = DropdownStage.TABLE

    self._show_matches(matches)

  def _update_operator_stage(self, text: str) -> None:
    """Show operator suggestions filtered by text."""
    category = TYPE_CATEGORIES.get(self._picked_type, None)
    if self._picked_type and category is None:
      # Might be a USER-DEFINED enum type
      category = "enum"
    operators = OPERATORS_BY_TYPE.get(category, list(OPERATORS_BY_TYPE["text"]))
    matches = [op for op in operators if op.lower().startswith(text.lower())]
    self._show_matches(matches)

  def _update_value_stage(self, text: str) -> None:
    """Show value suggestions (enums, booleans) or leave open for free text."""
    category = TYPE_CATEGORIES.get(self._picked_type, None)

    if category == "bool":
      options = ["true", "false"]
      matches = [v for v in options if v.startswith(text.lower())]
      self._show_matches(matches)
    elif category is None and self._picked_type in self._enum_values:
      # Enum type
      values = self._enum_values[self._picked_type]
      matches = [v for v in values if v.lower().startswith(text.lower())]
      self._show_matches(matches)
    else:
      # Free text — no dropdown suggestions
      self.close()

  def _show_matches(self, matches: list[str]) -> None:
    """Populate with matches and open, or close if empty."""
    self.clear_options()
    if matches:
      for m in matches:
        self.add_option(m)
      self.highlighted = 0
      self.open()
    else:
      self.close()
  # }}}

  # Pick highlighted item {{{
  def pick_highlighted(self, input_widget: Input) -> dict | None:
    """Pick the highlighted option. Returns a result dict or None.

    For TABLE/COLUMN stages: fills the input, returns result when column
    is fully selected.
    For OPERATOR/VALUE stages: returns the completed filter info.

    Result dict keys:
      "type": "column" | "filter"
      For "column": "table", "column"
      For "filter": "column", "operator", "value"
    """
    if self.highlighted is None:
      return None
    option = self.get_option_at_index(self.highlighted)
    value = str(option.prompt)

    if self.stage == DropdownStage.TABLE:
      # Fill "table." and switch to column stage
      input_widget.value = f"{value}."
      input_widget.cursor_position = len(input_widget.value)
      return None

    elif self.stage == DropdownStage.COLUMN:
      # Assemble full column name
      table = input_widget.value.split('.', 1)[0]
      full_column = f"{table}.{value}" if table else value
      if self.mode == "select":
        # Fill input, close dropdown — user confirms with Enter
        self._suppress = True
        input_widget.value = full_column
        input_widget.cursor_position = len(input_widget.value)
        self.close()
        return None
      else:
        # Filter mode: store column, advance to OPERATOR
        self._picked_column = full_column
        # Look up type
        self._picked_type = self._column_types.get(full_column, "")
        self.stage = DropdownStage.OPERATOR
        input_widget.value = ""
        self.update("")
        return None

    elif self.stage == DropdownStage.OPERATOR:
      self._picked_operator = value
      if value in ("IS NULL", "IS NOT NULL"):
        # No value needed — return completed filter
        result = {
          "type": "filter",
          "column": self._picked_column,
          "operator": self._picked_operator,
          "value": None,
        }
        self._reset_filter_state()
        input_widget.value = ""
        self.update("")
        return result
      else:
        # Advance to VALUE stage
        self.stage = DropdownStage.VALUE
        input_widget.value = ""
        self.update("")
        return None

    elif self.stage == DropdownStage.VALUE:
      return self._submit_value(value, input_widget)

    return None

  def submit_text(self, text: str, input_widget: Input) -> dict | None:
    """Submit free text (Enter without picking from dropdown).
    Used for VALUE stage free text, or column confirmation in select mode.
    """
    if self.stage == DropdownStage.VALUE:
      return self._submit_value(text, input_widget)
    return None

  def _submit_value(self, raw_value: str, input_widget: Input) -> dict | None:
    """Parse and submit a value, returning a completed filter."""
    op = self._picked_operator
    if op == "BETWEEN":
      # Expect "low AND high"
      parts = raw_value.split(" AND ", 1)
      if len(parts) != 2:
        parts = raw_value.split(",", 1)
      if len(parts) != 2:
        return None  # Invalid — don't submit
      value = (parts[0].strip(), parts[1].strip())
    elif op in ("IN", "NOT IN"):
      # Comma-separated values
      value = [v.strip() for v in raw_value.split(",") if v.strip()]
      if not value:
        return None
    else:
      value = raw_value

    result = {
      "type": "filter",
      "column": self._picked_column,
      "operator": self._picked_operator,
      "value": value,
    }
    self._reset_filter_state()
    input_widget.value = ""
    self.update("")
    return result

  def _reset_filter_state(self) -> None:
    """Reset filter construction state back to column stage."""
    self.stage = DropdownStage.TABLE
    self._picked_column = ""
    self._picked_type = ""
    self._picked_operator = ""

  def get_progress_text(self) -> str:
    """Return text showing the filter being built."""
    if self.stage == DropdownStage.OPERATOR:
      return f"{self._picked_column} ..."
    elif self.stage == DropdownStage.VALUE:
      return f"{self._picked_column} {self._picked_operator} ..."
    return ""
  # }}}
# }}}

class SQLBuilderScreen(Screen): # {{{
  """Screen for building SQL queries with SELECT, FILTER, and SCHEMA panels."""

  BINDINGS = [
    ("escape", "app.pop_screen", "Back"),
  ]

  def __init__(self, schema_inspector):
    """Initialize with a SchemaInspector instance."""
    super().__init__()
    self.inspector = schema_inspector
    self._schema_data: list[dict] = []
    self._column_lookup: dict[str, list[str]] = {}
    self._table_columns: dict[str, list[str]] = {}
    self._column_types: dict[str, str] = {}

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
          yield Dropdown(mode="select", id="select-dropdown")
          with ScrollableContainer(id="select-content", classes="content-area"):
            yield Static("Awaiting SELECT Input")

        # Lower left: FILTER section
        with Container(id="filter-section"):
          yield Label("FILTER:", classes="section-title")
          yield Static("", id="filter-progress")
          yield Input(
            placeholder="Type filters here",
            classes="inline-input",
            id="filter-input"
          )
          yield Dropdown(mode="filter", id="filter-dropdown")
          with ScrollableContainer(id="filter-content", classes="content-area"):
            yield Static("Awaiting FILTER Input")

      # Right side: Schema browser
      with Container(id="schema-panel"):
        yield Label("SCHEMA:", classes="section-title")
        with ScrollableContainer(id="schema-content"):
          yield Static("Fetching Schema...")

    yield Footer()

  def on_mount(self) -> None:
    """Called when screen is mounted."""
    self.query_one("#select-input", Input).focus()
    self.load_schema()
  # }}}

  # Input-Dropdown Pairing {{{
  _PAIRS = {
    "select-input": "select-dropdown",
    "filter-input": "filter-dropdown",
  }

  def _active_dropdown(self) -> Dropdown | None:
    """Return the dropdown paired with the currently focused input."""
    for input_id, dropdown_id in self._PAIRS.items():
      if self.query_one(f"#{input_id}", Input).has_focus:
        return self.query_one(f"#{dropdown_id}", Dropdown)
    return None

  def _active_input(self) -> Input | None:
    """Return the currently focused input if it has a paired dropdown."""
    for input_id in self._PAIRS:
      inp = self.query_one(f"#{input_id}", Input)
      if inp.has_focus:
        return inp
    return None
  # }}}

  # Event Routing {{{
  def on_input_changed(self, event: Input.Changed) -> None:
    """Route input changes to the paired dropdown."""
    dropdown_id = self._PAIRS.get(event.input.id)
    if dropdown_id is None:
      return
    dropdown = self.query_one(f"#{dropdown_id}", Dropdown)
    dropdown.update(event.value)
    # Update filter progress label
    if event.input.id == "filter-input":
      self.query_one("#filter-progress", Static).update(dropdown.get_progress_text())

  def on_input_submitted(self, event: Input.Submitted) -> None:
    """On Enter: pick from dropdown, or submit the input text."""
    dropdown_id = self._PAIRS.get(event.input.id)
    if dropdown_id is None:
      return

    dropdown = self.query_one(f"#{dropdown_id}", Dropdown)

    if dropdown.is_open and dropdown.highlighted is not None:
      # Pick from dropdown
      event.stop()
      result = dropdown.pick_highlighted(event.input)
      self._handle_result(result, event.input)
    else:
      # Submit text directly
      text = event.value.strip()
      if event.input.id == "select-input":
        dropdown.close()
        self._handle_select_input(text)
        event.input.value = ""
      elif event.input.id == "filter-input":
        # In VALUE stage, submit free text
        result = dropdown.submit_text(text, event.input)
        self._handle_result(result, event.input)

    # Update filter progress label
    if event.input.id == "filter-input":
      self.query_one("#filter-progress", Static).update(dropdown.get_progress_text())

  def on_key(self, event: events.Key) -> None:
    """Intercept Up/Down/Escape/Tab to control the active dropdown."""
    dropdown = self._active_dropdown()
    if dropdown is None or not dropdown.is_open:
      return

    if event.key == "down" or event.key == "tab":
      event.stop()
      event.prevent_default()
      dropdown.move_highlight(1)
    elif event.key == "up":
      event.stop()
      event.prevent_default()
      dropdown.move_highlight(-1)
    elif event.key == "escape":
      event.stop()
      event.prevent_default()
      dropdown.close()
  # }}}

  # Handling Results {{{
  def _handle_result(self, result: dict | None, input_widget: Input) -> None:
    """Act on a completed pick from a dropdown."""
    if result is None:
      return

    if result["type"] == "filter":
      self._submit_filter(result)

  def _submit_filter(self, result: dict) -> None:
    """Add a completed filter to the query builder."""
    app = cast("GazerApp", self.app)
    query_builder = cast("QueryBuilder", app.query_builder)

    column = result["column"]
    operator = result["operator"]
    value = result["value"]

    # Split "table.column" for add_filter
    if '.' in column:
      table, col = column.split('.', 1)
      query_builder.add_filter(col, operator, value, table_name=table)
    else:
      query_builder.add_filter(column, operator, value)

    self.refresh_display()
    # Clear progress label
    self.query_one("#filter-progress", Static).update("")

  def _resolve_column(self, text: str) -> tuple[str, str] | None:
    """Parse input into (table, column). Returns None on error.
    Accepts 'table.column' or bare 'column' (looked up from schema).
    """
    if '.' in text:
      table, column = text.split('.', 1)
      if not table:
        text = column
      else:
        if table not in self._table_columns:
          self.show_error("Select", f"Table '{table}' not found in schema.")
          return None
        if column not in self._table_columns[table]:
          self.show_error("Select", f"Column '{column}' not found in table '{table}'.")
          return None
        return table, column

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
    """Validate and add a column to the query builder."""
    if not text:
      return

    resolved = self._resolve_column(text)
    if resolved is None:
      return
    table, column = resolved

    app = cast("GazerApp", self.app)
    query_builder = cast("QueryBuilder", app.query_builder)

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

      # Prefetch enum values (DB calls, must be in worker thread)
      enum_values: dict[str, list[str]] = {}
      for item in schema_data:
        for col in item['columns']:
          udt = col['udt_name']
          if col['type'] == 'USER-DEFINED' and udt not in enum_values:
            enum_values[udt] = self.inspector.get_enum_values(udt)

      self.app.call_from_thread(self.display_schema, schema_data, enum_values)

    except Exception as e:
      error_msg = f"{type(e).__name__}: {e}"
      self.app.call_from_thread(self.show_error, "Schema", error_msg)

  def display_schema(self, schema_data: list, enum_values: dict) -> None:
    """Display the schema and set up dropdowns."""
    self._schema_data = schema_data

    # Build lookup structures
    self._column_lookup = {}
    self._table_columns = {}
    self._column_types = {}
    for item in schema_data:
      table = item['table']
      col_names = []
      for col in item['columns']:
        col_names.append(col['name'])
        self._column_lookup.setdefault(col['name'], []).append(table)
        self._column_types[f"{table}.{col['name']}"] = col['udt_name']
      self._table_columns[table] = col_names

    # Pass schema data to both dropdowns
    for dropdown_id in ("select-dropdown", "filter-dropdown"):
      self.query_one(f"#{dropdown_id}", Dropdown).set_schema(
        self._table_columns, self._column_lookup,
        self._column_types, enum_values,
      )

    # Open the select dropdown (input is already focused)
    self.query_one("#select-dropdown", Dropdown).update("")

    # Render schema tree
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
    """Render current columns in the SELECT panel."""
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
# }}}
