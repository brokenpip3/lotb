import os
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from lotb.common.config import Config
from lotb.plugins.rssfeed import Plugin


@pytest.fixture
def mock_feedparser():
  with patch("feedparser.parse") as mock_parse:
    yield mock_parse


@pytest.fixture
def rssfeed_plugin(mock_db):
  with patch.dict(os.environ, {"LOTB_PLUGIN_RSSFEED_CHATID": "4815162342", "LOTB_PLUGIN_RSSFEED_INTERVAL": "60"}):
    config = Config()
    config.config = {
      "core": {"database": "test.db"},
      "plugins": {
        "rssfeed": {
          "enabled": "true",
          "chatid": "4815162342",
          "interval": "60",
          "feeds": [
            {"name": "San-ti-feed", "url": "https://youarebugs.alien"},
            {"name": "Asoiaf-feed2", "url": "https://not.today"},
          ],
        }
      },
    }
    plugin = Plugin()
    plugin.set_config(config)
    plugin.db_cursor = mock_db
    plugin.initialize()
    return plugin


@pytest.mark.asyncio
async def test_check_feeds_new_article_feed1(mock_context, mock_feedparser, rssfeed_plugin):
  rssfeed_plugin.feeds = [{"name": "San-ti-feed", "url": "https://youarebugs.alien"}]
  mock_feedparser.return_value.entries = [
    MagicMock(id="1", title="New Article", link="http://example.com", published="2023-01-01T00:00:00Z")
  ]
  rssfeed_plugin.article_exists = MagicMock(return_value=False)
  rssfeed_plugin.save_article = MagicMock()

  await rssfeed_plugin.check_feeds(mock_context)

  rssfeed_plugin.save_article.assert_called_once()
  mock_context.bot.send_message.assert_called_once_with(
    chat_id=rssfeed_plugin.chat_id, text="New article from San-ti-feed: New Article\nhttp://example.com"
  )


@pytest.mark.asyncio
async def test_check_feeds_new_article_feed2(mock_context, mock_feedparser, rssfeed_plugin):
  rssfeed_plugin.feeds = [{"name": "Asoiaf-feed2", "url": "https://not.today"}]
  mock_feedparser.return_value.entries = [
    MagicMock(id="1", title="New Article", link="http://example.com", published="2023-01-01T00:00:00Z")
  ]
  rssfeed_plugin.article_exists = MagicMock(return_value=False)
  rssfeed_plugin.save_article = MagicMock()

  await rssfeed_plugin.check_feeds(mock_context)

  rssfeed_plugin.save_article.assert_called_once()
  mock_context.bot.send_message.assert_called_once_with(
    chat_id=rssfeed_plugin.chat_id, text="New article from Asoiaf-feed2: New Article\nhttp://example.com"
  )


@pytest.mark.asyncio
async def test_check_feeds_existing_article_feed1(mock_context, mock_feedparser, rssfeed_plugin):
  rssfeed_plugin.feeds = [{"name": "San-ti-feed", "url": "https://youarebugs.alien"}]
  mock_feedparser.return_value.entries = [
    MagicMock(id="1", title="Existing Article", link="http://example.com", published="2023-01-01T00:00:00Z")
  ]
  rssfeed_plugin.article_exists = MagicMock(return_value=True)
  rssfeed_plugin.save_article = MagicMock()

  await rssfeed_plugin.check_feeds(mock_context)

  rssfeed_plugin.save_article.assert_not_called()
  mock_context.bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_check_feeds_existing_article_feed2(mock_context, mock_feedparser, rssfeed_plugin):
  rssfeed_plugin.feeds = [{"name": "Asoiaf-feed2", "url": "https://not.today"}]
  mock_feedparser.return_value.entries = [
    MagicMock(id="1", title="Existing Article", link="http://example.com", published="2023-01-01T00:00:00Z")
  ]
  rssfeed_plugin.article_exists = MagicMock(return_value=True)
  rssfeed_plugin.save_article = MagicMock()

  await rssfeed_plugin.check_feeds(mock_context)

  rssfeed_plugin.save_article.assert_not_called()
  mock_context.bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_execute(mock_update, mock_context, rssfeed_plugin):
  await rssfeed_plugin.execute(mock_update, mock_context)
  mock_update.message.reply_text.assert_called_once_with("RSS Feed Reader is running in the background.")
