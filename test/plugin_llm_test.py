import json
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from lotb.plugins._llm.prompts import SIMPLE_LLM_ROLE
from lotb.plugins.llm import Plugin


@pytest.fixture
def mock_simple_config():
  config = MagicMock()
  config.get.side_effect = lambda key, default=None: {
    "plugins.llm": {"model": "closed-ai-gpt44", "apikey": "soon-I-will-be-leaked", "friendlyname": "Dino"},
    "core.database": ":memory:",
  }.get(key, default)
  return config


@pytest.fixture
def mock_assistant_config():
  config = MagicMock()
  config.get.side_effect = lambda key, default=None: {
    "plugins.llm": {
      "model": "openMai",
      "apikey": "yes",
      "friendlyname": "Dino",
      "assistant": True,
      "mcpservers": [
        {"name": "free-money-mcp-server", "url": "http://test", "auth_value": "my-incredible-auth"},
        {"name": "mcp-server-avengers", "url": "http://test2", "auth_value": "my-incredible-auth"},
      ],
    },
    "core.database": ":memory:",
  }.get(key, default)
  return config


@pytest.fixture
def simple_plugin(mock_simple_config):
  plugin = Plugin()
  plugin.set_config(mock_simple_config)
  plugin.initialize()
  return plugin


@pytest.fixture
def assistant_plugin(mock_assistant_config):
  plugin = Plugin()
  plugin.set_config(mock_assistant_config)
  plugin.initialize()
  return plugin


@pytest.mark.asyncio
async def test_simple_mode_initialization(simple_plugin):
  assert simple_plugin.name == "llm"
  assert simple_plugin.config_handler.model == "closed-ai-gpt44"
  assert simple_plugin.config_handler.apikey == "soon-I-will-be-leaked"
  assert simple_plugin.config_handler.assistant_mode is False
  assert simple_plugin.handler is not None


@pytest.mark.asyncio
async def test_simple_llm_success(mock_update, mock_context, simple_plugin):
  mock_update.message.text = "/llm hello my dear assistant"
  mock_response = MagicMock()
  mock_response.choices = [MagicMock()]
  mock_response.choices[0].message.content = "Hello Boss, how is going?"

  with (
    patch("lotb.common.plugin_class.PluginBase.llm_completion", new=AsyncMock(return_value=mock_response)) as mock_llm,
    patch("lotb.common.plugin_class.PluginBase.send_typing_action", new=AsyncMock()) as mock_typing,
  ):
    await simple_plugin.execute(mock_update, mock_context)
    mock_llm.assert_called_once_with(
      messages=[{"role": "system", "content": SIMPLE_LLM_ROLE}, {"role": "user", "content": "hello my dear assistant"}],
      model="closed-ai-gpt44",
      api_key="soon-I-will-be-leaked",
    )
    mock_typing.assert_called_once_with(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_once_with("Hello Boss, how is going?")


@pytest.mark.asyncio
async def test_simple_llm_api_error(mock_update, mock_context, simple_plugin):
  mock_update.message.text = "/llm hello my dear assistant"
  with (
    patch("lotb.common.plugin_class.PluginBase.llm_completion", new=AsyncMock(side_effect=Exception("Test error"))),
    patch("lotb.common.plugin_class.PluginBase.send_typing_action", new=AsyncMock()),
  ):
    await simple_plugin.execute(mock_update, mock_context)
    reply = mock_update.message.reply_text.call_args[0][0]
    assert "LLM error" in reply
    assert "Test error" in reply


@pytest.mark.asyncio
async def test_simple_llm_missing_query(mock_update, mock_context, simple_plugin):
  mock_update.message.text = "/llm"
  await simple_plugin.execute(mock_update, mock_context)
  mock_update.message.reply_text.assert_called_once_with("Please provide a query")


@pytest.mark.asyncio
async def test_simple_llm_with_quoted_message(mock_update, mock_context, simple_plugin):
  mock_update.message.text = "/llm explain this"
  mock_update.message.reply_to_message = MagicMock()
  mock_update.message.reply_to_message.text = "The mitochondria is the powerhouse of the cell"

  mock_response = MagicMock()
  mock_response.choices = [MagicMock()]
  mock_response.choices[0].message.content = "Hello Boss, how is going?"

  with (
    patch("lotb.common.plugin_class.PluginBase.llm_completion", new=AsyncMock(return_value=mock_response)) as mock_llm,
    patch("lotb.common.plugin_class.PluginBase.send_typing_action", new=AsyncMock()),
  ):
    await simple_plugin.execute(mock_update, mock_context)
    mock_llm.assert_called_once_with(
      messages=[
        {"role": "system", "content": SIMPLE_LLM_ROLE},
        {"role": "user", "content": "explain this\n\nQuoted message:\nThe mitochondria is the powerhouse of the cell"},
      ],
      model="closed-ai-gpt44",
      api_key="soon-I-will-be-leaked",
    )


@pytest.mark.asyncio
async def test_simple_message_history_rotation(mock_update, mock_context, simple_plugin):
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
      await simple_plugin.execute(mock_update, mock_context)

    history = simple_plugin.handler.history.get_conversation_history(4815162342, 996699)
    assert len(history) == 3

    contents = [msg["content"] for msg in history]
    assert "message4" in contents
    assert "response4" in contents


@pytest.mark.asyncio
async def test_trigger_with_hey(mock_update, mock_context, simple_plugin):
  mock_update.message.text = "Dino, what's the weather?"
  mock_response = MagicMock()
  mock_response.choices = [MagicMock()]
  mock_response.choices[0].message.content = "It's sunny!"

  with (
    patch("lotb.common.plugin_class.PluginBase.llm_completion", new=AsyncMock(return_value=mock_response)) as mock_llm,
    patch("lotb.common.plugin_class.PluginBase.send_typing_action", new=AsyncMock()),
  ):
    await simple_plugin.execute(mock_update, mock_context)
    mock_llm.assert_called_once()
    call_args = mock_llm.call_args
    assert call_args[1]["messages"][1]["content"] == "what's the weather?"
    mock_update.message.reply_text.assert_called_once_with("It's sunny!")


@pytest.mark.asyncio
async def test_trigger_with_comma(mock_update, mock_context, simple_plugin):
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
    await simple_plugin.execute(mock_update, mock_context)
    mock_llm.assert_called_once()
    call_args = mock_llm.call_args
    assert call_args[1]["messages"][1]["content"] == "tell me a joke"


@pytest.mark.asyncio
async def test_trigger_case_insensitive(mock_update, mock_context, simple_plugin):
  mock_update.message.text = "DINO: help me with my fire calculation"
  mock_response = MagicMock()
  mock_response.choices = [MagicMock()]
  mock_response.choices[0].message.content = "How can I help?"

  with (
    patch("lotb.common.plugin_class.PluginBase.llm_completion", new=AsyncMock(return_value=mock_response)) as mock_llm,
    patch("lotb.common.plugin_class.PluginBase.send_typing_action", new=AsyncMock()),
  ):
    await simple_plugin.execute(mock_update, mock_context)
    mock_llm.assert_called_once()
    call_args = mock_llm.call_args
    assert call_args[1]["messages"][1]["content"] == "help me with my fire calculation"


@pytest.mark.asyncio
async def test_trigger_with_no_query(mock_update, mock_context, simple_plugin):
  mock_update.message.text = "Dino!"
  await simple_plugin.execute(mock_update, mock_context)
  mock_update.message.reply_text.assert_called_once_with("yes?")


@pytest.mark.asyncio
async def test_trigger_with_punctuation(mock_update, mock_context, simple_plugin):
  test_cases = [("Dino! help", "help"), ("Dino? what's up", "what's up"), ("Dino: do something", "do something")]

  for message_text, expected_query in test_cases:
    # Clear history before each test case
    user_id = mock_update.effective_user.id
    chat_id = mock_update.effective_chat.id
    simple_plugin.handler.history.clear_history(user_id, chat_id)

    mock_update.message.text = message_text
    mock_update.message.reply_text.reset_mock()

    with (
      patch(
        "lotb.common.plugin_class.PluginBase.llm_completion",
        new=AsyncMock(return_value=MagicMock(choices=[MagicMock(message=MagicMock(content="OK"))])),
      ) as mock_llm,
      patch("lotb.common.plugin_class.PluginBase.send_typing_action", new=AsyncMock()),
    ):
      await simple_plugin.execute(mock_update, mock_context)
      call_args = mock_llm.call_args
      assert call_args[1]["messages"][1]["content"] == expected_query


@pytest.mark.asyncio
async def test_trigger_not_partial_match(mock_update, mock_context, simple_plugin):
  mock_update.message.text = "giardino what's up"
  result = await simple_plugin.intercept_patterns(mock_update, mock_context, simple_plugin.handler.pattern_actions)
  assert result is False


@pytest.mark.asyncio
async def test_trigger_disabled(mock_update, mock_context):
  config = MagicMock()
  config.get.side_effect = lambda key, default=None: {
    "plugins.llm": {"model": "gpt-4", "apikey": "test-key"},
    "core.database": ":memory:",
  }.get(key, default)

  plugin = Plugin()
  plugin.set_config(config)
  plugin.initialize()

  mock_update.message.text = "Dino, hello"
  mock_response = MagicMock()
  mock_response.choices = [MagicMock()]
  mock_response.choices[0].message.content = "Hi!"

  with patch(
    "lotb.common.plugin_class.PluginBase.llm_completion", new=AsyncMock(return_value=mock_response)
  ) as mock_llm:
    await plugin.execute(mock_update, mock_context)
    mock_llm.assert_not_called()


@pytest.mark.asyncio
async def test_assistant_mode_initialization(assistant_plugin):
  assert assistant_plugin.name == "llm"
  assert assistant_plugin.config_handler.model == "openMai"
  assert assistant_plugin.config_handler.apikey == "yes"
  assert assistant_plugin.config_handler.assistant_mode is True
  assert len(assistant_plugin.config_handler.mcp_servers) == 2
  assert assistant_plugin.handler is not None


@pytest.mark.asyncio
async def test_assistant_help_command(assistant_plugin, mock_update, mock_context):
  mock_update.message.text = "/llm help"
  await assistant_plugin.execute(mock_update, mock_context)
  reply_text = mock_update.message.reply_text.call_args[0][0]
  assert "🤖 Assistant help" in reply_text
  assert "/llm <prompt>" in reply_text


@pytest.mark.asyncio
async def test_assistant_tools_command(assistant_plugin, mock_update, mock_context):
  mock_update.message.text = "/llm tools"
  with patch.object(assistant_plugin.handler, "_ensure_tools_loaded", new_callable=AsyncMock) as mock_load:
    mock_load.return_value = []
    await assistant_plugin.execute(mock_update, mock_context)
    mock_load.assert_called()
    mock_update.message.reply_text.assert_called()


@pytest.mark.asyncio
async def test_assistant_status_command(assistant_plugin, mock_update, mock_context):
  mock_update.message.text = "/llm status"
  with patch.object(assistant_plugin.handler, "_ensure_tools_loaded", new_callable=AsyncMock) as mock_load:
    mock_load.return_value = []
    await assistant_plugin.execute(mock_update, mock_context)
    mock_load.assert_called()
    reply_text = mock_update.message.reply_text.call_args[0][0]
    assert "🔧 Assistant status" in reply_text


@pytest.mark.asyncio
async def test_assistant_query(assistant_plugin, mock_update, mock_context):
  mock_update.message.text = "/llm question without a real answer"
  with (
    patch.object(assistant_plugin.handler, "_handle_llm_conversation", new_callable=AsyncMock) as mock_handle,
    patch("lotb.common.plugin_class.PluginBase.send_typing_action", new=AsyncMock()),
  ):
    mock_handle.return_value = "test response"
    await assistant_plugin.execute(mock_update, mock_context)
    mock_handle.assert_called()
    mock_update.message.reply_text.assert_called_with("test response")


@pytest.mark.asyncio
async def test_assistant_blocked_input(assistant_plugin, mock_update, mock_context):
  mock_update.message.text = "/llm <script>alert('xss')</script>"
  await assistant_plugin.execute(mock_update, mock_context)
  reply_text = mock_update.message.reply_text.call_args[0][0]
  assert "invalid input" in reply_text.lower()


@pytest.mark.asyncio
async def test_assistant_ensure_tools_loaded(assistant_plugin):
  with (
    patch.object(assistant_plugin.handler.mcp, "load_all_tools", new_callable=AsyncMock) as mock_tools,
    patch.object(assistant_plugin.handler.mcp, "load_all_resources", new_callable=AsyncMock) as mock_resources,
    patch.object(assistant_plugin.handler.tool_handler, "create_resource_tools", new_callable=AsyncMock) as mock_create,
  ):
    mock_tools.return_value = []
    mock_resources.return_value = []
    mock_create.return_value = []
    await assistant_plugin.handler._ensure_tools_loaded()
    mock_tools.assert_called()
    mock_resources.assert_called()


@pytest.mark.asyncio
async def test_assistant_handle_llm_conversation(assistant_plugin):
  messages = [{"role": "user", "content": "test"}]
  with patch.object(assistant_plugin.handler, "_get_llm_response", new_callable=AsyncMock) as mock_llm:
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "test response"
    mock_choice.message.tool_calls = None
    mock_response.choices = [mock_choice]
    mock_llm.return_value = (mock_choice.message, None)
    response = await assistant_plugin.handler._handle_llm_conversation(messages)
    assert response == "test response"


@pytest.mark.asyncio
async def test_assistant_tool_call_blocked(assistant_plugin):
  tool_call = MagicMock()
  tool_call.function.name = "exec_shell"
  tool_call.function.arguments = "{}"
  tool_call.id = "call_id"
  messages = []

  await assistant_plugin.handler.tool_handler.execute_tool_call(tool_call, messages, [])
  assert "security error" in messages[0]["content"].lower()


@pytest.mark.asyncio
async def test_assistant_tool_call_valid_mcp(assistant_plugin):
  tool_call = MagicMock()
  tool_call.function.name = "valid_tool"
  tool_call.function.arguments = json.dumps({"arg1": "value1"})
  tool_call.id = "call_id"
  messages = []

  assistant_plugin.handler.mcp.tool_to_server_map = {"valid_tool": {"name": "test-server"}}
  assistant_plugin.handler.tool_handler.call_tool_from_session = AsyncMock(return_value="tool result")

  await assistant_plugin.handler.tool_handler.execute_tool_call(tool_call, messages, [])
  assert messages[0]["role"] == "tool"
  assert messages[0]["content"] == "tool result"


@pytest.mark.asyncio
async def test_assistant_tool_call_resource(assistant_plugin):
  tool_call = MagicMock()
  tool_call.function.name = "read_resource_mind"
  tool_call.function.arguments = "{}"
  tool_call.id = "call_id"
  messages = []
  tools = [{"type": "function", "function": {"name": "read_resource_mind"}, "_resource_uri": "uri1"}]

  assistant_plugin.handler.tool_handler.read_resource = AsyncMock(return_value="resource content")

  await assistant_plugin.handler.tool_handler.execute_tool_call(tool_call, messages, tools)
  assert messages[0]["content"] == "resource content"


@pytest.mark.asyncio
async def test_assistant_tool_call_invalid_json(assistant_plugin):
  tool_call = MagicMock()
  tool_call.function.name = "valid_tool"
  tool_call.function.arguments = "{invalid_json"
  tool_call.id = "call_id"
  messages = []

  await assistant_plugin.handler.tool_handler.execute_tool_call(tool_call, messages, [])
  assert "invalid tool arguments" in messages[0]["content"].lower()


@pytest.mark.asyncio
async def test_assistant_llm_conversation_with_tool_calls(assistant_plugin):
  messages = [{"role": "user", "content": "question"}]

  tool_call = MagicMock()
  tool_call.function.name = "test_tool"
  tool_call.function.arguments = json.dumps({})
  tool_call.id = "call_id"

  first_message = MagicMock()
  first_message.content = None
  first_message.tool_calls = [tool_call]

  second_message = MagicMock()
  second_message.content = "final answer"
  second_message.tool_calls = None

  assistant_plugin.handler._get_llm_response = AsyncMock(side_effect=[(first_message, None), (second_message, None)])
  assistant_plugin.handler.tool_handler.execute_tool_call = AsyncMock(
    side_effect=lambda tc, msgs, tools: (
      msgs.append({"role": "tool", "tool_call_id": tc.id, "content": "result"}) or "continue"
    )
  )

  response = await assistant_plugin.handler._handle_llm_conversation(messages)
  assert response == "final answer"


@pytest.mark.asyncio
async def test_assistant_llm_conversation_max_iterations(assistant_plugin):
  messages = [{"role": "user", "content": "test"}]
  tool_call = MagicMock()
  tool_call.function.name = "test_tool"
  tool_call.function.arguments = json.dumps({})
  tool_call.id = "call_id"

  llm_message = MagicMock()
  llm_message.content = None
  llm_message.tool_calls = [tool_call]

  assistant_plugin.handler._get_llm_response = AsyncMock(return_value=(llm_message, None))
  assistant_plugin.handler.tool_handler.execute_tool_call = AsyncMock(return_value="continue")

  response = await assistant_plugin.handler._handle_llm_conversation(messages)
  assert "max tool call iterations" in response


@pytest.mark.asyncio
async def test_assistant_show_status(assistant_plugin, mock_update, mock_context):
  assistant_plugin.handler.tools = [1, 2, 3]
  assistant_plugin.handler.resources = [1]
  assistant_plugin.handler.mcp.tool_to_server_map = {"tool1": "server1"}

  await assistant_plugin.handler.show_status(mock_update, mock_context)
  reply_text = mock_update.message.reply_text.call_args[0][0]
  assert "openMai" in reply_text
  assert "✅" in reply_text


@pytest.mark.asyncio
async def test_assistant_show_tools(assistant_plugin, mock_update, mock_context):
  assistant_plugin.handler.tools = [
    {"type": "function", "function": {"name": "test_tool", "description": "test desc"}},
    {"type": "function", "function": {"name": "read_resource_mind", "description": "read resource"}},
  ]
  assistant_plugin.handler.mcp.tool_to_server_map = {"test_tool": {"name": "test-server"}}

  await assistant_plugin.handler.show_tools(mock_update, mock_context)
  reply_text = mock_update.message.reply_text.call_args[0][0]
  assert "test_tool" in reply_text
  assert "test desc" in reply_text


@pytest.mark.asyncio
async def test_assistant_capabilities_summary_empty(assistant_plugin):
  assistant_plugin.handler.tools = []
  assistant_plugin.handler.resources = []
  summary = await assistant_plugin.handler._generate_capabilities_summary()
  assert "no capabilities available" in summary


@pytest.mark.asyncio
async def test_assistant_capabilities_summary_with_tools(assistant_plugin):
  assistant_plugin.handler.tools = [{"type": "function", "function": {"name": "test_tool", "description": "test"}}]
  assistant_plugin.handler.resources = []
  summary = await assistant_plugin.handler._generate_capabilities_summary()
  assert "TOOLS" in summary
  assert "test_tool" in summary


@pytest.mark.asyncio
async def test_config_validation_warnings(caplog):
  config = MagicMock()
  config.get.side_effect = lambda key, default=None: {
    "plugins.llm": {},  # Missing everything
    "core.database": ":memory:",
  }.get(key, default)

  plugin = Plugin()
  plugin.set_config(config)
  plugin.initialize()
  assert "missing api key" in caplog.text.lower()
  assert "missing model" in caplog.text.lower()


@pytest.mark.asyncio
async def test_config_assistant_mode_no_servers_warning(caplog):
  config = MagicMock()
  config.get.side_effect = lambda key, default=None: {
    "plugins.llm": {"model": "gpt-4", "apikey": "test", "assistant": True, "mcpservers": []},
    "core.database": ":memory:",
  }.get(key, default)

  plugin = Plugin()
  plugin.set_config(config)
  plugin.initialize()
  assert "no mcp servers" in caplog.text.lower()


@pytest.mark.asyncio
async def test_history_save_and_get(simple_plugin, mock_update):
  user_id = mock_update.effective_user.id
  chat_id = mock_update.effective_chat.id
  history = simple_plugin.handler.history

  history.save_message(user_id, chat_id, "user", "test message")
  history.save_message(user_id, chat_id, "assistant", "test response")

  retrieved = history.get_conversation_history(user_id, chat_id)
  assert len(retrieved) == 2
  assert retrieved[0]["content"] == "test message"
  assert retrieved[1]["content"] == "test response"


@pytest.mark.asyncio
async def test_history_truncation(simple_plugin, mock_update):
  user_id = mock_update.effective_user.id
  chat_id = mock_update.effective_chat.id
  history = simple_plugin.handler.history

  long_content = "x" * 3000
  history.save_message(user_id, chat_id, "user", long_content)

  retrieved = history.get_conversation_history(user_id, chat_id)
  assert len(retrieved[0]["content"]) == 2000


@pytest.mark.asyncio
async def test_history_rotation(simple_plugin, mock_update):
  user_id = mock_update.effective_user.id
  chat_id = mock_update.effective_chat.id
  history = simple_plugin.handler.history

  for i in range(5):
    history.save_message(user_id, chat_id, "user", f"message{i}")

  retrieved = history.get_conversation_history(user_id, chat_id)
  assert len(retrieved) == 3
  assert "message2" in retrieved[0]["content"]


@pytest.mark.asyncio
async def test_tool_handler_read_resource_content_types(assistant_plugin):
  handler = assistant_plugin.handler.tool_handler
  session = MagicMock()
  server_cfg = {"name": "juve_store", "url": "http://juventus.com", "auth_value": "finoallafine"}

  mock_result = MagicMock()
  mock_content = MagicMock()
  mock_content.text = "Forza Juve"
  del mock_content.blob
  mock_result.contents = [mock_content]
  session.read_resource = AsyncMock(return_value=mock_result)

  with patch("lotb.plugins._llm.mcp_manager.MCPSessionManager.session_context") as mock_ctx:
    mock_ctx.return_value.__aenter__.return_value = session

    assistant_plugin.handler.mcp.resource_to_server_map = {"juve://stadium": server_cfg}

    mock_ctx.return_value.__aenter__.return_value = session

    res = await handler.read_resource("juve://stadium")
    assert res == "Forza Juve"

    mock_content_blob = MagicMock()
    mock_content_blob.blob = "trophy_image_blob"
    del mock_content_blob.text
    mock_result.contents = [mock_content_blob, mock_content]
    res = await handler.read_resource("juve://stadium")
    assert res == "Forza Juve"

    mock_content_other = MagicMock()
    del mock_content_other.text
    del mock_content_other.blob
    mock_content_other.__str__.return_value = "scudetto"
    mock_result.contents = [mock_content_other]
    res = await handler.read_resource("juve://stadium")
    assert res == "scudetto"


@pytest.mark.asyncio
async def test_tool_handler_call_tool_content_types(assistant_plugin):
  handler = assistant_plugin.handler.tool_handler
  session = MagicMock()
  server_cfg = {"name": "allianz_stadium", "url": "http://test", "auth_value": "token"}
  assistant_plugin.handler.mcp.tool_to_server_map = {"buy_ticket": server_cfg}

  with patch("lotb.plugins._llm.mcp_manager.MCPSessionManager.session_context") as mock_ctx:
    mock_ctx.return_value.__aenter__.return_value = session

    mock_result = MagicMock()
    mock_item = MagicMock()
    mock_item.text = "Ticket purchased"
    mock_result.content = [mock_item]
    session.call_tool = AsyncMock(return_value=mock_result)

    res = await handler.call_tool("buy_ticket", {})
    assert res == "Ticket purchased"

    mock_result.content = MagicMock()
    mock_result.content.text = "Season pass"
    session.call_tool = AsyncMock(return_value=mock_result)

    res = await handler.call_tool("buy_ticket", {})
    assert res == "Season pass"

    session.call_tool = AsyncMock(return_value="Sold out")
    res = await handler.call_tool("buy_ticket", {})
    assert res == "Sold out"


@pytest.mark.asyncio
async def test_tool_handler_create_resource_tools_naming(assistant_plugin):
  handler = assistant_plugin.handler.tool_handler
  resources = [
    {"uri": "juve://history", "name": "History.txt"},
    {"uri": "juve://players", "name": "Del-Piero"},
  ]

  tools = await handler.create_resource_tools(resources)
  assert len(tools) == 2
  assert tools[0]["function"]["name"] == "read_resource_History_txt"
  assert tools[1]["function"]["name"] == "read_resource_Del_Piero"


@pytest.mark.asyncio
async def test_mcp_manager_list_methods(assistant_plugin):
  manager = assistant_plugin.handler.mcp
  session = MagicMock()
  server_cfg = {"name": "continassa", "url": "http://test", "auth_value": "token"}

  mock_response = MagicMock()
  mock_res = MagicMock()
  mock_res.uri = "juve://training_center"
  mock_res.name = "Training Schedule"
  mock_res.description = "Daily training"
  mock_res.mimeType = "text/plain"
  mock_response.resources = [mock_res]
  session.list_resources = AsyncMock(return_value=mock_response)

  with patch("lotb.plugins._llm.mcp_manager.MCPSessionManager.session_context") as mock_ctx:
    mock_ctx.return_value.__aenter__.return_value = session

    resources = await manager.list_resources(server_cfg)
    assert len(resources) == 1
    assert resources[0]["uri"] == "juve://training_center"


@pytest.mark.asyncio
async def test_simple_llm_handler_process_query_error(simple_plugin, mock_update, mock_context):
  with (
    patch("lotb.common.plugin_class.PluginBase.llm_completion", new=AsyncMock(side_effect=Exception("Referee Error"))),
    patch("lotb.common.plugin_class.PluginBase.send_typing_action", new=AsyncMock()),
  ):
    await simple_plugin.handler.process_query(mock_update, mock_context, "query")
    mock_update.message.reply_text.assert_called()
    assert "LLM error: Referee Error" in mock_update.message.reply_text.call_args[0][0]


@pytest.mark.asyncio
async def test_assistant_handler_process_query_error(assistant_plugin, mock_update, mock_context):
  with patch.object(assistant_plugin.handler, "_ensure_tools_loaded", side_effect=Exception("VAR Check Failed")):
    await assistant_plugin.handler.process_query(mock_update, mock_context, "query")
    mock_update.message.reply_text.assert_called()
    assert "something went wrong" in mock_update.message.reply_text.call_args[0][0]
