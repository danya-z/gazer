from __future__ import annotations
from typing import TYPE_CHECKING, cast

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual import work
from textual.containers import Container, Vertical, ScrollableContainer
from textual.screen import Screen
from textual.widgets import Static, Input, Label, Header, Footer

from .ui_error import ErrorOverlay
from .ui_dropdown import Dropdown
from .ui_output import ResultsScreen, ExportDialog, PresetPicker, PresetSaver, SchemaScreen

if TYPE_CHECKING:
  from .ui_main import GazerApp
  from .core_sql_build import QueryBuilder


class SQLBuilderScreen(Screen): # {{{
  """Screen for building SQL queries with SELECT, ORDER BY, and FILTER panels."""

  BINDINGS = [
    ("escape", "app.pop_screen", "Back"),
    ("ctrl+r", "run_query", "Run Query"),
    ("ctrl+x", "export_query", "Export CSV"),
    ("ctrl+l", "load_preset", "Load Preset"),
    ("ctrl+s", "save_preset", "Save Preset"),
    ("ctrl+d", "toggle_distinct", "Toggle DISTINCT"),
    ("f1", "show_schema", "Schema"),
  ]

  def __init__(self, schema_inspector) -> None:
    """Initialize with a SchemaInspector instance."""
    super().__init__()
    self.inspector = schema_inspector
    self._schema_data: list[dict] = []
    self._column_lookup: dict[str, list[str]] = {}
    self._table_columns: dict[str, list[str]] = {}
    self._column_types: dict[str, str] = {}

  # Compose {{{
  def compose(self) -> ComposeResult:
    """Create the layout structure."""
    yield Header()
    yield Static("Query Builder", id="title")

    with Container(id="main-container"):
      # Left: SELECT panel (full height)
      with Vertical(id="select-panel"):
        yield Label("SELECT:", classes="section-title")
        yield Input(
          placeholder="Type [table_name].column_name here",
          classes="inline-input",
          id="select-input"
        )
        yield Dropdown(mode="select", id="select-dropdown")
        with ScrollableContainer(id="select-content", classes="content-area"):
          yield Static("Awaiting SELECT Input")

      # Right: ORDER BY + FILTER
      with Vertical(id="right-panel"):

        # Upper right: ORDER BY section
        with Container(id="order-section"):
          yield Label("ORDER BY:", classes="section-title")
          yield Input(
            placeholder="Type [table_name].column_name here",
            classes="inline-input",
            id="order-input"
          )
          yield Dropdown(mode="order", id="order-dropdown")
          with ScrollableContainer(id="order-content", classes="content-area"):
            yield Static("Awaiting ORDER Input")

        # Lower right: FILTER section
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
    "order-input": "order-dropdown",
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
      elif event.input.id == "order-input":
        # In DIRECTION stage, submit free text (defaults to ASC)
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
    elif result["type"] == "order":
      self._submit_order(result)

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

  def _submit_order(self, result: dict) -> None:
    """Add a completed ORDER BY entry to the query builder."""
    app = cast("GazerApp", self.app)
    query_builder = cast("QueryBuilder", app.query_builder)
    query_builder.add_order_by(result["column"], result["direction"])
    self.refresh_display()

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
    """Store schema and set up dropdowns."""
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

    # Pass schema data to all dropdowns
    for dropdown_id in ("select-dropdown", "filter-dropdown", "order-dropdown"):
      self.query_one(f"#{dropdown_id}", Dropdown).set_schema(
        self._table_columns, self._column_lookup,
        self._column_types, enum_values,
      )

    # Open the select dropdown (input is already focused)
    self.query_one("#select-dropdown", Dropdown).update("")
  # }}}

  # Displaying Query State {{{
  def refresh_display(self) -> None:
    """Update SELECT, ORDER BY, and FILTER panels from the query builder state."""
    app = cast("GazerApp", self.app)
    query_builder = cast("QueryBuilder", app.query_builder)

    state = query_builder.get_state()
    self._display_select(state)
    self._display_filters(state)
    self._display_order_by(state)

  def _display_select(self, state: dict) -> None:
    """Render current columns in the SELECT panel, with DISTINCT badge if active."""
    container = self.query_one("#select-content", ScrollableContainer)
    container.remove_children()

    if state.get('distinct'):
      container.mount(Static("[DISTINCT]", classes="distinct-badge"))

    columns = state['columns']
    if not columns:
      container.mount(Static("Awaiting SELECT Input"))
      return

    for col in columns:
      container.mount(Static(f"  - {col}"))

  def _display_order_by(self, state: dict) -> None:
    """Render current ORDER BY entries in the ORDER BY panel."""
    container = self.query_one("#order-content", ScrollableContainer)
    container.remove_children()

    order_by = state['order_by']
    if not order_by:
      container.mount(Static("Awaiting ORDER Input"))
      return

    for entry in order_by:
      container.mount(Static(f"  - {entry['column']} {entry['direction']}"))

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

  def _format_filter_tree(self, group, indent: int = 0) -> list[str]:
    """Recursively format a FilterGroup into display lines."""
    from .core_sql_build import Filter, FilterGroup
    lines: list[str] = []
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

  # Actions {{{
  def action_toggle_distinct(self) -> None:
    """Toggle DISTINCT on/off in the query builder."""
    app = cast("GazerApp", self.app)
    query_builder = cast("QueryBuilder", app.query_builder)
    query_builder.toggle_distinct()
    self.refresh_display()

  def action_show_schema(self) -> None:
    """Open the schema browser modal."""
    self.app.push_screen(SchemaScreen(self._schema_data))
  # }}}

  # Presets {{{
  def action_load_preset(self) -> None:
    """Open the preset picker modal."""
    self.app.push_screen(PresetPicker(), callback=self._on_preset_picked)

  def _on_preset_picked(self, columns: list[str] | None) -> None:
    """Callback when a preset is picked (or dismissed)."""
    if not columns:
      return

    app = cast("GazerApp", self.app)
    query_builder = cast("QueryBuilder", app.query_builder)

    valid: list[tuple[str, str]] = []
    for col_str in columns:
      if '.' not in col_str:
        continue
      table, column = col_str.split('.', 1)
      if table in self._table_columns and column in self._table_columns[table]:
        valid.append((table, column))

    if not valid:
      self.show_error("Preset", "No valid columns in this preset for the current schema.")
      return

    # Set base table from first valid column if not already set
    if query_builder._table is None:
      query_builder.set_table(valid[0][0])

    for table, column in valid:
      query_builder.add_column(column, table)

    self.refresh_display()

  def action_save_preset(self) -> None:
    """Open the preset saver modal with current columns."""
    app = cast("GazerApp", self.app)
    query_builder = cast("QueryBuilder", app.query_builder)
    columns = query_builder.get_state()['columns']
    self.app.push_screen(PresetSaver(columns))
  # }}}

  # Query Execution {{{
  def show_error(self, category: str, user_msg: str, technical: str = "") -> None:
    """Show an error overlay."""
    self.app.push_screen(ErrorOverlay(category, user_msg, technical or user_msg))

  def safe_build(self) -> tuple[str, list] | None:
    """Build the query, catching errors and showing them to the user.
    Called from worker threads — uses call_from_thread for UI.
    Returns (sql, params) on success, None on failure.
    """
    app = cast("GazerApp", self.app)
    query_builder = cast("QueryBuilder", app.query_builder)
    try:
      return query_builder.build()
    except (ValueError, RuntimeError) as e:
      self.app.call_from_thread(self.show_error, "Query", str(e))
      return None

  @work(thread=True)
  def action_run_query(self) -> None:
    """Build the query, execute it, and show results in a DataTable."""
    result = self.safe_build()
    if result is None:
      return

    sql, params = result
    app = cast("GazerApp", self.app)
    try:
      rows = app.db.execute_query_raw(sql, params)
      rows = [dict(r) for r in rows]
      self.app.call_from_thread(
        self.app.push_screen,
        ResultsScreen(sql, params, rows)
      )
    except Exception as e:
      error_msg = f"{type(e).__name__}: {e}"
      self.app.call_from_thread(self.show_error, "Query", error_msg)

  @work(thread=True)
  def action_export_query(self) -> None:
    """Build the query, execute it, and open the export dialog."""
    result = self.safe_build()
    if result is None:
      return

    sql, params = result
    app = cast("GazerApp", self.app)
    try:
      rows = app.db.execute_query_raw(sql, params)
      if not rows:
        self.app.call_from_thread(
          self.show_error, "Export", "Query returned no rows."
        )
        return
      # Convert DictCursor rows to plain dicts
      rows = [dict(r) for r in rows]
      self.app.call_from_thread(self.app.push_screen, ExportDialog(rows))
    except Exception as e:
      error_msg = f"{type(e).__name__}: {e}"
      self.app.call_from_thread(self.show_error, "Export", error_msg)
  # }}}
# }}}
