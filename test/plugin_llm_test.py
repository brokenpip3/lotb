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
    "plugins.llm": {"model": "closed-ai-gpt44", "apikey": "soon-I-will-be-leaked", "friendlyname": "Dino"},
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

  with (
    patch("lotb.common.plugin_class.PluginBase.llm_completion", new=AsyncMock(return_value=mock_response)) as mock_llm,
    patch("lotb.common.plugin_class.PluginBase.send_typing_action", new=AsyncMock()) as mock_typing,
  ):
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
  mock_update.message.text = "/llm test"
  plugin = Plugin()
  with patch.object(plugin, "config", None):
    await plugin.execute(mock_update, mock_context)
    error_message = mock_update.message.reply_text.call_args[0][0]
    assert error_message.startswith("LLM error:")


@pytest.mark.asyncio
async def test_llm_api_error(mock_update, mock_context, llm_plugin):
  mock_update.message.text = "/llm hello my dear assistant"
  with (
    patch("lotb.common.plugin_class.PluginBase.llm_completion", new=AsyncMock(side_effect=Exception("Test error"))),
    patch("lotb.common.plugin_class.PluginBase.send_typing_action", new=AsyncMock()),
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

  with (
    patch("lotb.common.plugin_class.PluginBase.llm_completion", new=AsyncMock(return_value=mock_response)) as mock_llm,
    patch("lotb.common.plugin_class.PluginBase.send_typing_action", new=AsyncMock()) as mock_typing,
  ):
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

  with (
    patch("lotb.common.plugin_class.PluginBase.llm_completion", new=AsyncMock(return_value=mock_response)) as mock_llm,
    patch("lotb.common.plugin_class.PluginBase.send_typing_action", new=AsyncMock()) as mock_typing,
  ):
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

  with (
    patch("lotb.common.plugin_class.PluginBase.llm_completion", new=AsyncMock(return_value=mock_response)),
    patch("lotb.common.plugin_class.PluginBase.send_typing_action", new=AsyncMock()),
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


@pytest.mark.asyncio
async def test_trigger_with_hey_trigger(mock_update, mock_context, llm_plugin):
  mock_update.message.text = "hey Dino, what's the weather?"
  mock_response = MagicMock()
  mock_response.choices = [MagicMock()]
  mock_response.choices[0].message.content = "It's sunny!"

  with (
    patch("lotb.common.plugin_class.PluginBase.llm_completion", new=AsyncMock(return_value=mock_response)) as mock_llm,
    patch("lotb.common.plugin_class.PluginBase.send_typing_action", new=AsyncMock()) as mock_typing,
  ):
    await llm_plugin.execute(mock_update, mock_context)
    mock_llm.assert_called_once_with(
      messages=[{"role": "system", "content": LLM_ROLE}, {"role": "user", "content": "what's the weather?"}],
      model="closed-ai-gpt44",
      api_key="soon-I-will-be-leaked",
    )
    mock_typing.assert_called_once_with(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_once_with("It's sunny!")


@pytest.mark.asyncio
async def test_trigger_with_comma(mock_update, mock_context, llm_plugin):
  mock_update.message.text = "Dino, tell me a joke"
  mock_response = MagicMock()
  mock_response.choices = [MagicMock()]
  mock_response.choices[
    0
  ].message.content = "do you know that it's 5 year since the last time that Juventus won the serie A?"

  with (
    patch("lotb.common.plugin_class.PluginBase.llm_completion", new=AsyncMock(return_value=mock_response)) as mock_llm,
    patch("lotb.common.plugin_class.PluginBase.send_typing_action", new=AsyncMock()),
  ):
    await llm_plugin.execute(mock_update, mock_context)
    mock_llm.assert_called_once()
    call_args = mock_llm.call_args
    assert call_args[1]["messages"][1]["content"] == "tell me a joke"


@pytest.mark.asyncio
async def test_trigger_case_insensitive(mock_update, mock_context, llm_plugin):
  mock_update.message.text = "DINO: help me with my fire calculation"
  mock_response = MagicMock()
  mock_response.choices = [MagicMock()]
  mock_response.choices[0].message.content = "How can I help?"

  with (
    patch("lotb.common.plugin_class.PluginBase.llm_completion", new=AsyncMock(return_value=mock_response)) as mock_llm,
    patch("lotb.common.plugin_class.PluginBase.send_typing_action", new=AsyncMock()),
  ):
    await llm_plugin.execute(mock_update, mock_context)
    mock_llm.assert_called_once()
    call_args = mock_llm.call_args
    assert call_args[1]["messages"][1]["content"] == "help me with my fire calculation"


@pytest.mark.asyncio
async def test_trigger_with_no_query(mock_update, mock_context, llm_plugin):
  mock_update.message.text = "hey Dino!"
  await llm_plugin.execute(mock_update, mock_context)
  mock_update.message.reply_text.assert_called_once_with("yes? 🦕")


@pytest.mark.asyncio
async def test_trigger_disabled(mock_update, mock_context, mock_config):
  """Test that trigger is disabled when friendlyname is not set"""
  config = MagicMock()
  config.get.side_effect = lambda key, default=None: {
    "plugins.llm": {"model": "gpt-4", "apikey": "test-key"},  # no friendlyname
    "core.database": ":memory:",
  }.get(key, default)

  plugin = Plugin()
  plugin.set_config(config)
  plugin.initialize()

  mock_update.message.text = "hey Dino, hello"
  mock_response = MagicMock()
  mock_response.choices = [MagicMock()]
  mock_response.choices[0].message.content = "Hi!"

  with patch(
    "lotb.common.plugin_class.PluginBase.llm_completion", new=AsyncMock(return_value=mock_response)
  ) as mock_llm:
    await plugin.execute(mock_update, mock_context)
    mock_llm.assert_not_called()


@pytest.mark.asyncio
async def test_trigger_custom_name(mock_update, mock_context, mock_config):
  config = MagicMock()
  config.get.side_effect = lambda key, default=None: {
    "plugins.llm": {"model": "gpt-4", "apikey": "test-key", "friendlyname": "Bot"},
    "core.database": ":memory:",
  }.get(key, default)

  plugin = Plugin()
  plugin.set_config(config)
  plugin.initialize()

  mock_update.message.text = "hey Bot, what time is it?"
  mock_response = MagicMock()
  mock_response.choices = [MagicMock()]
  mock_response.choices[0].message.content = "It's 3 PM"

  with (
    patch("lotb.common.plugin_class.PluginBase.llm_completion", new=AsyncMock(return_value=mock_response)) as mock_llm,
    patch("lotb.common.plugin_class.PluginBase.send_typing_action", new=AsyncMock()),
  ):
    await plugin.execute(mock_update, mock_context)
    mock_llm.assert_called_once()
    call_args = mock_llm.call_args
    assert call_args[1]["messages"][1]["content"] == "what time is it?"


@pytest.mark.asyncio
async def test_trigger_with_punctuation_exclamation(mock_update, mock_context, llm_plugin):
  mock_update.message.text = "Dino! help"
  mock_response = MagicMock()
  mock_response.choices = [MagicMock()]
  mock_response.choices[0].message.content = "OK"

  with (
    patch("lotb.common.plugin_class.PluginBase.llm_completion", new=AsyncMock(return_value=mock_response)) as mock_llm,
    patch("lotb.common.plugin_class.PluginBase.send_typing_action", new=AsyncMock()),
  ):
    await llm_plugin.execute(mock_update, mock_context)
    call_args = mock_llm.call_args
    assert call_args[1]["messages"][1]["content"] == "help"


@pytest.mark.asyncio
async def test_trigger_with_punctuation_question(mock_update, mock_context, llm_plugin):
  mock_update.message.text = "Dino? what's up"
  mock_response = MagicMock()
  mock_response.choices = [MagicMock()]
  mock_response.choices[0].message.content = "OK"

  with (
    patch("lotb.common.plugin_class.PluginBase.llm_completion", new=AsyncMock(return_value=mock_response)) as mock_llm,
    patch("lotb.common.plugin_class.PluginBase.send_typing_action", new=AsyncMock()),
  ):
    await llm_plugin.execute(mock_update, mock_context)
    call_args = mock_llm.call_args
    assert call_args[1]["messages"][1]["content"] == "what's up"


@pytest.mark.asyncio
async def test_trigger_with_space_only(mock_update, mock_context, llm_plugin):
  mock_update.message.text = "Dino help me"
  mock_response = MagicMock()
  mock_response.choices = [MagicMock()]
  mock_response.choices[0].message.content = "OK"

  with (
    patch("lotb.common.plugin_class.PluginBase.llm_completion", new=AsyncMock(return_value=mock_response)) as mock_llm,
    patch("lotb.common.plugin_class.PluginBase.send_typing_action", new=AsyncMock()),
  ):
    await llm_plugin.execute(mock_update, mock_context)
    call_args = mock_llm.call_args
    assert call_args[1]["messages"][1]["content"] == "help me"


@pytest.mark.asyncio
async def test_trigger_with_punctuation_colon(mock_update, mock_context, llm_plugin):
  mock_update.message.text = "Dino: do something"
  mock_response = MagicMock()
  mock_response.choices = [MagicMock()]
  mock_response.choices[0].message.content = "OK"

  with (
    patch("lotb.common.plugin_class.PluginBase.llm_completion", new=AsyncMock(return_value=mock_response)) as mock_llm,
    patch("lotb.common.plugin_class.PluginBase.send_typing_action", new=AsyncMock()),
  ):
    await llm_plugin.execute(mock_update, mock_context)
    call_args = mock_llm.call_args
    assert call_args[1]["messages"][1]["content"] == "do something"


@pytest.mark.asyncio
async def test_trigger_with_no_message(mock_update, mock_context, llm_plugin):
  mock_update.message = None
  mock_update.effective_chat.send_message = AsyncMock()
  await llm_plugin.execute(mock_update, mock_context)
  mock_update.effective_chat.send_message.assert_called_once_with("Message is unavailable")


@pytest.mark.asyncio
async def test_trigger_with_no_message_text(mock_update, mock_context, llm_plugin):
  mock_update.message.text = None
  await llm_plugin.handle_trigger(mock_update, mock_context)
  mock_update.message.reply_text.assert_not_called()


@pytest.mark.asyncio
async def test_process_query_missing_user(mock_update, mock_context, llm_plugin):
  mock_update.effective_user = None
  await llm_plugin.process_query(mock_update, mock_context, "test query")
  mock_update.message.reply_text.assert_called_once_with("User or chat information missing")


@pytest.mark.asyncio
async def test_process_query_missing_chat(mock_update, mock_context, llm_plugin):
  mock_update.effective_chat = None
  await llm_plugin.process_query(mock_update, mock_context, "test query")
  mock_update.message.reply_text.assert_called_once_with("User or chat information missing")


@pytest.mark.asyncio
async def test_initialize_missing_model_warning(caplog, mock_config):
  config = MagicMock()
  config.get.side_effect = lambda key, default=None: {
    "plugins.llm": {"apikey": "test-key"},
    "core.database": ":memory:",
  }.get(key, default)

  plugin = Plugin()
  plugin.set_config(config)
  plugin.initialize()
  assert "missing model" in caplog.text.lower()


@pytest.mark.asyncio
async def test_trigger_not_partial_match_giardino(mock_update, mock_context, llm_plugin):
  mock_update.message.text = "giardino what's up"
  result = await llm_plugin.intercept_patterns(mock_update, mock_context, llm_plugin.pattern_actions)
  assert result is False, "Pattern should not match 'giardino'"


@pytest.mark.asyncio
async def test_trigger_not_partial_match_comodino(mock_update, mock_context, llm_plugin):
  mock_update.message.text = "comodino, help me"
  result = await llm_plugin.intercept_patterns(mock_update, mock_context, llm_plugin.pattern_actions)
  assert result is False, "Pattern should not match 'comodino'"
