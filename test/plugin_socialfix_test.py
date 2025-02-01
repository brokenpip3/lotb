from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import pytest

from lotb.common.config import Config
from lotb.plugins.socialfix import Plugin


@pytest.fixture
def mock_config():
  config = MagicMock(spec=Config)
  config.get.side_effect = lambda key, default=None: {
    "core.database": "/tmp/test.db",
    "plugins.socialfix": {"enabled": "true"},
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
