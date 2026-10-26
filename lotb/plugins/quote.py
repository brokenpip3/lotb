import random
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

from lotb.common.plugin_class import PluginBase
from lotb.common.tools import plugin_tool
from lotb.common.tools import ToolResult


class Plugin(PluginBase):
  def __init__(self):
    super().__init__(
      "quote",
      "/quote to add a quote by quoting to a message, /quote <term> to get a random quote",
      False,
    )

  def initialize(self):
    self.initialize_plugin()
    self.create_table("""
            CREATE TABLE IF NOT EXISTS quotes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                quote TEXT NOT NULL
            )
        """)
    self.execute_query("CREATE INDEX IF NOT EXISTS idx_quotes_chat_id ON quotes (chat_id, quote)")
    self.log_info("Quote plugin initialized.")

  async def add_quote(self, update: Update, context: ContextTypes.DEFAULT_TYPE, quote_text: str) -> None:
    user_id: Optional[int] = update.effective_user.id if update.effective_user else None
    chat_id: Optional[int] = update.effective_chat.id if update.effective_chat else None

    if not update.message:
      return
    if user_id is None:
      await self.reply_quote_message(update, context, "User information is missing.")
      return
    if chat_id is None:
      await self.reply_quote_message(update, context, "Chat information is missing.")
      return

    author: str = (
      update.message.reply_to_message.from_user.full_name
      if update.message.reply_to_message and update.message.reply_to_message.from_user
      else "Unknown"
    )

    result = await self.store_quote(update, quote_text, author)
    await self.reply_quote_message(update, context, result.data["message"])

  async def store_quote(self, update, quote_text: str, author: str) -> ToolResult:
    formatted_quote = f"{quote_text}\n\n- {author}"
    self.execute_query(
      "INSERT INTO quotes (user_id, chat_id, quote) VALUES (?, ?, ?)",
      (update.effective_user.id, update.effective_chat.id, formatted_quote),
    )
    return ToolResult(True, {"message": "Quote added successfully", "quote": formatted_quote})

  def get_tools(self):
    return [
      plugin_tool("lotb_quote_add", "Save the actual replied-to text as a quote with its author", {}, self.add_action),
      plugin_tool(
        "lotb_quote_find",
        "Find a random quote containing a term in this chat",
        {"term": {"type": "string", "minLength": 1}},
        self.find_action,
      ),
      plugin_tool("lotb_quote_random", "Get a random quote from this chat", {}, self.random_action),
    ]

  async def add_action(self, update, context) -> ToolResult:
    reply = update.message.reply_to_message if update.message else None
    if not reply or not reply.text:
      return ToolResult(False, {}, "Reply to a text message to save a quote")
    author = reply.from_user.full_name if reply.from_user else "Unknown"
    return await self.store_quote(update, reply.text, author)

  def select_quote(self, chat_id: int, term: str | None = None) -> ToolResult:
    if self.db_cursor is None:
      return ToolResult(False, {}, "Database cursor is not available.")
    if term is None:
      self.db_cursor.execute("SELECT quote FROM quotes WHERE chat_id = ?", (chat_id,))
    else:
      self.db_cursor.execute("SELECT quote FROM quotes WHERE quote LIKE ? AND chat_id = ?", (f"%{term}%", chat_id))
    quotes = self.db_cursor.fetchall()
    if not quotes:
      return ToolResult(False, {}, "No quotes available" if term is None else "No quotes found containing that term")
    return ToolResult(True, {"quote": random.choice(quotes)[0]})

  async def find_action(self, update, context, term: str) -> ToolResult:
    return self.select_quote(update.effective_chat.id, term)

  async def random_action(self, update, context) -> ToolResult:
    return self.select_quote(update.effective_chat.id)

  async def get_quote(self, update: Update, context: ContextTypes.DEFAULT_TYPE, term: str):
    if update.effective_chat:
      chat_id = update.effective_chat.id
    else:
      await self.reply_quote_message(update, context, "Chat information is missing")
      return

    result = self.select_quote(chat_id, term)
    await self.reply_quote_message(
      update, context, result.data["quote"] if result.ok else result.error or "Action failed"
    )

  async def get_random_quote(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat:
      chat_id = update.effective_chat.id
    else:
      await self.reply_quote_message(update, context, "Chat information is missing")
      return

    result = self.select_quote(chat_id)
    await self.reply_quote_message(
      update, context, result.data["quote"] if result.ok else result.error or "Action failed"
    )

  async def execute(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.text:
      parts = update.message.text.split(maxsplit=1)

      if len(parts) == 1:
        if update.message.reply_to_message and update.message.reply_to_message.text:
          quote_text = update.message.reply_to_message.text
          await self.add_quote(update, context, quote_text)
        else:
          await self.get_random_quote(update, context)
      elif len(parts) == 2:
        term = parts[1].strip()
        if term:
          await self.get_quote(update, context, term)
        else:
          await self.reply_quote_message(update, context, "Please provide a term to search for quotes")
      else:
        await self.reply_quote_message(update, context, "Invalid command format")
    else:
      await self.reply_quote_message(update, context, "No command text found")
