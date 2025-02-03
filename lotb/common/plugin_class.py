import logging
import re
import sqlite3
from typing import Callable
from typing import Dict
from typing import List

from telegram import Update
from telegram.ext import ContextTypes
from telegram.ext import JobQueue


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

  def initialize_plugin(self):
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
      await update.message.reply_text(message, quote=True)

  def log_info(self, message: str):
    logging.info(f"[{self.name}] {message}")

  def log_warning(self, message: str):
    logging.warning(f"[{self.name}] {message}")

  def log_error(self, message: str):
    logging.error(f"[{self.name}] {message}")

  def set_job_queue(self, job_queue: JobQueue):
    pass

  def escape_markdown(self, text):
    special_chars = ["_", "*", "[", "]", "(", ")", "~", "`", ">", "#", "+", "-", "=", "|", "{", "}", ".", "!"]
    return "".join("\\" + char if char in special_chars else char for char in str(text))

  async def intercept_patterns(self, update: Update, context: ContextTypes.DEFAULT_TYPE, pattern_actions: dict):
    if update.message and update.message.text:
      message_text = update.message.text.lower()
      self.log_info(f"Checking message: {message_text}")
      for pattern, action in pattern_actions.items():
        self.log_info(f"Checking pattern: {pattern}")
        if re.search(pattern, message_text):
          self.log_info(f"Pattern matched: {pattern}")
          await action(update, context)
          self.log_info(f"Intercepted pattern '{pattern}' in message: {message_text}")
          return True
    self.log_info("No patterns matched.")
    return False

  async def execute(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    raise NotImplementedError("Implement this in your plugin")
