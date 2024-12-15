from datetime import datetime
from typing import Callable
from typing import Dict

from telegram import Update
from telegram.ext import ContextTypes

from lotb.common.plugin_class import PluginBase


class Plugin(PluginBase):
  def __init__(self):
    super().__init__("memo", "Save messages with /memo", require_auth=False)

  def initialize(self):
    self.initialize_plugin()
    plugin_config = self.config.get(f"plugins.{self.name}", {})

    self.categories = {
      "todo": {
        "file_path": plugin_config.get("todo"),
        "patterns": ["todo", "to-do", "TODO", "TO-DO"],
        "prefix": "\n\n- TODO ",
        "daily_file": True,
        "success_message": "Message saved to todo.",
        "reaction_patterns": [r"\btodo\b", r"\bto-do\b", r"\btask\b"],
      },
      "book": {
        "file_path": plugin_config.get("book"),
        "patterns": ["to-read", "toread", "TO-READ"],
        "prefix": "\n\n- ",
        "daily_file": False,
        "success_message": "Message saved to book.",
        "reaction_patterns": [r"\bto[- ]?read\b", r"\bbook\b"],
      },
      "series": {
        "file_path": plugin_config.get("series"),
        "patterns": ["to-watch-series", "towatch-series", "WATCH-SERIES"],
        "prefix": "\n\n- ",
        "daily_file": False,
        "success_message": "Message saved to series.",
        "reaction_patterns": [r"\bseries\b", r"\bshow\b"],
      },
      "film": {
        "file_path": plugin_config.get("film"),
        "patterns": ["to-watch-film", "towatch-film", "WATCH-FILM"],
        "prefix": "\n\n- ",
        "daily_file": False,
        "success_message": "Message saved to film.",
        "reaction_patterns": [r"\bfilm\b", r"\bmovie\b"],
      },
      "generic": {
        "file_path": plugin_config.get("generic"),
        "patterns": [],  # Default fallback
        "prefix": "\n\n- ",
        "daily_file": True,
        "success_message": "Message saved to generic.",
        "reaction_patterns": [],
      },
    }

    if not all(cat["file_path"] for cat in self.categories.values()):
      raise ValueError("All memo file paths must be specified in the configuration.")

    self.pattern_actions = self._build_pattern_actions()
    self.pattern_mapping = self._build_pattern_mapping()
    self.log_info(f"Memo plugin initialized with categories: {list(self.categories.keys())}")

  def _build_pattern_mapping(self) -> Dict[str, str]:
    pattern_mapping = {}
    for category, config in self.categories.items():
      for pattern in config["patterns"]:
        pattern_mapping[pattern.lower()] = category
    return pattern_mapping

  def _build_pattern_actions(self) -> Dict[str, Callable]:
    pattern_actions = {}
    for category, config in self.categories.items():
      if config["reaction_patterns"]:
        for pattern in config["reaction_patterns"]:
          pattern_actions[pattern] = lambda u, c, cat=category: self.react_to_message(u, c, cat)
    return pattern_actions

  def get_daily_file_path(self, base_path: str) -> str:
    date_str = datetime.now().strftime("%Y_%m_%d")
    return f"{base_path}/{date_str}.md"

  def append_to_file(self, file_path: str, message: str, prefix: str):
    with open(file_path, "a") as file:
      file.write(prefix + message + "\n")

  def get_category_from_message(self, message: str) -> str:
    """Determine the appropriate category based on the message content."""
    message_lower = message.lower().strip()

    for pattern, category in self.pattern_mapping.items():
      if message_lower.startswith(pattern):
        return category

    return "generic"

  def clean_message(self, message: str, category: str) -> str:
    """Remove category prefix from message."""
    message_lower = message.lower()
    for pattern in self.categories[category]["patterns"]:
      if message_lower.startswith(pattern.lower()):
        return message[len(pattern) :].strip()
    return message.strip()

  async def save_message(self, message: str, category: str, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Save a message to the appropriate category file."""
    cat_config = self.categories[category]

    file_path = (
      self.get_daily_file_path(cat_config["file_path"]) if cat_config["daily_file"] else cat_config["file_path"]
    )

    cleaned_message = self.clean_message(message, category)
    self.append_to_file(file_path, cleaned_message, cat_config["prefix"])

    await self.reply_quote_message(update, context, cat_config["success_message"])
    self.log_info(f"Saved message to {category}: {cleaned_message}")

  async def react_to_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE, category: str):
    if _message := update.message and update.message.text:
      await self.save_message(_message, category, update, context)
      return True
    return False

  async def execute(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.text:
      message_text = update.message.text.split(maxsplit=1)
    else:
      await self.reply_message(update, context, "No message text found.")
      return

    if update.message and update.message.reply_to_message and update.message.reply_to_message.text:
      quoted_message = update.message.reply_to_message.text
      if quoted_message:
        category = self.get_category_from_message(quoted_message)
        await self.save_message(str(quoted_message), category, update, context)
      else:
        await self.reply_message(update, context, "No quoted message found to save.")
        self.log_warning("No quoted message found to save.")
      return

    if len(message_text) > 1:
      message = message_text[1] if len(message_text) > 1 else None
      if message:
        category = self.get_category_from_message(message)
        if category != "generic":
          await self.save_message(message, category, update, context)
        else:
          await self.save_message(message, "generic", update, context)
      else:
        await self.reply_message(update, context, "No message text found.")
    else:
      await self.reply_message(update, context, "No quoted message found to save.")
