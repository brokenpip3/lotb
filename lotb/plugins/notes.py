from telegram import Update
from telegram.ext import ContextTypes

from lotb.common.plugin_class import PluginBase


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

  async def add_note(self, update: Update, context: ContextTypes.DEFAULT_TYPE, note: str):
    if update.effective_user:
      user_id = update.effective_user.id
    else:
      await self.reply_quote_message(update, context, "User information is missing.")
      return
    self.execute_query("INSERT INTO notes (user_id, note) VALUES (?, ?)", (user_id, note))
    await self.reply_quote_message(update, context, "Note added successfully.")
    self.log_info(f"Note added for user {user_id}: {note}")

  async def view_notes(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user:
      user_id = update.effective_user.id
    else:
      await self.reply_quote_message(update, context, "User information is missing.")
      return

    if self.db_cursor:
      self.db_cursor.execute("SELECT id, note FROM notes WHERE user_id = ?", (user_id,))
      notes = self.db_cursor.fetchall()
    else:
      await self.reply_quote_message(update, context, "Database cursor is not available.")
      return
    if notes:
      response = "Your notes:\n" + "\n".join([f"{note[0]}: {note[1]}" for note in notes])
    else:
      response = "You have no notes."
    await self.reply_quote_message(update, context, response)
    self.log_info(f"Notes viewed for user {user_id}")

  async def delete_note(self, update: Update, context: ContextTypes.DEFAULT_TYPE, note_id: int):
    if update.effective_user:
      user_id = update.effective_user.id
    else:
      await self.reply_quote_message(update, context, "User information is missing.")
      return

    self.execute_query(
      "DELETE FROM notes WHERE id = ? AND user_id = ?",
      (note_id, user_id),
    )
    if self.db_cursor and self.db_cursor.rowcount > 0:
      await self.reply_quote_message(update, context, "Note deleted successfully.")
      self.log_info(f"Note with ID {note_id} deleted")
    else:
      await self.reply_quote_message(
        update,
        context,
        "Note not found or you don't have permission to delete it.",
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

    if main_command.startswith("/"):
      main_command = main_command[1:]

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
