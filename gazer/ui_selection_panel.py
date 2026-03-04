from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Static, Input, Label

from .ui_autocomplete import Autocomplete


# Schema data container {{{
@dataclass
class SchemaData:
  """Immutable container for schema information."""
  table_columns: dict[str, list[str]] = field(default_factory=dict)
  column_lookup: dict[str, list[str]] = field(default_factory=dict)
  column_types:  dict[str, str]       = field(default_factory=dict)
  enum_values:   dict[str, list[str]] = field(default_factory=dict)
# }}}


# Stage pipeline {{{
@dataclass
class Stage:
  """One step in a panel's multi-step input pipeline.

  get_options(schema, partial_state, text) -> list[str]
  on_pick(partial_state, picked_value, raw_text) -> result dict
  """
  name: str
  get_options: Callable[[SchemaData, dict, str], list[str]]
  on_pick: Callable[[dict, str, str], dict]
  allow_freetext: bool = False
  placeholder: Callable[[dict], str] | None = None
# }}}


# Constants {{{
OPERATORS_BY_TYPE = {
  "numeric": ["=", "!=", "<", ">", "<=", ">=", "BETWEEN", "IN", "IS NULL", "IS NOT NULL"],
  "text":    ["=", "!=", "LIKE", "ILIKE", "NOT LIKE", "NOT ILIKE", "IN", "IS NULL", "IS NOT NULL"],
  "bool":    ["=", "IS NULL", "IS NOT NULL"],
  "enum":    ["=", "!=", "IN", "IS NULL", "IS NOT NULL"],
  "date":    ["=", "!=", "<", ">", "<=", ">=", "BETWEEN", "IS NULL", "IS NOT NULL"],
}

TYPE_CATEGORIES = {
  "int2": "numeric", "int4": "numeric", "int8": "numeric",
  "float4": "numeric", "float8": "numeric", "numeric": "numeric",
  "varchar": "text", "text": "text", "bpchar": "text", "char": "text",
  "bool": "bool",
  "date": "date", "timestamp": "date", "timestamptz": "date", "time": "date",
}
# }}}


# Shared stage helpers {{{
def _column_get_options(schema: SchemaData, state: dict, text: str) -> list[str]:
  """Table/column autocomplete options shared by all pipelines."""
  if '.' in text and text.split('.', 1)[0]:
    table, col_prefix = text.split('.', 1)
    columns = schema.table_columns.get(table, [])
    return [c for c in columns if c.lower().startswith(col_prefix.lower())]
  elif text.startswith('.'):
    col_prefix = text[1:]
    all_columns = list(schema.column_lookup.keys())
    return [c for c in all_columns if c.lower().startswith(col_prefix.lower())]
  else:
    tables = list(schema.table_columns.keys())
    return [t for t in tables if t.lower().startswith(text.lower())]


def _column_on_pick_fill(state: dict, picked: str, raw_text: str) -> dict:
  """Pick handler for column stage — fills table. or assembles table.column."""
  if raw_text.startswith('.'):
    # Bare column pick (user typed ".col_prefix")
    return {"column": picked, "_fill_input": ""}
  if '.' not in raw_text:
    # Picked a table name
    return {"_fill_input": f"{picked}.", "_advance": False}
  table = raw_text.split('.', 1)[0]
  full_column = f"{table}.{picked}"
  return {"column": full_column, "_fill_input": ""}
# }}}


# SELECT pipeline {{{
def _select_on_pick(state: dict, picked: str, raw_text: str) -> dict:
  """Select mode: fill table., fill table.column, or submit freetext."""
  # Freetext submission (Enter when autocomplete is closed)
  if picked == raw_text:
    return {"complete": True, "text": raw_text}
  # Bare column pick (user typed ".col_prefix")
  if raw_text.startswith('.'):
    return {"_fill_input": picked, "_close_autocomplete": True, "_advance": False}
  # Picked a table name
  if '.' not in raw_text:
    return {"_fill_input": f"{picked}.", "_advance": False}
  # Picked a column name (user typed "table.col_prefix")
  table = raw_text.split('.', 1)[0]
  full_column = f"{table}.{picked}"
  return {"_fill_input": full_column, "_close_autocomplete": True, "_advance": False}


def make_select_pipeline() -> list[Stage]:
  return [
    Stage(
      name="column",
      get_options=_column_get_options,
      on_pick=_select_on_pick,
      allow_freetext=True,
    ),
  ]
# }}}


# FILTER pipeline {{{
def _filter_column_on_pick(state: dict, picked: str, raw_text: str) -> dict:
  """Filter column pick: fill table. or store column and advance to operator."""
  return _column_on_pick_fill(state, picked, raw_text)


def _filter_operator_options(schema: SchemaData, state: dict, text: str) -> list[str]:
  column = state.get("column", "")
  udt_name = schema.column_types.get(column, "")
  category = TYPE_CATEGORIES.get(udt_name)
  if udt_name and category is None:
    category = "enum"
  operators = OPERATORS_BY_TYPE.get(category, OPERATORS_BY_TYPE["text"])
  return [op for op in operators if op.lower().startswith(text.lower())]


def _filter_operator_on_pick(state: dict, picked: str, raw_text: str) -> dict:
  if picked in ("IS NULL", "IS NOT NULL"):
    return {
      "complete": True,
      "column": state["column"],
      "operator": picked,
      "value": None,
    }
  return {"operator": picked, "_fill_input": ""}


def _filter_value_options(schema: SchemaData, state: dict, text: str) -> list[str]:
  column = state.get("column", "")
  udt_name = schema.column_types.get(column, "")
  category = TYPE_CATEGORIES.get(udt_name)
  if category == "bool":
    return [v for v in ["true", "false"] if v.startswith(text.lower())]
  elif category is None and udt_name in schema.enum_values:
    values = schema.enum_values[udt_name]
    return [v for v in values if v.lower().startswith(text.lower())]
  return []


def _filter_value_on_pick(state: dict, picked: str, raw_text: str) -> dict:
  op = state.get("operator", "")
  if op == "BETWEEN":
    parts = picked.split(" AND ", 1)
    if len(parts) != 2:
      parts = picked.split(",", 1)
    if len(parts) != 2:
      return {"_advance": False}
    value: Any = (parts[0].strip(), parts[1].strip())
  elif op in ("IN", "NOT IN"):
    value = [v.strip() for v in picked.split(",") if v.strip()]
    if not value:
      return {"_advance": False}
  else:
    value = picked
  return {
    "complete": True,
    "column": state["column"],
    "operator": state["operator"],
    "value": value,
  }


def make_filter_pipeline() -> list[Stage]:
  return [
    Stage(
      name="column",
      get_options=_column_get_options,
      on_pick=_filter_column_on_pick,
    ),
    Stage(
      name="operator",
      get_options=_filter_operator_options,
      on_pick=_filter_operator_on_pick,
      placeholder=lambda s: f"{s.get('column', '')} ...",
    ),
    Stage(
      name="value",
      get_options=_filter_value_options,
      on_pick=_filter_value_on_pick,
      allow_freetext=True,
      placeholder=lambda s: f"{s.get('column', '')} {s.get('operator', '')} ...",
    ),
  ]
# }}}


# ORDER BY pipeline {{{
def _order_column_on_pick(state: dict, picked: str, raw_text: str) -> dict:
  """Order column pick: fill table. or store column and advance to direction."""
  return _column_on_pick_fill(state, picked, raw_text)


def _order_direction_options(schema: SchemaData, state: dict, text: str) -> list[str]:
  return [o for o in ["ASC", "DESC"] if o.lower().startswith(text.lower())]


def _order_direction_on_pick(state: dict, picked: str, raw_text: str) -> dict:
  direction = picked.strip().upper()
  if direction not in ("ASC", "DESC"):
    direction = "ASC"
  return {
    "complete": True,
    "column": state["column"],
    "direction": direction,
  }


def make_order_pipeline() -> list[Stage]:
  return [
    Stage(
      name="column",
      get_options=_column_get_options,
      on_pick=_order_column_on_pick,
    ),
    Stage(
      name="direction",
      get_options=_order_direction_options,
      on_pick=_order_direction_on_pick,
      allow_freetext=True,
      placeholder=lambda s: f"{s.get('column', '')} [ASC/DESC?]",
    ),
  ]
# }}}


# SelectionPanel widget {{{
class SelectionPanel(Widget):
  """Composed widget: Input + Autocomplete + content area with a stage pipeline.
  Posts EntryAdded upward when the pipeline completes.
  The parent Screen calls set_content() to update the display.
  """

  class EntryAdded(Message):
    """Pipeline completed — a new entry was produced."""
    def __init__(self, panel: SelectionPanel, result: dict) -> None:
      super().__init__()
      self.panel = panel
      self.result = result

  def __init__(
    self,
    title: str,
    pipeline: list[Stage],
    placeholder: str = "Type here...",
    **kwargs,
  ) -> None:
    super().__init__(**kwargs)
    self._title = title
    self._pipeline = pipeline
    self._placeholder = placeholder
    self._stage_index: int = 0
    self._partial_state: dict = {}
    self._schema: SchemaData | None = None
    self._suppress_input_change: bool = False

  # Compose {{{
  def compose(self) -> ComposeResult:
    yield Label(self._title, classes="section-title")
    yield Input(
      placeholder=self._placeholder,
      classes="inline-input",
      id=f"{self.id}-input",
    )
    yield Autocomplete(id=f"{self.id}-autocomplete")
    with ScrollableContainer(id=f"{self.id}-content", classes="content-area"):
      yield Static(f"Awaiting {self._title.rstrip(':')} Input")
  # }}}

  # Schema {{{
  def set_schema(self, schema: SchemaData) -> None:
    self._schema = schema
  # }}}

  # Pipeline control {{{
  @property
  def _current_stage(self) -> Stage:
    return self._pipeline[self._stage_index]

  def _refresh_options(self, text: str) -> None:
    """Ask current stage for options and push to autocomplete."""
    if self._schema is None:
      return
    autocomplete = self.query_one(f"#{self.id}-autocomplete", Autocomplete)
    options = self._current_stage.get_options(self._schema, self._partial_state, text)
    autocomplete.set_options(options)

  def _advance_or_complete(self, result: dict) -> None:
    """Process stage result: fill input, advance, or complete pipeline."""
    input_widget = self.query_one(f"#{self.id}-input", Input)

    if result.get("_fill_input") is not None:
      self._suppress_input_change = True
      input_widget.value = result["_fill_input"]
      input_widget.cursor_position = len(input_widget.value)

    if result.get("_close_autocomplete"):
      self.query_one(f"#{self.id}-autocomplete", Autocomplete).close()

    if result.get("complete"):
      self.post_message(self.EntryAdded(panel=self, result=result))
      self._reset_pipeline()
      return

    if result.get("_advance") is not False:
      self._stage_index += 1
      self._partial_state.update(
        {k: v for k, v in result.items() if not k.startswith("_")}
      )
      input_widget.value = ""
      self._update_placeholder()
      self._refresh_options("")
    elif result.get("_fill_input") is not None and not result.get("_close_autocomplete"):
      # Stayed on same stage with new input — refresh options (e.g. "table." → show columns)
      self._refresh_options(result["_fill_input"])

  def _reset_pipeline(self) -> None:
    """Reset to first stage with empty state."""
    input_widget = self.query_one(f"#{self.id}-input", Input)
    self._stage_index = 0
    self._partial_state = {}
    input_widget.value = ""
    self._update_placeholder()
    self._refresh_options("")

  def _update_placeholder(self) -> None:
    """Set the input placeholder from the current stage, or fall back to default."""
    input_widget = self.query_one(f"#{self.id}-input", Input)
    stage = self._current_stage
    if stage.placeholder is not None:
      input_widget.placeholder = stage.placeholder(self._partial_state)
    else:
      input_widget.placeholder = self._placeholder
  # }}}

  # Event handlers {{{
  def on_descendant_focus(self, event: events.DescendantFocus) -> None:
    """Open autocomplete when input gains focus."""
    if event.widget.id == f"{self.id}-input":
      input_widget = self.query_one(f"#{self.id}-input", Input)
      self._refresh_options(input_widget.value)

  def on_descendant_blur(self, event: events.DescendantBlur) -> None:
    """Close autocomplete when input loses focus."""
    if event.widget.id == f"{self.id}-input":
      self.query_one(f"#{self.id}-autocomplete", Autocomplete).close()

  def on_input_changed(self, event: Input.Changed) -> None:
    if event.input.id != f"{self.id}-input":
      return
    if self._suppress_input_change:
      self._suppress_input_change = False
      return
    self._refresh_options(event.value)

  def on_input_submitted(self, event: Input.Submitted) -> None:
    if event.input.id != f"{self.id}-input":
      return

    autocomplete = self.query_one(f"#{self.id}-autocomplete", Autocomplete)

    if autocomplete.is_open and autocomplete.highlighted is not None:
      event.stop()
      value = autocomplete.get_highlighted_value()
      if value is not None:
        result = self._current_stage.on_pick(
          self._partial_state, value, event.input.value
        )
        self._advance_or_complete(result)
    elif self._current_stage.allow_freetext:
      text = event.value.strip()
      if text:
        result = self._current_stage.on_pick(
          self._partial_state, text, text
        )
        self._advance_or_complete(result)

  def on_key(self, event: events.Key) -> None:
    """Intercept arrow keys and escape for autocomplete navigation."""
    input_widget = self.query_one(f"#{self.id}-input", Input)
    if not input_widget.has_focus:
      return

    autocomplete = self.query_one(f"#{self.id}-autocomplete", Autocomplete)
    if not autocomplete.is_open:
      return

    if event.key == "down":
      event.stop()
      event.prevent_default()
      autocomplete.move_highlight(1)
    elif event.key == "up":
      event.stop()
      event.prevent_default()
      autocomplete.move_highlight(-1)
    elif event.key == "escape":
      event.stop()
      event.prevent_default()
      autocomplete.close()
  # }}}

  # Content area {{{
  def set_content(self, lines: list[str]) -> None:
    """Replace the content area with the given lines.
    Called by the Screen after updating QueryBuilder state.
    """
    container = self.query_one(f"#{self.id}-content", ScrollableContainer)
    container.remove_children()
    if not lines:
      container.mount(Static(f"Awaiting {self._title.rstrip(':')} Input"))
    else:
      for line in lines:
        container.mount(Static(line))
  # }}}
# }}}
