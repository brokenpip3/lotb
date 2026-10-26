from telegram import Update
from telegram.ext import ContextTypes

from lotb.common.plugin_class import PluginBase
from lotb.common.tools import plugin_tool
from lotb.common.tools import ToolResult


class Plugin(PluginBase):
  def __init__(self):
    super().__init__("welcome", "Send a welcome message with /welcome <message>", False)

  def initialize(self):
    self.initialize_plugin()
    self.log_info("Welcome plugin initialized.")

  async def execute(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id if update.effective_user else None
    message = update.message.text.split(maxsplit=1) if update.message and update.message.text else []
    await self.send_action(update, context, message[1] if len(message) > 1 else "")
    self.log_info(f"just welcomed someone {user_id}")

  def get_tools(self):
    return [
      plugin_tool("lotb_welcome_send", "Send a welcome greeting", {"message": {"type": "string"}}, self.send_action)
    ]

  async def send_action(self, update, context, message: str) -> ToolResult:
    response = f"Welcome: {message}" if message else "Welcome!"
    await self.reply_quote_message(update, context, response)
    return ToolResult(True, {"message": response}, sent_message=True)
