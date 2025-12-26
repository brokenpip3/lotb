from telegram import Update
from telegram.ext import ContextTypes

from lotb.common.plugin_class import PluginBase
from lotb.plugins._llm.assistant import AssistantHandler
from lotb.plugins._llm.config import LLMConfig
from lotb.plugins._llm.simple import SimpleLLMHandler


class Plugin(PluginBase):
  def __init__(self):
    super().__init__(
      name="llm",
      description="Chat llm assistant, ask anything with /llm <query>, supports simple and assistant mode",
      require_auth=False,
    )
    self.handler = None
    self.config_handler = None

  def initialize(self):
    self.initialize_plugin()

    if not hasattr(self, "config") or self.config is None:
      self.log_error("Configuration not loaded")
      return

    self.config_handler = LLMConfig(self.config)

    warnings = self.config_handler.validate()
    for warning in warnings:
      self.log_warning(warning)

    if self.config_handler.assistant_mode:
      self.handler = AssistantHandler(self, self.config_handler)
      self.log_info("LLM plugin running in assistant mode (MCP enabled)")
    else:
      self.handler = SimpleLLMHandler(self, self.config_handler)
      self.log_info("LLM plugin running in simple mode")

    self.handler.initialize()
    self.log_info(self.config_handler.get_info())

  async def execute(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    if self.handler:
      await self.handler.execute(update, context)
    else:
      self.log_error("Handler not initialized")
      if update.effective_chat:
        await update.effective_chat.send_message("Plugin not properly initialized")
