import random
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

from lotb.common.plugin_class import PluginBase


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

    formatted_quote = f"{quote_text}\n\n- {author}"

    self.execute_query(
      "INSERT INTO quotes (user_id, chat_id, quote) VALUES (?, ?, ?)", (user_id, chat_id, formatted_quote)
    )
    await self.reply_quote_message(update, context, "Quote added successfully")
    self.log_info(f"Quote added for user {user_id} in chat {chat_id}: {formatted_quote}")

  async def get_quote(self, update: Update, context: ContextTypes.DEFAULT_TYPE, term: str):
    if update.effective_chat:
      chat_id = update.effective_chat.id
    else:
      await self.reply_quote_message(update, context, "Chat information is missing")
      return

    if self.db_cursor:
      search_term = f"%{term}%"
      self.db_cursor.execute("SELECT quote FROM quotes WHERE quote LIKE ? AND chat_id = ?", (search_term, chat_id))
      quotes = self.db_cursor.fetchall()
    else:
      await self.reply_quote_message(update, context, "Database cursor is not available.")
      return

    if quotes:
      selected_quote = random.choice(quotes)[0]
      await self.reply_quote_message(update, context, selected_quote)
      self.log_info(f"Quote retrieved with term '{term}' in chat {chat_id}: {selected_quote}")
    else:
      await self.reply_quote_message(update, context, "No quotes found containing that term")
      self.log_info(f"No quotes found containing term '{term}' in chat {chat_id}")

  async def execute(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.text:
      parts = update.message.text.split(maxsplit=1)

      if len(parts) == 1:
        if update.message.reply_to_message and update.message.reply_to_message.text:
          quote_text = update.message.reply_to_message.text
          await self.add_quote(update, context, quote_text)
        else:
          await self.reply_quote_message(update, context, "Please reply to a message to add it as a quote")
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
