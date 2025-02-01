from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from lotb.plugins.readwise import Plugin


@pytest.fixture
def mock_update(mock_update):
  update = mock_update
  update.message.text = "/readwise https://wikipedia.com"
  return update


@pytest.mark.asyncio
@patch("lotb.plugins.readwise.httpx.AsyncClient")
@patch("lotb.plugins.readwise.httpx.Client")
async def test_save_url(mock_httpx_client, mock_httpx_async, mock_update, mock_context):
  mock_response_valid = MagicMock()
  mock_response_valid.status_code = 204
  mock_httpx_client.return_value.__enter__.return_value.get.return_value = mock_response_valid

  mock_response_save = MagicMock()
  mock_response_save.status_code = 201
  mock_httpx_async.return_value.__aenter__.return_value.post.return_value = mock_response_save

  config = MagicMock()
  config.get.side_effect = lambda key, default=None: {
    "plugins.readwise": {"enabled": "true", "token": "fake_token"}
  }.get(key, default)

  plugin = Plugin()
  plugin.set_config(config)
  plugin.initialize()
  await plugin.execute(mock_update, mock_context)
  mock_update.message.reply_text.assert_called_once_with("URL saved to Readwise successfully.", quote=True)


@pytest.mark.asyncio
@patch("lotb.plugins.readwise.httpx.AsyncClient")
@patch("lotb.plugins.readwise.httpx.Client")
async def test_readwise_article_already_exist(mock_httpx_client, mock_httpx_async, mock_update, mock_context):
  mock_response_valid = MagicMock()
  mock_response_valid.status_code = 204
  mock_httpx_client.return_value.__enter__.return_value.get.return_value = mock_response_valid

  mock_response_already_present = MagicMock()
  mock_response_already_present.status_code = 200
  mock_httpx_async.return_value.__aenter__.return_value.post.return_value = mock_response_already_present

  config = MagicMock()
  config.get.side_effect = lambda key, default=None: {
    "plugins.readwise": {"enabled": "true", "token": "fake_token"}
  }.get(key, default)

  plugin = Plugin()
  plugin.set_config(config)
  plugin.initialize()
  await plugin.execute(mock_update, mock_context)
  mock_update.message.reply_text.assert_called_once_with("URL already exists in your Readwise archive.", quote=True)


@pytest.mark.asyncio
@patch("lotb.plugins.readwise.httpx.Client")
async def test_readwise_invalid_token(mock_httpx_client):
  mock_response_invalid = MagicMock()
  mock_response_invalid.status_code = 401
  mock_httpx_client.return_value.__enter__.return_value.get.return_value = mock_response_invalid

  config = MagicMock()
  config.get.side_effect = lambda key, default=None: {
    "plugins.readwise": {"enabled": "true", "token": "fake_token"}
  }.get(key, default)

  with pytest.raises(ValueError, match="Readwise token is not valid."):
    plugin = Plugin()
    plugin.set_config(config)
    plugin.initialize()


@pytest.mark.asyncio
@patch("lotb.plugins.readwise.httpx.AsyncClient")
@patch("lotb.plugins.readwise.httpx.Client")
async def test_readwise_no_url(mock_httpx_client, mock_httpx_async, mock_update, mock_context):
  mock_response_valid = MagicMock()
  mock_response_valid.status_code = 204
  mock_httpx_client.return_value.__enter__.return_value.get.return_value = mock_response_valid

  mock_response_save = MagicMock()
  mock_response_save.status_code = 201
  mock_httpx_async.return_value.__aenter__.return_value.post.return_value = mock_response_save

  config = MagicMock()
  config.get.side_effect = lambda key, default=None: {
    "plugins.readwise": {"enabled": "true", "token": "fake_token"}
  }.get(key, default)

  plugin = Plugin()
  plugin.set_config(config)
  plugin.initialize()
  mock_update.message.text = "/readwise"
  await plugin.execute(mock_update, mock_context)
  mock_update.message.reply_text.assert_called_once_with("Missing URL argument for Readwise command.", quote=True)
