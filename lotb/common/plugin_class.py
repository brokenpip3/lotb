import logging
import re
import sqlite3
from contextlib import contextmanager
from typing import Callable
from typing import Dict
from typing import List

import httpx
import litellm
from telegram import Update
from telegram.ext import ContextTypes
from telegram.ext import JobQueue


class SecurityValidator:
  def __init__(self):
    self.max_tool_arg_size = 10000
    self.blocked_tool_patterns = [
      re.compile(pattern, re.IGNORECASE)
      for pattern in [r".*exec.*", r".*eval.*", r".*shell.*", r".*cmd.*", r".*rm\s+.*", r".*delete.*", r".*drop.*"]
    ]
    self.suspicious_content_patterns = [
      re.compile(pattern, re.IGNORECASE)
      for pattern in [
        r"<script[\s\S]*?>.*?</script>",
        r"javascript:",
        r"on\w+=",
        r"data:text/html",
        r"data:text/javascript",
        r"data:text/css",
      ]
    ]

  def validate_user_input(self, text: str) -> tuple[bool, str]:
    for pattern in self.suspicious_content_patterns:
      if pattern.search(text):
        return False, f"Input contains suspicious content matching pattern: {pattern.pattern}"
    return True, ""

  def llm_validate_tool_name(self, tool_name: str) -> tuple[bool, str]:
    for pattern in self.blocked_tool_patterns:
      if pattern.match(tool_name):
        return False, f"tool '{tool_name}' matches blocked pattern"
    return True, ""


class PluginBase:
  def __init__(self, name: str, description: str, require_auth: bool = False):
    self.name = name
    self.description = description
    self.require_auth = require_auth
    self.config = None
    self.connection = None
    self.db_cursor = None
    self.admin_ids: List[int] = []
    self.pattern_actions: Dict[str, Callable] = {}
    self.auth_group_ids: List[int] = []
    self.auth_group_enabled = False
    self.security_validator = SecurityValidator()

  def initialize_plugin(self):
    if self.config is None:
      self.log_error("Configuration not loaded")
      return

    plugin_config = self.config.get(f"plugins.{self.name}", {})
    if not plugin_config.get("enabled", True):
      raise ValueError(f"{self.name.capitalize()} plugin not loaded: not enabled in config")
    else:
      self.log_info(f"{self.name.capitalize()} plugin is enabled.")

    if plugin_config.get("debug"):
      self.log_info(f"Configuration for {self.name}: {plugin_config}")
    self.pattern_actions = {}

  def set_config(self, config):
    self.config = config
    plugin_config = self.config.get(f"plugins.{self.name}", {})
    if plugin_config.get("debug"):
      self.log_info(f"Configuration for {self.name}: {plugin_config}")

    database_name = self.config.get("core.database", ":memory:")
    self.connection = sqlite3.connect(database_name)
    self.db_cursor = self.connection.cursor()
    self.log_info(f"Database connection established for {self.name}")

    if self.require_auth:
      self.admin_ids = [int(admin_id) for admin_id in self.config.get("core.admins", [])]

    self.auth_group_ids = [int(group_id) for group_id in plugin_config.get("auth_groups_ids", [])]
    self.auth_group_enabled = plugin_config.get("auth_group_enabled", False)

  def is_authorized(self, update: Update) -> bool:
    if update.effective_user:
      user_id = update.effective_user.id
      if self.require_auth and user_id not in self.admin_ids:
        return False
    return True

  def group_is_authorized(self, update: Update) -> bool:
    if update.effective_chat:
      chat_id = update.effective_chat.id
      if self.auth_group_enabled and chat_id not in self.auth_group_ids:
        return False
    return True

  def set_plugins(self, plugins):
    self.plugins = plugins

  def create_table(self, query: str):
    if self.db_cursor:
      self.db_cursor.execute(query)
      self.connection.commit()

  def execute_query(self, query: str, params: tuple = ()):
    if self.db_cursor:
      self.db_cursor.execute(query, params)
      self.connection.commit()

  async def reply_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE, message: str):
    if update.message:
      await update.message.reply_text(message)

  async def reply_quote_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE, message: str):
    if update.message:
      await update.message.reply_text(message, do_quote=True)

  def log_info(self, message: str):
    logging.info(f"[{self.name}] {message}")

  def log_warning(self, message: str):
    logging.warning(f"[{self.name}] {message}")

  def log_error(self, message: str):
    logging.error(f"[{self.name}] {message}")

  def log_debug(self, message: str):
    logging.debug(f"[{self.name}] {message}")

  def set_job_queue(self, job_queue: JobQueue):
    pass

  def escape_markdown(self, text):
    special_chars = ["_", "*", "[", "]", "(", ")", "~", "`", ">", "#", "+", "-", "=", "|", "{", "}", ".", "!"]
    return "".join("\\" + char if char in special_chars else char for char in str(text))

  async def intercept_patterns(self, update: Update, context: ContextTypes.DEFAULT_TYPE, pattern_actions: dict):
    if update.message and update.message.text:
      message_text = update.message.text.lower()
      self.log_debug(f"Checking message: {message_text}")
      for pattern, action in pattern_actions.items():
        self.log_debug(f"Checking pattern: {pattern}")
        if re.search(pattern, message_text):
          self.log_debug(f"Pattern matched: {pattern}")
          await action(update, context)
          self.log_debug(f"Intercepted pattern '{pattern}' in message: {message_text}")
          return True
    self.log_debug("No patterns matched.")
    return False

  @contextmanager
  def _wrap_llm_logging(self, model_name: str):
    """thanks openai for this trick"""
    original_level = logging.getLogger("LiteLLM").level
    try:
      logging.getLogger("LiteLLM").setLevel(logging.WARNING)
      self.log_info(f"Starting llm completion with model: {model_name}")
      yield
    finally:
      logging.getLogger("LiteLLM").setLevel(original_level)
      self.log_info(f"Completed llm completion with model: {model_name}")

  async def llm_completion(
    self, messages: list, model: str | None = None, api_key: str | None = None, **kwargs
  ) -> litellm.ModelResponse:
    try:
      if not model:
        model = "gpt-4.1-nano"
        self.log_warning("no model specified, using default openai/gpt-4.1-nano")

      params = {
        "model": model,
        "api_key": api_key,
        "temperature": 0.7,
        **kwargs,
      }

      filtered_params = {"model": model, "messages": messages}
      for k, v in params.items():
        if k != "model" and v is not None:
          filtered_params[k] = v

      with self._wrap_llm_logging(model):
        response = await litellm.acompletion(**filtered_params)
      return response
    except httpx.HTTPError as e:
      self.log_error(f"llm completion failed: {str(e)}")
      raise

  async def execute(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    raise NotImplementedError("Implement this in your plugin")
