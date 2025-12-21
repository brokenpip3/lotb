import re
from typing import Callable
from typing import Dict
from typing import TYPE_CHECKING

from telegram import Update
from telegram.ext import ContextTypes

from .history import ConversationHistory
from .prompts import SIMPLE_LLM_ROLE

if TYPE_CHECKING:
  from lotb.common.plugin_class import PluginBase
  from .config import LLMConfig


class SimpleLLMHandler:
  def __init__(self, plugin: "PluginBase", config: "LLMConfig"):
    self.plugin = plugin
    self.config = config
    self.history = ConversationHistory(plugin, config.max_history)
    self.pattern_actions: Dict[str, Callable] = {}

  def initialize(self):
    self.history.create_table()

    if self.config.friendly_name:
      trigger_pattern = rf"(?i)\b(?:hey\s+)?{re.escape(self.config.friendly_name)}\b[\s,:!?]*"
      self.pattern_actions = {trigger_pattern: self.handle_trigger}
      self.plugin.log_info(f"LLM trigger enabled with name: {self.config.friendly_name}")

  async def handle_trigger(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
      return

    if self.config.friendly_name:
      trigger_pattern = rf"(?i)\b(?:hey\s+)?{re.escape(self.config.friendly_name)}\b[\s,:!?]*"
      query = re.sub(trigger_pattern, "", update.message.text, count=1).strip()

      if not query:
        await self.plugin.reply_message(update, context, "yes? 🦕")
        return

    await self.process_query(update, context, query)

  async def process_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
    if not update.effective_user or not update.effective_chat:
      await self.plugin.reply_message(update, context, "User or chat information missing")
      return

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    try:
      quoted_text = ""
      if update.message and update.message.reply_to_message and update.message.reply_to_message.text:
        quoted_text = f"\n\nQuoted message:\n{update.message.reply_to_message.text}"

      history = self.history.get_conversation_history(user_id, chat_id)
      messages = [
        {"role": "system", "content": SIMPLE_LLM_ROLE},
        *history,
        {"role": "user", "content": f"{query}{quoted_text}"},
      ]

      await self.plugin.send_typing_action(update, context)
      response = await self.plugin.llm_completion(
        messages=messages,
        model=self.config.model,
        api_key=self.config.apikey,
      )

      if response.choices and hasattr(response.choices[0], "message") and response.choices[0].message:
        response_content = response.choices[0].message.content or ""
        self.history.save_message(user_id, chat_id, "user", query)
        self.history.save_message(user_id, chat_id, "assistant", response_content)
        await self.plugin.reply_message(update, context, response_content)
      else:
        await self.plugin.reply_message(update, context, "LLM error: Invalid response format")

    except Exception as e:
      await self.plugin.reply_message(update, context, f"LLM error: {str(e)}")
      self.plugin.log_error(f"LLM query failed: {str(e)}")

  async def execute(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await self.plugin.intercept_patterns(update, context, self.pattern_actions):
      return

    if not update or not update.effective_chat:
      if update and update.effective_chat:
        await update.effective_chat.send_message("Message is unavailable")
      return

    if not update.message or not update.message.text:
      if update.effective_chat:
        await update.effective_chat.send_message("Message is unavailable")
      return

    query = update.message.text.replace("/llm", "", 1).strip()

    if not query:
      await self.plugin.reply_message(update, context, "Please provide a query")
      return

    await self.process_query(update, context, query)
