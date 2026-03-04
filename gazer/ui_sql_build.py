from __future__ import annotations
from typing import TYPE_CHECKING, cast

from textual import work
from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.screen import Screen
from textual.widgets import Static, Header, Footer

from .ui_error import ErrorOverlay
from .core_sql_build import Filter, FilterGroup
from .ui_selection_panel import (
  SelectionPanel,
  make_select_pipeline, make_filter_pipeline, make_order_pipeline,
)
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

  def __init__(self) -> None:
    super().__init__()
    self._filter_map: dict[int, tuple[FilterGroup, Filter | FilterGroup]] = {}

  # Compose {{{
  def compose(self) -> ComposeResult:
    yield Header()
    yield Static("Query Builder", id="title")

    with Container(id="main-container"):
      yield SelectionPanel(
        title="SELECT:",
        pipeline=make_select_pipeline(),
        placeholder="Type [table_name].column_name here",
        id="select-panel",
      )
      with Vertical(id="right-panel"):
        yield SelectionPanel(
          title="ORDER BY:",
          pipeline=make_order_pipeline(),
          placeholder="Type [table_name].column_name here",
          id="order-section",
        )
        yield SelectionPanel(
          title="FILTER:",
          pipeline=make_filter_pipeline(),
          placeholder="Type filters here",
          id="filter-section",
        )

    yield Footer()

  def on_mount(self) -> None:
    app = cast("GazerApp", self.app)
    self.query_one("#select-panel-input").focus()
    if app.schema is not None:
      for panel_id in ("select-panel", "order-section", "filter-section"):
        self.query_one(f"#{panel_id}", SelectionPanel).set_schema(app.schema)
  # }}}

  # Message Handlers {{{
  def on_selection_panel_entry_added(self, event: SelectionPanel.EntryAdded) -> None:
    """Dispatch completed entries to QueryBuilder."""
    panel_id = event.panel.id
    if panel_id == "select-panel":
      self._handle_select_entry(event.result)
    elif panel_id == "filter-section":
      self._handle_filter_entry(event.result)
    elif panel_id == "order-section":
      self._handle_order_entry(event.result)

  def on_selection_panel_entry_removed(self, event: SelectionPanel.EntryRemoved) -> None:
    """Remove entries from QueryBuilder by data index."""
    panel_id = event.panel.id
    if panel_id == "select-panel":
      state = self._query_builder.get_state()
      for idx in sorted(event.indices, reverse=True):
        if 0 <= idx < len(state['columns']):
          self._query_builder.remove_column(state['columns'][idx])
    elif panel_id == "order-section":
      for idx in sorted(event.indices, reverse=True):
        self._query_builder.remove_order_by(idx)
    elif panel_id == "filter-section":
      for idx in sorted(event.indices, reverse=True):
        entry = self._filter_map.get(idx)
        if entry is None:
          continue
        parent, child = entry
        if child in parent.children:
          parent.children.remove(child)
    self._refresh_all_panels()

  def on_selection_panel_entries_grouped(self, event: SelectionPanel.EntriesGrouped) -> None:
    """Group selected filter entries into an AND/OR group."""
    if event.panel.id != "filter-section":
      return

    # Collect (parent, child) pairs
    items: list[tuple[FilterGroup, Filter | FilterGroup]] = []
    for idx in event.indices:
      entry = self._filter_map.get(idx)
      if entry is not None:
        items.append(entry)
    if len(items) < 2:
      return

    # Verify all share the same parent
    parents = {id(parent) for parent, _ in items}
    if len(parents) > 1:
      self.show_error("Group", "Can only group entries that share the same parent.")
      return

    parent = items[0][0]
    children_to_group = [child for _, child in items]

    # Find insertion position (earliest)
    insert_pos = min(parent.children.index(c) for c in children_to_group)

    # Remove from parent
    for child in children_to_group:
      parent.children.remove(child)

    # Create group and insert
    new_group = FilterGroup(logic=event.logic, children=children_to_group)
    parent.children.insert(insert_pos, new_group)

    self._refresh_all_panels()

  def on_selection_panel_entry_swapped(self, event: SelectionPanel.EntrySwapped) -> None:
    """Toggle a FilterGroup's logic between AND and OR."""
    if event.panel.id != "filter-section":
      return
    entry = self._filter_map.get(event.index)
    if entry is None:
      return
    _, child = entry
    if isinstance(child, FilterGroup):
      child.logic = "OR" if child.logic == "AND" else "AND"
      self._refresh_all_panels()

  def _handle_select_entry(self, result: dict) -> None:
    """Validate and add a column to the query builder."""
    text = result.get("text", "").strip()
    if not text:
      return

    resolved = self._resolve_column(text)
    if resolved is None:
      return
    table, column = resolved

    qb = self._query_builder
    if qb._table is None:
      qb.set_table(table)
    qb.add_column(column, table)
    self._refresh_all_panels()

  def _handle_filter_entry(self, result: dict) -> None:
    """Add a completed filter to the query builder."""
    column = result["column"]
    operator = result["operator"]
    value = result.get("value")

    qb = self._query_builder
    if '.' in column:
      table, col = column.split('.', 1)
      qb.add_filter(col, operator, value, table_name=table)
    else:
      qb.add_filter(column, operator, value)
    self._refresh_all_panels()

  def _handle_order_entry(self, result: dict) -> None:
    """Add a completed ORDER BY entry to the query builder."""
    qb = self._query_builder
    qb.add_order_by(result["column"], result["direction"])
    self._refresh_all_panels()

  def _resolve_column(self, text: str) -> tuple[str, str] | None:
    """Parse input into (table, column). Returns None on error."""
    if not self._app.schema:
      return None

    if '.' in text:
      table, column = text.split('.', 1)
      if not table:
        text = column
      else:
        if table not in self._app.schema.table_columns:
          self.show_error("Select", f"Table '{table}' not found in schema.")
          return None
        if column not in self._app.schema.table_columns[table]:
          self.show_error("Select", f"Column '{column}' not found in table '{table}'.")
          return None
        return table, column

    tables = self._app.schema.column_lookup.get(text, [])
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
  # }}}

  # Display {{{
  def _refresh_all_panels(self) -> None:
    """Update all panels from the query builder state."""
    state = self._query_builder.get_state()

    # SELECT
    select_entries: list[tuple[str, int | None]] = []
    if state.get('distinct'):
      select_entries.append(("[DISTINCT]", None))
    for i, col in enumerate(state['columns']):
      select_entries.append((f"  - {col}", i))
    self.query_one("#select-panel", SelectionPanel).set_entries(select_entries)

    # ORDER BY
    order_entries: list[tuple[str, int | None]] = [
      (f"  - {e['column']} {e['direction']}", i)
      for i, e in enumerate(state['order_by'])
    ]
    self.query_one("#order-section", SelectionPanel).set_entries(order_entries)

    # FILTER
    self._filter_map.clear()
    root = state['root_group']
    if root.is_empty():
      filter_entries: list[tuple[str, int | None]] = []
    else:
      # Root group header (selectable so it can be swapped)
      root_id = len(self._filter_map)
      self._filter_map[root_id] = (root, root)
      filter_entries: list[tuple[str, int | None]] = [(root.logic, root_id)]
      filter_entries.extend(self._format_filter_entries(root))
    self.query_one("#filter-section", SelectionPanel).set_entries(filter_entries)

  def _format_filter_entries(self, group: FilterGroup,
                             ancestors_last: list[bool] | None = None,
                             ) -> list[tuple[str, int | None]]:
    """Recursively format a FilterGroup into (text, entry_id) entries.
    Every entry gets a unique ID. _filter_map maps ID → (parent, child).

    ancestors_last tracks whether each ancestor is the last child in its
    parent, so we draw │ continuation lines or spaces accordingly.
    """
    if ancestors_last is None:
      ancestors_last = []

    entries: list[tuple[str, int | None]] = []
    children = group.children

    for i, child in enumerate(children):
      is_last = i == len(children) - 1

      # Build prefix: for each ancestor depth, │ if ancestor has siblings after it, else space
      prefix = "".join("   " if last else "│  " for last in ancestors_last)
      connector = "└─" if is_last else "├─"

      entry_id = len(self._filter_map)
      self._filter_map[entry_id] = (group, child)
      if isinstance(child, Filter):
        entries.append((f"{prefix}{connector} {child}", entry_id))
      elif isinstance(child, FilterGroup):
        entries.append((f"{prefix}{connector} {child.logic}", entry_id))
        entries.extend(self._format_filter_entries(
          child, ancestors_last + [is_last],
        ))

    return entries

  @property
  def _app(self) -> GazerApp:
    return cast("GazerApp", self.app)

  @property
  def _query_builder(self) -> QueryBuilder:
    return cast("QueryBuilder", self._app.query_builder)
  # }}}

  # Actions {{{
  def action_toggle_distinct(self) -> None:
    self._query_builder.toggle_distinct()
    self._refresh_all_panels()

  def action_show_schema(self) -> None:
    self.app.push_screen(SchemaScreen(self._app.schema_data_raw))
  # }}}

  # Presets {{{
  def action_load_preset(self) -> None:
    self.app.push_screen(PresetPicker(), callback=self._on_preset_picked)

  def _on_preset_picked(self, columns: list[str] | None) -> None:
    if not columns or not self._app.schema:
      return

    qb = self._query_builder
    valid: list[tuple[str, str]] = []
    for col_str in columns:
      if '.' not in col_str:
        continue
      table, column = col_str.split('.', 1)
      if table in self._app.schema.table_columns and column in self._app.schema.table_columns[table]:
        valid.append((table, column))

    if not valid:
      self.show_error("Preset", "No valid columns in this preset for the current schema.")
      return

    if qb._table is None:
      qb.set_table(valid[0][0])

    for table, column in valid:
      qb.add_column(column, table)

    self._refresh_all_panels()

  def action_save_preset(self) -> None:
    columns = self._query_builder.get_state()['columns']
    self.app.push_screen(PresetSaver(columns))
  # }}}

  # Query Execution {{{
  def show_error(self, category: str, user_msg: str, technical: str = "") -> None:
    self.app.push_screen(ErrorOverlay(category, user_msg, technical or user_msg))

  def safe_build(self) -> tuple[str, list] | None:
    """Build the query, catching errors. Called from worker threads."""
    try:
      return self._query_builder.build()
    except (ValueError, RuntimeError) as e:
      self.app.call_from_thread(self.show_error, "Query", str(e))
      return None

  @work(thread=True)
  def action_run_query(self) -> None:
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
      rows = [dict(r) for r in rows]
      self.app.call_from_thread(self.app.push_screen, ExportDialog(rows))
    except Exception as e:
      error_msg = f"{type(e).__name__}: {e}"
      self.app.call_from_thread(self.show_error, "Export", error_msg)
  # }}}
# }}}
