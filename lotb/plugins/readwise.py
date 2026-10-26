import httpx
from telegram import Update
from telegram.ext import ContextTypes

from lotb.common.plugin_class import PluginBase
from lotb.common.tools import plugin_tool
from lotb.common.tools import ToolResult


class Plugin(PluginBase):
  def __init__(self):
    super().__init__("readwise", "save to Readwise: /readwise <url>", True)

  def initialize(self):
    plugin_config = self.config.get(f"plugins.{self.name}", {})
    self.readwise_token = plugin_config.get("token")
    if not self.readwise_token:
      raise ValueError("Readwise token not found in configuration.")
    if not self.check_token_validity():
      raise ValueError("Readwise token is not valid.")
    self.log_info("Readwise plugin initialized.")

  def check_token_validity(self) -> bool:
    headers = {"Authorization": f"Token {self.readwise_token}"}
    with httpx.Client() as client:
      response = client.get("https://readwise.io/api/v2/auth/", headers=headers)
    return response.status_code == 204

  def get_tools(self):
    return [
      plugin_tool(
        "lotb_readwise_save",
        "Save an HTTP(S) URL to Readwise",
        {"url": {"type": "string", "pattern": "^https?://[^\\s]+$"}},
        self.save_action,
      )
    ]

  async def save_action(self, update, context, url: str) -> ToolResult:
    headers = {"Authorization": f"Token {self.readwise_token}"}
    async with httpx.AsyncClient() as client:
      response = await client.post("https://readwise.io/api/v3/save/", headers=headers, json={"url": url})
    if response.status_code == 201:
      return ToolResult(True, {"message": "URL saved to Readwise successfully.", "status": "saved"})
    if response.status_code == 200:
      return ToolResult(True, {"message": "URL already exists in your Readwise archive.", "status": "already_present"})
    self.log_error(f"Failed to save URL to Readwise. Status code: {response.status_code}, Response: {response.text}")
    return ToolResult(False, {}, "Failed to save URL to Readwise.")

  async def save_to_readwise(self, update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
    result = await self.save_action(update, context, url)
    await self.reply_quote_message(
      update, context, result.data["message"] if result.ok else result.error or "Action failed"
    )

  def extract_url_from_message(self, message_text: str) -> str:
    words = message_text.split()
    for word in words:
      if word.startswith("http://") or word.startswith("https://"):
        return word
    return ""

  async def execute(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_parts = update.message.text.split(maxsplit=1) if update.message and update.message.text else []
    if len(message_parts) > 1:
      url = message_parts[1]
      await self.save_to_readwise(update, context, url)
    elif update.message and update.message.reply_to_message and update.message.reply_to_message.text:
      quoted_url = self.extract_url_from_message(update.message.reply_to_message.text)
      if quoted_url:
        await self.save_to_readwise(update, context, quoted_url)
      else:
        await self.reply_quote_message(update, context, "Quoted message does not contain a valid URL.")
    else:
      await self.reply_quote_message(update, context, "Missing URL argument for Readwise command.")
