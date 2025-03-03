from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import pytest

from lotb.common.config import Config
from lotb.plugins.socialfix import Plugin


@pytest.fixture
def mock_config():
  config = MagicMock(spec=Config)
  config.get.side_effect = lambda key, default=None: {
    "core.database": ":memory:",
    "plugins.socialfix": {"enabled": True},
    "plugins.socialfix.twitter": True,
    "plugins.socialfix.instagram": True,
    "plugins.socialfix.reddit": True,
  }.get(key, default)
  return config


@pytest.fixture
def socialfix_plugin(mock_config):
  plugin = Plugin()
  plugin.set_config(mock_config)
  plugin.initialize()
  plugin.reply_message = AsyncMock()
  return plugin


@pytest.mark.asyncio
async def test_fix_twitter_link(mock_update, mock_context, socialfix_plugin):
  mock_update.message.text = "https://x.com/fuckyoumask"
  await socialfix_plugin.execute(mock_update, mock_context)
  socialfix_plugin.reply_message.assert_awaited_once_with(
    mock_update, mock_context, "https://fxtwitter.com/fuckyoumask"
  )


@pytest.mark.asyncio
async def test_fix_instagram_link(mock_update, mock_context, socialfix_plugin):
  mock_update.message.text = "https://www.instagram.com/stupidmemethatisnotfunny"
  await socialfix_plugin.execute(mock_update, mock_context)
  socialfix_plugin.reply_message.assert_awaited_once_with(
    mock_update, mock_context, "https://www.ddinstagram.com/stupidmemethatisnotfunny"
  )


@pytest.mark.asyncio
async def test_fix_reddit_link(mock_update, mock_context, socialfix_plugin):
  mock_update.message.text = "https://www.reddit.com/r/interestingasfuck/comments/1iivowu/very_smart/"
  await socialfix_plugin.execute(mock_update, mock_context)
  socialfix_plugin.reply_message.assert_awaited_once_with(
    mock_update, mock_context, "https://rxddit.com/r/interestingasfuck/comments/1iivowu/very_smart/"
  )


@pytest.mark.asyncio
async def test_fix_old_reddit_link(mock_update, mock_context, socialfix_plugin):
  mock_update.message.text = "https://old.reddit.com/r/interestingasfuck/comments/1iivowu/very_smart/"
  await socialfix_plugin.execute(mock_update, mock_context)
  socialfix_plugin.reply_message.assert_awaited_once_with(
    mock_update, mock_context, "https://rxddit.com/r/interestingasfuck/comments/1iivowu/very_smart/"
  )


@pytest.mark.asyncio
async def test_disabled_twitter(mock_update, mock_context, mock_config):
  mock_config.get.side_effect = lambda key, default=None: {
    "core.database": ":memory:",
    "plugins.socialfix.enabled": True,
    "plugins.socialfix.twitter": False,
  }.get(key, default)

  plugin = Plugin()
  plugin.set_config(mock_config)
  plugin.initialize()
  plugin.reply_message = AsyncMock()

  mock_update.message.text = "https://x.com/fuckyoumask"
  await plugin.execute(mock_update, mock_context)
  plugin.reply_message.assert_not_called()


@pytest.mark.asyncio
async def test_disabled_instagram(mock_update, mock_context, mock_config):
  mock_config.get.side_effect = lambda key, default=None: {
    "core.database": ":memory:",
    "plugins.socialfix.enabled": True,
    "plugins.socialfix.instagram": False,
  }.get(key, default)

  plugin = Plugin()
  plugin.set_config(mock_config)
  plugin.initialize()
  plugin.reply_message = AsyncMock()

  mock_update.message.text = "https://www.instagram.com/stupidmemethatisnotfunny"
  await plugin.execute(mock_update, mock_context)
  plugin.reply_message.assert_not_called()


@pytest.mark.asyncio
async def test_disabled_reddit(mock_update, mock_context, mock_config):
  mock_config.get.side_effect = lambda key, default=None: {
    "core.database": ":memory:",
    "plugins.socialfix.enabled": True,
    "plugins.socialfix.reddit": False,
  }.get(key, default)

  plugin = Plugin()
  plugin.set_config(mock_config)
  plugin.initialize()
  plugin.reply_message = AsyncMock()

  mock_update.message.text = "https://www.reddit.com/r/interestingasfuck/comments/1iivowu/very_smart/"
  await plugin.execute(mock_update, mock_context)
  plugin.reply_message.assert_not_called()
