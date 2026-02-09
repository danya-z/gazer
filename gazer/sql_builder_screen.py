# sql_builder_screen.py

from textual.app import ComposeResult
from textual import work 
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.screen import Screen
from textual.widgets import Static, Input, Label, Header, Footer

class SQLBuilderScreen(Screen):
  """Screen for building SQL queries with SELECT, FILTER, and SCHEMA panels."""

  BINDINGS = [
    ("escape", "app.pop_screen", "Back"),
  ]

  def __init__(self, schema_inspector):
    """Initialize, with a SchemaInspector instance."""
    super().__init__()
    self.inspector = schema_inspector
    self.tables = []
    self.current_table_columns = {}

  # CSS {{{
  CSS_PATH = "gazer.tcss"
  CSS = """
  SQLBuilderScreen {
      layout: vertical;
  }

  #main-container {
      layout: horizontal;
      width: 1fr;
  }

  #builder-panel {
      width: 1fr;
      border: solid green;
  }

  #schema-panel {
      width: 1fr;
      border: solid blue;
  }

  /* Vertical split within builder: SELECT and FILTER */
  #select-section {
      height: 1fr;
      border: solid yellow;
  }

  #filter-section {
      height: 2fr;
      border: solid yellow;
  }

  /* Section titles */
  .section-title {
      background: $primary;
      color: $text;
      padding: 0 1;
      text-style: bold;
  }

  /* Input boxes for typing */
  .inline-input {
      margin: 0 1;
      border: solid $accent;
  }

  /* Scrollable content areas */
  .content-area {
      height: 1fr;
      border: solid $panel;
      margin: 0 1 1 1;
  }

  /* Schema content area */
  #schema-content {
      height: 1fr;
      border: solid $panel;
      margin: 0 1 1 1;
  }
  """ 
  # }}}

  def compose(self) -> ComposeResult:
    """Create the layout structure."""
    yield Header()
    yield Static("Query Builder", id="title")

    with Container(id="main-container"):
      # Left side: Query builder (SELECT + FILTER) {{{
      with Vertical(id="builder-panel"):

        # Upper left: SELECT Screen
        with Container(id="select-section"):
          yield Label("SELECT:", classes="section-title")
          yield Input(
            placeholder="type selection here",
            classes="inline-input",
            id="select-input"
          )
          with ScrollableContainer(classes="content-area"):
            yield Static("-- Imported from .../Table.xlsx")
            yield Static("- Table_name.Column_name")
            yield Static("- Table_name.Column_name")
            yield Static("- Table_name.Column_name")

        # Lower left: FILTER Screen
        with Container(id="filter-section"):
          yield Label("FILTER:", classes="section-title")
          yield Input(
            placeholder="type filters here",
            classes="inline-input",
            id="filter-input"
          )
          with ScrollableContainer(classes="content-area"):
            yield Static("AND┌─ OR ┌─── Imported from .../Table.xlsx")
            yield Static("   │     ├─ Table_name.Column_name > 30")
            yield Static("   │     └─ Table_name.Column_name NOT NULL")
            yield Static("   ├─ AND┌─ Table_name.Column_name = STUFF")
            yield Static("   │     ├─ ...")
            yield Static("   └─    └─ ...")
      # }}}
      # Right side: Schema browser {{{
      with Container(id="schema-panel"):
        yield Label("SCHEMA:", classes="section-title")
        with ScrollableContainer(id="schema-content"):
          yield Static("Fetching Schema...")
      # }}}

    yield Footer()

  def on_mount(self) -> None:
    """Called when screen is mounted."""
    self.query_one("#select-input", Input).focus()
    self.load_schema()

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
      self.app.call_from_thread(self.display_schema_error, str(e))

  def display_schema(self, schema_data: list) -> None:
    """Display the schema in the schema panel."""
    container = self.query_one("#schema-content", ScrollableContainer)
    container.remove_children()

    for item in schema_data:
      table_name = item['table']
      columns = item['columns']

      container.mount(Static(table_name, classes="table-name"))
      for col in columns: 
        col_str = f"  ├─ {col['name']}; {col['udt_name']}"
        if col['is_primary_key']:
          col_str += "; PK"
        if col['is_foreign_key']:
          col_str += f"; FK→{col['fk_table']}.{col['fk_column']}"

        container.mount(Static(col_str))
      container.mount(Static(""))

  def display_schema_error(self, error_msg: str) -> None:
    """Display an error message in the schema panel."""
    container = self.query_one("#schema-content", ScrollableContainer)
    container.remove_children()
    container.mount(Static(f"Error loading schema: {error_msg}", classes="user-error"))
