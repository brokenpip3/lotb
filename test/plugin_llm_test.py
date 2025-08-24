from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from lotb.plugins.llm import LLM_ROLE
from lotb.plugins.llm import Plugin


@pytest.fixture
def mock_config():
  config = MagicMock()
  config.get.side_effect = lambda key, default=None: {
    "plugins.llm": {"model": "closed-ai-gpt44", "apikey": "soon-I-will-be-leaked"},
    "core.database": ":memory:",
  }.get(key, default)
  return config


@pytest.fixture
def llm_plugin(mock_config):
  plugin = Plugin()
  plugin.set_config(mock_config)
  plugin.initialize()
  return plugin


@pytest.mark.asyncio
async def test_llm_success(mock_update, mock_context, llm_plugin):
  mock_update.message.text = "/llm hello my dear assistant"
  mock_response = MagicMock()
  mock_response.choices = [MagicMock()]
  mock_response.choices[0].message.content = "Hello Boss, how is going?"

  with patch(
    "lotb.common.plugin_class.PluginBase.llm_completion", new=AsyncMock(return_value=mock_response)
  ) as mock_llm, patch(
    "lotb.common.plugin_class.PluginBase.send_typing_action", new=AsyncMock()
  ) as mock_typing:
    await llm_plugin.execute(mock_update, mock_context)
    mock_llm.assert_called_once_with(
      messages=[{"role": "system", "content": LLM_ROLE}, {"role": "user", "content": "hello my dear assistant"}],
      model="closed-ai-gpt44",
      api_key="soon-I-will-be-leaked",
    )
    mock_typing.assert_called_once_with(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_once_with("Hello Boss, how is going?")


@pytest.mark.asyncio
async def test_llm_missing_config(mock_update, mock_context):
  plugin = Plugin()
  with patch.object(plugin, "config", None):
    await plugin.execute(mock_update, mock_context)
    error_message = mock_update.message.reply_text.call_args[0][0]
    assert error_message.startswith("LLM error:")


@pytest.mark.asyncio
async def test_llm_api_error(mock_update, mock_context, llm_plugin):
  mock_update.message.text = "/llm hello my dear assistant"
  with patch("lotb.common.plugin_class.PluginBase.llm_completion", new=AsyncMock(side_effect=Exception("Test error"))), patch(
    "lotb.common.plugin_class.PluginBase.send_typing_action", new=AsyncMock()
  ):
    await llm_plugin.execute(mock_update, mock_context)
    reply = mock_update.message.reply_text.call_args[0][0]
    assert "LLM error" in reply
    assert "Test error" in reply


@pytest.mark.asyncio
async def test_llm_missing_query(mock_update, mock_context, llm_plugin):
  mock_update.message.text = "/llm"
  await llm_plugin.execute(mock_update, mock_context)
  mock_update.message.reply_text.assert_called_once_with("Please provide a query")


@pytest.mark.asyncio
async def test_llm_missing_message(mock_update, mock_context, llm_plugin):
  mock_update.message = None
  mock_update.effective_chat.send_message = AsyncMock()
  await llm_plugin.execute(mock_update, mock_context)
  mock_update.effective_chat.send_message.assert_called_once_with("Message is unavailable")


@pytest.mark.asyncio
async def test_llm_with_quoted_message(mock_update, mock_context, llm_plugin):
  mock_update.message.text = "/llm explain this"
  mock_update.message.reply_to_message = MagicMock()
  mock_update.message.reply_to_message.text = "The mitochondria is the powerhouse of the cell"

  mock_response = MagicMock()
  mock_response.choices = [MagicMock()]
  mock_response.choices[0].message.content = "Hello Boss, how is going?"

  with patch(
    "lotb.common.plugin_class.PluginBase.llm_completion", new=AsyncMock(return_value=mock_response)
  ) as mock_llm, patch(
    "lotb.common.plugin_class.PluginBase.send_typing_action", new=AsyncMock()
  ) as mock_typing:
    await llm_plugin.execute(mock_update, mock_context)
    mock_llm.assert_called_once_with(
      messages=[
        {"role": "system", "content": LLM_ROLE},
        {"role": "user", "content": "explain this\n\nQuoted message:\nThe mitochondria is the powerhouse of the cell"},
      ],
      model="closed-ai-gpt44",
      api_key="soon-I-will-be-leaked",
    )
    mock_typing.assert_called_once_with(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_once_with("Hello Boss, how is going?")


@pytest.mark.asyncio
async def test_llm_with_quoted_message_no_text(mock_update, mock_context, llm_plugin):
  mock_update.message.text = "/llm explain this"
  mock_update.message.reply_to_message = MagicMock()
  mock_update.message.reply_to_message.text = None

  mock_response = MagicMock()
  mock_response.choices = [MagicMock()]
  mock_response.choices[0].message.content = "Hello Boss, how is going?"

  with patch(
    "lotb.common.plugin_class.PluginBase.llm_completion", new=AsyncMock(return_value=mock_response)
  ) as mock_llm, patch(
    "lotb.common.plugin_class.PluginBase.send_typing_action", new=AsyncMock()
  ) as mock_typing:
    await llm_plugin.execute(mock_update, mock_context)
    mock_llm.assert_called_once_with(
      messages=[{"role": "system", "content": LLM_ROLE}, {"role": "user", "content": "explain this"}],
      model="closed-ai-gpt44",
      api_key="soon-I-will-be-leaked",
    )
    mock_typing.assert_called_once_with(mock_update, mock_context)


@pytest.mark.asyncio
async def test_message_history_rotation(mock_update, mock_context, llm_plugin):
  mock_update.message.text = "/llm message1"
  mock_response = MagicMock()
  mock_response.choices = [MagicMock()]
  mock_response.choices[0].message.content = "response1"

  with patch("lotb.common.plugin_class.PluginBase.llm_completion", new=AsyncMock(return_value=mock_response)), patch(
    "lotb.common.plugin_class.PluginBase.send_typing_action", new=AsyncMock()
  ):
    for i in range(1, 5):
      mock_update.message.text = f"/llm message{i}"
      mock_response.choices[0].message.content = f"response{i}"
      await llm_plugin.execute(mock_update, mock_context)

    history = llm_plugin.get_conversation_history(4815162342, 996699)
    assert len(history) == 3

    contents = [msg["content"] for msg in history]
    roles = [msg["role"] for msg in history]
    assert "response3" in contents
    assert "message4" in contents
    assert "response4" in contents
    assert roles.count("user") == 1
    assert roles.count("assistant") == 2
