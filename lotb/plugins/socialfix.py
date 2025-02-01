import re

from telegram import Update
from telegram.ext import ContextTypes

from lotb.common.plugin_class import PluginBase


class Plugin(PluginBase):
  def __init__(self):
    super().__init__("socialfix", "fix shitty social links like twitter and instangram", require_auth=False)

  def initialize(self):
    self.initialize_plugin()
    self.pattern_actions = {
      r"^https://x\.com/(.+)": self.create_pattern_handler(self.fix_twitter_link, r"^https://x\.com/(.+)"),
      r"^https://www\.instagram\.com/(.+)": self.create_pattern_handler(
        self.fix_instagram_link, r"^https://www\.instagram\.com/(.+)"
      ),
    }
    self.log_info("social fix plugin initialized")

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
