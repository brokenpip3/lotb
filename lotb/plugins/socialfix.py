import re

from telegram import Update
from telegram.ext import ContextTypes

from lotb.common.plugin_class import PluginBase
from lotb.common.tools import plugin_tool
from lotb.common.tools import ToolResult


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

  def get_tools(self):
    return [
      plugin_tool(
        "lotb_socialfix_fix",
        "Fix a supported social URL using enabled providers",
        {"url": {"type": "string", "minLength": 1}},
        self.fix_action,
      )
    ]

  async def fix_action(self, update, context, url: str) -> ToolResult:
    replacements = ["https://fxtwitter.com/", "https://www.ddinstagram.com/", "https://rxddit.com/"]
    patterns = [
      r"^https://x\.com/(.+)",
      r"^https://www\.instagram\.com/(.+)",
      r"^https://(?:www\.|old\.)?reddit\.com/(.+)",
    ]
    for pattern, replacement in zip(patterns, replacements):
      if pattern in self.pattern_actions and (match := re.fullmatch(pattern, url)):
        return ToolResult(True, {"url": replacement + match[1]})
    return ToolResult(False, {}, "Unsupported or disabled social URL")

  async def execute(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await self.intercept_patterns(update, context, self.pattern_actions):
      return
    url = self.command_arguments(update).strip()
    if url:
      result = await self.fix_action(update, context, url)
      await self.reply_message(update, context, result.data["url"] if result.ok else result.error or "Action failed")

  async def fix_twitter_link(self, update: Update, context: ContextTypes.DEFAULT_TYPE, match: re.Match):
    await self.reply_fixed_link(update, context, match)

  async def fix_instagram_link(self, update: Update, context: ContextTypes.DEFAULT_TYPE, match: re.Match):
    await self.reply_fixed_link(update, context, match)

  async def fix_reddit_link(self, update: Update, context: ContextTypes.DEFAULT_TYPE, match: re.Match):
    await self.reply_fixed_link(update, context, match)

  async def reply_fixed_link(self, update, context, match):
    if match:
      result = await self.fix_action(update, context, match[0])
      if result.ok:
        await self.reply_message(update, context, result.data["url"])
