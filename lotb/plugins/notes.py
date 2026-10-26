from telegram import Update
from telegram.ext import ContextTypes

from lotb.common.plugin_class import PluginBase
from lotb.common.tools import plugin_tool
from lotb.common.tools import ToolResult


class Plugin(PluginBase):
  def __init__(self):
    super().__init__(
      "notes",
      "Manage your notes: /notes add <str>, /notes list, /notes delete <id>",
      True,
    )

  def initialize(self):
    self.initialize_plugin()
    self.create_table("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            note TEXT NOT NULL
        )
        """)
    self.log_info("Notes plugin initialized.")

  def get_tools(self):
    return [
      plugin_tool(
        "lotb_notes_add",
        "Save a note for the requesting user",
        {"text": {"type": "string", "minLength": 1}},
        self.add_action,
      ),
      plugin_tool("lotb_notes_list", "List the requesting user's notes", {}, self.list_action),
      plugin_tool(
        "lotb_notes_delete",
        "Delete one of the requesting user's notes",
        {"note_id": {"type": "integer", "minimum": 1}},
        self.delete_action,
      ),
    ]

  async def add_action(self, update, context, text: str) -> ToolResult:
    if not update.effective_user:
      return ToolResult(False, {}, "User information is missing.")
    self.execute_query("INSERT INTO notes (user_id, note) VALUES (?, ?)", (update.effective_user.id, text))
    return ToolResult(True, {"message": "Note added successfully."})

  async def list_action(self, update, context) -> ToolResult:
    if not update.effective_user:
      return ToolResult(False, {}, "User information is missing.")
    if self.db_cursor is None:
      return ToolResult(False, {}, "Database cursor is not available.")
    self.db_cursor.execute("SELECT id, note FROM notes WHERE user_id = ?", (update.effective_user.id,))
    notes = self.db_cursor.fetchall()
    message = "Your notes:\n" + "\n".join(f"{row[0]}: {row[1]}" for row in notes) if notes else "You have no notes."
    return ToolResult(True, {"notes": [{"id": row[0], "text": row[1]} for row in notes], "message": message})

  async def delete_action(self, update, context, note_id: int) -> ToolResult:
    if not update.effective_user:
      return ToolResult(False, {}, "User information is missing.")
    self.execute_query("DELETE FROM notes WHERE id = ? AND user_id = ?", (note_id, update.effective_user.id))
    if self.db_cursor and self.db_cursor.rowcount > 0:
      return ToolResult(True, {"message": "Note deleted successfully."})
    return ToolResult(False, {}, "Note not found or you don't have permission to delete it.")

  async def add_note(self, update, context, note: str):
    result = await self.add_action(update, context, note)
    await self.reply_quote_message(
      update, context, result.data["message"] if result.ok else result.error or "Action failed"
    )

  async def view_notes(self, update, context):
    result = await self.list_action(update, context)
    await self.reply_quote_message(
      update, context, result.data["message"] if result.ok else result.error or "Action failed"
    )

  async def delete_note(self, update, context, note_id: int):
    result = await self.delete_action(update, context, note_id)
    await self.reply_quote_message(
      update, context, result.data["message"] if result.ok else result.error or "Action failed"
    )

  async def execute(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.text:
      command_args = update.message.text.split(maxsplit=2)
    else:
      await self.reply_quote_message(update, context, "No command text found.")
      return
    if len(command_args) > 1:
      main_command, sub_command = command_args[0], command_args[1]
      args = command_args[2] if len(command_args) > 2 else ""
    else:
      main_command, sub_command, args = command_args[0], "", ""

    self.log_info(f"Received command: {main_command}, sub_command: {sub_command}, args: {args}")

    if main_command.startswith(("/", "!")):
      main_command = main_command[1:].split("@", 1)[0]

    if main_command == "notes":
      if sub_command == "add" and args:
        await self.add_note(update, context, args)
      elif sub_command == "list":
        await self.view_notes(update, context)
      elif sub_command == "delete" and args.isdigit():
        await self.delete_note(update, context, int(args))
      else:
        await self.reply_quote_message(update, context, "Invalid notes subcommand or missing arguments.")
    else:
      await self.reply_quote_message(update, context, "Invalid notes command.")
