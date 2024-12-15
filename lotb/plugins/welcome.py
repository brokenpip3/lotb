from telegram import Update
from telegram.ext import ContextTypes

from lotb.common.plugin_class import PluginBase


class Plugin(PluginBase):
  def __init__(self):
    super().__init__("welcome", "Send a welcome message with /welcome <message>", False)

  def initialize(self):
    self.initialize_plugin()
    self.log_info("Welcome plugin initialized.")

  async def execute(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id if update.effective_user else None
    message = update.message.text.split(maxsplit=1) if update.message and update.message.text else []
    if len(message) > 1:
      response = f"Welcome: {message[1]}"
    else:
      response = "Welcome!"
    await self.reply_quote_message(update, context, response)
    self.log_info(f"just welcomed someone {user_id}")
