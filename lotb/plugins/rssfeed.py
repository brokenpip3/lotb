# farewell https://github.com/brokenpip3/rtt
from datetime import datetime
from typing import Any
from typing import List

import feedparser
from dateutil import parser
from telegram import Update
from telegram.ext import ContextTypes
from telegram.ext import JobQueue

from lotb.common.plugin_class import PluginBase


class Plugin(PluginBase):
  def __init__(self):
    super().__init__("rssfeed", "RSS Feed Reader Plugin", False)

  def initialize(self):
    plugin_config = self.config.get(f"plugins.{self.name}", {})
    if not plugin_config.get("enabled") or plugin_config.get("enabled") is False:
      raise ValueError("RSS feed not loaded: not enabled in config")
    if plugin_config.get("debug"):
      self.log_info(f"Configuration for {self.name}: {plugin_config}")

    self.chat_id = plugin_config.get("chatid")
    self.check_interval = int(plugin_config.get("interval", 3600))
    self.feeds = plugin_config.get("feeds", [])
    if not self.chat_id or not self.feeds:
      raise ValueError("RSS feed chat ID or feeds not found in configuration.")

    self.create_table()
    self.log_info("RSS Feed Reader plugin initialized.")

  def create_table(self):
    query = """
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            feed_name TEXT,
            article_id TEXT,
            title TEXT,
            link TEXT,
            published TIMESTAMP
        )
        """
    self.db_cursor.execute(query)
    self.connection.commit()

  def get_last_articles_sorted(self, feed_url: str, num_articles: int) -> List[Any]:
    feed = feedparser.parse(feed_url)
    sorted_entries = sorted(feed.entries, key=lambda entry: parser.parse(entry.published))
    last_articles = sorted_entries[:num_articles]
    return last_articles

  async def check_feeds(self, context: ContextTypes.DEFAULT_TYPE):
    self.log_info("Checking RSS feeds for new articles.")
    for feed in self.feeds:
      feed_name = feed["name"]
      feed_url = feed["url"]
      self.log_info(f"Checking feed: {feed_name}")
      feed_data = self.get_last_articles_sorted(feed_url, 5)
      for entry in feed_data:
        article_id = entry.id
        if not self.article_exists(feed_name, article_id):
          self.save_article(feed_name, entry)
          message = f"New article from {feed_name}: {entry.title}\n{entry.link}"
          await context.bot.send_message(chat_id=self.chat_id, text=message)
          self.log_info(f"Sent new article: {entry.title}")

  def article_exists(self, feed_name, article_id):
    query = "SELECT 1 FROM articles WHERE feed_name = ? AND article_id = ?"
    self.db_cursor.execute(query, (feed_name, article_id))
    return self.db_cursor.fetchone() is not None

  def save_article(self, feed_name, entry):
    query = """
        INSERT INTO articles (feed_name, article_id, title, link, published)
        VALUES (?, ?, ?, ?, ?)
        """
    self.db_cursor.execute(query, (feed_name, entry.id, entry.title, entry.link, datetime(*entry.published_parsed[:6])))
    self.connection.commit()

  async def execute(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    await self.reply_message(update, context, "RSS Feed Reader is running in the background.")

  def set_job_queue(self, job_queue: JobQueue):
    job_queue.run_repeating(self.check_feeds, interval=self.check_interval, first=0)
