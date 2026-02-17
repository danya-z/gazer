from __future__ import annotations

from enum import Enum, auto

from textual.widgets import Input, OptionList


# Constants {{{
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

  def __init__(self, mode: str = "select", **kwargs) -> None:
    super().__init__(**kwargs)
    self.mode = mode
    self.stage: DropdownStage = DropdownStage.TABLE
    self._suppress: bool = False

    # Schema data (set via set_schema)
    self._table_columns: dict[str, list[str]] = {}
    self._column_lookup: dict[str, list[str]] = {}
    self._column_types: dict[str, str] = {}   # "table.column" -> udt_name
    self._enum_values: dict[str, list[str]] = {}  # udt_name -> [values]

    # Filter construction state (filter mode only)
    self._picked_column: str = ""       # "table.column"
    self._picked_type: str = ""         # udt_name
    self._picked_operator: str = ""

  def set_schema(self, table_columns: dict[str, list[str]],
                 column_lookup: dict[str, list[str]],
                 column_types: dict[str, str] | None = None,
                 enum_values: dict[str, list[str]] | None = None) -> None:
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
