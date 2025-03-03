import re

from telegram import Update
from telegram.ext import ContextTypes

from lotb.common.plugin_class import PluginBase


class Plugin(PluginBase):
  def __init__(self):
    super().__init__("socialfix", "fix shitty social links like twitter and instangram", require_auth=False)

  def initialize(self):
    self.initialize_plugin()
    self.pattern_actions = {}

    twitter_enabled, instagram_enabled, reddit_enabled = [
      # Support multiple ways of specifying true
      str(self.config.get(f"plugins.{self.name}.{platform}", True)).lower() in ["true", "1", "yes", True]
      for platform in ["twitter", "instagram", "reddit"]
    ]

    patterns = {
      "twitter": (twitter_enabled, r"^https://x\.com/(.+)", self.fix_twitter_link),
      "instagram": (instagram_enabled, r"^https://www\.instagram\.com/(.+)", self.fix_instagram_link),
      "reddit": (reddit_enabled, r"^https://(?:www\.|old\.)?reddit\.com/(.+)", self.fix_reddit_link),
    }

    self.pattern_actions.update(
      {
        pattern: self.create_pattern_handler(handler, pattern)
        for enabled, pattern, handler in patterns.values()
        if enabled
      }
    )

    self.log_info("social fix plugin initialized")
    self.log_info(f"Twitter enabled: {twitter_enabled}")
    self.log_info(f"Instagram enabled: {instagram_enabled}")
    self.log_info(f"Reddit enabled: {reddit_enabled}")

  def create_pattern_handler(self, handler, pattern):
    async def handler_wrapper(u, c):
      match = re.match(pattern, u.message.text)
      await handler(u, c, match)

    return handler_wrapper

  async def execute(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await self.intercept_patterns(update, context, self.pattern_actions):
      return

  async def fix_twitter_link(self, update: Update, context: ContextTypes.DEFAULT_TYPE, match: re.Match):
    if match:
      fixed_url = f"https://fxtwitter.com/{match.group(1)}"
      await self.reply_message(update, context, fixed_url)

  async def fix_instagram_link(self, update: Update, context: ContextTypes.DEFAULT_TYPE, match: re.Match):
    if match:
      fixed_url = f"https://www.ddinstagram.com/{match.group(1)}"
      await self.reply_message(update, context, fixed_url)

  async def fix_reddit_link(self, update: Update, context: ContextTypes.DEFAULT_TYPE, match: re.Match):
    if match:
      fixed_url = f"https://rxddit.com/{match.group(1)}"
      await self.reply_message(update, context, fixed_url)
