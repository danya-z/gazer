# sql_builder_screen.py

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.screen import Screen
from textual.widgets import Static, Input, Label, Header, Footer

class SQLBuilderScreen(Screen):
  """Screen for building SQL queries with SELECT, FILTER, and SCHEMA panels."""

  BINDINGS = [
    ("escape", "app.pop_screen", "Back"),
  ]

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
          yield Static("Table_Name", classes="table-name")
          yield Static("  ├─ Column_name; type; table_id")
          yield Static("  ├─ Column_name; type; link → column'")
          yield Static("  └─ ...")
          yield Static("")
          yield Static("Another_Table", classes="table-name")
          yield Static("  ├─ Column_name; type; table_id")
          yield Static("  ├─ Column_name; type; link → column'")
          yield Static("  └─ ...")
      # }}}

    yield Footer()

  def on_mount(self) -> None:
    """Called when screen is mounted."""
    self.query_one("#select-input", Input).focus()

# Add to main app to test
if __name__ == "__main__":
  from textual.app import App

  class TestApp(App):
    def on_mount(self) -> None:
      self.push_screen(SQLBuilderScreen())

  app = TestApp()
  app.run()
