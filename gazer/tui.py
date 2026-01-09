from textual.app import App
from textual.widgets import Header, Footer, Static, Button, Input
from textual.binding import Binding

from db_connector import DBConnector
from schema_inspector import SchemaInspector
from query_builder import QueryBuilder

class GazerApp(App):

  TITLE = "Gazer"
  SUB_TITLE = "Database Query Builder"
  BINDINGS = [
    Binding("escape", "quit", "Quit"),
    Binding("c", "connect", "Connect")
  ]

  def on_mount(self):
    self.theme = "monokai"

  def compose(self):
    yield Header()
    yield Static("Host:")
    yield Input(
      value="ldvdbapgdb02a.itap.purdue.edu", 
      id="host"
    )
    yield Static("Port:")
    yield Input(value="5433", id="port")
    yield Static("Database:")
    yield Input(value="bdidata", id="database")
    
    yield Static("Username:")
    yield Input(placeholder="Enter username", id="username")
    yield Static("Password:")
    yield Input(
      placeholder="Enter password",
      password=True,
      id="password"
    )
    
    yield Static("")
    yield Button("Connect", id="connect", variant="primary")
    yield Static("", id="status")
    yield Footer()
  
  def on_button_pressed(self, event: Button.Pressed):
    if event.button.id == "connect":
      self.attempt_connection()

  def on_input_submitted(self, event: Input.Submitted):
    inputs = ["#host", "#port", "#database", "#username", "#password"]
    current_id = event.input.id
    current_index = inputs.index(f"#{current_id}")
    if current_index < len(inputs) - 1:
      next_input = self.query_one(inputs[current_index + 1], Input)
      next_input.focus()

  def attempt_connection(self):
    status = self.query_one("#status", Static)
    status.update("Connecting...")
    
    host = self.query_one("#host", Input).value
    port = self.query_one("#port", Input).value
    database = self.query_one("#database", Input).value
    username = self.query_one("#username", Input).value
    password = self.query_one("#password", Input).value
    
    if not username:
      status.update("Username is required")
      return
    if not password:
      status.update("Password is required")
      return

    try:
      db = DBConnector(host, port, database, username, password)
      db.connect()
      self.db = db

      self.schema = SchemaInspector(db)
      self.query_builder = QueryBuilder()
      status.update("✓ Connected successfully!")
      
    except Exception as e:
      if db is not None:
        try:
          db.close()
        except:
          pass

      raw_error_msg = str(e)
      code_error = raw_error_msg.lower()

      if "timeout" in code_error or "timed out" in code_error:
        human_readible_error_msg = "Connection timeout - Are you on the VPN?"
      elif "authentication failed" in code_error:
        human_readible_error_msg = "Authentication failed - Check password"
      elif "no pg_hba.conf entry for host" in code_error:
        human_readible_error_msg = "Authentication failed - Check username"
      elif "could not translate host name" in code_error:
        human_readible_error_msg = "Cannot reach host - Check VPN connection"
      else:
        human_readible_error_msg = "Gazer does not recognize this error."

      status.update(f"{human_readible_error_msg}\nDetails: {raw_error_msg}")
  
  def cleanup(self):
    if hasattr(self, 'db') and self.db is not None:
      try:
        self.db.close()
      except Exception as e:
        pass

  def action_quit(self):
    self.cleanup()
    self.exit()
  
  def action_connect(self):
    self.attempt_connection()

def main():
  app = GazerApp()
  app.run()

if __name__ == '__main__':
  main()
