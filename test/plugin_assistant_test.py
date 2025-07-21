import json
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from litellm import ModelResponse
from telegram import Update

from lotb.plugins.assistant import Plugin
from lotb.plugins.assistant import SystemPromptBuilder


@pytest.fixture
def mock_config():
  return {
    "plugins.assistant": {
      "mcpservers": [
        {"name": "free-money-mcp-server", "url": "http://test", "auth_value": "my-incredible-auth"},
        {"name": "mcp-server-avengers", "url": "http://test2", "auth_value": "my-incredible-auth"},
      ],
      "model": "openMai",
      "apikey": "yes",
    }
  }


@pytest.fixture
def assistant_plugin(mock_config):
  plugin = Plugin()
  plugin.set_config(mock_config)
  plugin.initialize()
  return plugin


@pytest.mark.asyncio
async def test_plugin_initialization(assistant_plugin):
  assistant_plugin.initialize()
  assert assistant_plugin.name == "assistant"
  assert assistant_plugin.model == "openMai"
  assert assistant_plugin.api_key == "yes"
  assert len(assistant_plugin.servers) == 2


@pytest.mark.asyncio
async def test_execute_help_command(assistant_plugin, mock_update, mock_context):
  mock_update.message.text = "/assistant help"
  await assistant_plugin.execute(mock_update, mock_context)
  mock_update.message.reply_text.assert_called()


@pytest.mark.asyncio
async def test_execute_tools_command(assistant_plugin, mock_update, mock_context):
  mock_update.message.text = "/assistant tools"
  with patch.object(assistant_plugin, "_ensure_tools_loaded", new_callable=AsyncMock) as mock_load:
    await assistant_plugin.execute(mock_update, mock_context)
    mock_load.assert_called()
    mock_update.message.reply_text.assert_called()


@pytest.mark.asyncio
async def test_execute_status_command(assistant_plugin, mock_update, mock_context):
  mock_update.message.text = "/assistant status"
  await assistant_plugin.execute(mock_update, mock_context)
  mock_update.message.reply_text.assert_called()


@pytest.mark.asyncio
async def test_execute_query(assistant_plugin, mock_update, mock_context):
  mock_update.message.text = "/assistant question without a real answer"
  with patch.object(assistant_plugin, "_handle_llm_conversation", new_callable=AsyncMock) as mock_handle:
    mock_handle.return_value = "test response"
    await assistant_plugin.execute(mock_update, mock_context)
    mock_handle.assert_called()
    mock_update.message.reply_text.assert_called_with("test response")


@pytest.mark.asyncio
async def test_execute_blocked_input(assistant_plugin, mock_update, mock_context):
  mock_update.message.text = "/assistant <script>alert('xss')</script>"
  await assistant_plugin.execute(mock_update, mock_context)
  assert "suspicious" in mock_update.message.reply_text.call_args[0][0].lower()


@pytest.mark.asyncio
async def test_ensure_tools_loaded(assistant_plugin):
  assistant_plugin.initialize()
  with (
    patch.object(assistant_plugin, "_load_all_tools", new_callable=AsyncMock) as mock_tools,
    patch.object(assistant_plugin, "load_all_resources", new_callable=AsyncMock) as mock_resources,
    patch.object(assistant_plugin, "_create_resource_tools", new_callable=AsyncMock) as mock_create,
  ):
    mock_tools.return_value = []
    mock_resources.return_value = []
    mock_create.return_value = []
    await assistant_plugin._ensure_tools_loaded()
    mock_tools.assert_called()
    mock_resources.assert_called()
    mock_create.assert_called()


@pytest.mark.asyncio
async def test_handle_llm_conversation(assistant_plugin):
  assistant_plugin.initialize()
  assistant_plugin.system_prompt_builder = SystemPromptBuilder("a simple example")
  assistant_plugin.capabilities_summary = "test your capabilities"
  messages = [{"role": "user", "content": "test"}]
  with patch.object(assistant_plugin, "_get_llm_response", new_callable=AsyncMock) as mock_llm:
    mock_response = MagicMock(spec=ModelResponse)
    mock_choice = MagicMock()
    mock_choice.message.content = "test response"
    mock_choice.message.tool_calls = None
    mock_response.choices = [mock_choice]
    mock_llm.return_value = (mock_choice.message, None)
    response = await assistant_plugin._handle_llm_conversation(messages)
    assert response == "test response"


@pytest.mark.asyncio
async def test_handle_tool_call(assistant_plugin):
  assistant_plugin.initialize()
  tool_call = MagicMock()
  tool_call.function.name = "create_money_from_nothing_tool"
  tool_call.function.arguments = json.dumps({"arg1": "value1"})
  tool_call.id = "a-ramdom-call-id"
  messages = []
  assistant_plugin.tool_to_server_map = {"create_money_from_nothing_tool": MagicMock()}

  with patch.object(assistant_plugin, "_handle_mcp_tool", new_callable=AsyncMock) as mock_handle:

    async def mock_side_effect(*args, **kwargs):
      messages.append({"role": "tool", "tool_call_id": "a-ramdom-call-id", "content": "tool result"})
      return "continue"

    mock_handle.side_effect = mock_side_effect
    await assistant_plugin._execute_tool_call(tool_call, messages)
    assert len(messages) == 1
    assert messages[0]["role"] == "tool"
    assert messages[0]["tool_call_id"] == "a-ramdom-call-id"
    assert messages[0]["content"] == "tool result"


@pytest.mark.asyncio
async def test_handle_blocked_tool_call(assistant_plugin):
  tool_call = MagicMock()
  tool_call.function.name = "exec_shell"
  tool_call.function.arguments = "{}"
  tool_call.id = "a-ramdom-call-id"
  messages = []

  await assistant_plugin._execute_tool_call(tool_call, messages)
  assert "security error" in messages[0]["content"].lower()


@pytest.mark.asyncio
async def test_execute_tool_call_valid_mcp_tool(assistant_plugin):
  tool_call = MagicMock()
  tool_call.function.name = "valid_tool"
  tool_call.function.arguments = json.dumps({"arg1": "value1"})
  tool_call.id = "a-ramdom-call-id"
  messages = []

  assistant_plugin.tool_to_server_map = {"valid_tool": {"name": "free-money-mcp-server"}}
  assistant_plugin.call_tool_from_session = AsyncMock(return_value="tool result")

  await assistant_plugin._execute_tool_call(tool_call, messages)
  assert messages[0]["role"] == "tool"
  assert messages[0]["tool_call_id"] == "a-ramdom-call-id"
  assert messages[0]["content"] == "tool result"


@pytest.mark.asyncio
async def test_execute_tool_call_valid_resource_tool(assistant_plugin):
  tool_call = MagicMock()
  tool_call.function.name = "read_resource_mind"
  tool_call.function.arguments = "{}"
  tool_call.id = "a-ramdom-call-id"
  messages = []

  assistant_plugin._find_resource_uri_for_tool = MagicMock(return_value="resource_uri")
  assistant_plugin._read_resource = AsyncMock(return_value="resource content")

  await assistant_plugin._execute_tool_call(tool_call, messages)
  assert messages[0]["role"] == "tool"
  assert messages[0]["tool_call_id"] == "a-ramdom-call-id"
  assert messages[0]["content"] == "resource content"


@pytest.mark.asyncio
async def test_execute_tool_call_resource_tool_no_resource_uri(assistant_plugin):
  tool_call = MagicMock()
  tool_call.function.name = "read_resource_mind"
  tool_call.function.arguments = "{}"
  tool_call.id = "a-ramdom-call-id"
  messages = []

  assistant_plugin._find_resource_uri_for_tool = MagicMock(return_value=None)

  await assistant_plugin._execute_tool_call(tool_call, messages)
  assert any("error" in m["content"].lower() for m in messages)


@pytest.mark.asyncio
async def test_execute_tool_call_invalid_tool(assistant_plugin):
  tool_call = MagicMock()
  tool_call.function.name = "invalid_tool"
  tool_call.function.arguments = "{}"
  tool_call.id = "a-ramdom-call-id"
  messages = []

  await assistant_plugin._execute_tool_call(tool_call, messages)
  assert "error" in messages[0]["content"].lower()
  assert "no server" in messages[0]["content"].lower()


@pytest.mark.asyncio
async def test_execute_tool_call_with_invalid_json_args(assistant_plugin):
  tool_call = MagicMock()
  tool_call.function.name = "valid_tool"
  tool_call.function.arguments = "{invalid_json"
  tool_call.id = "a-ramdom-call-id"
  messages = []

  await assistant_plugin._execute_tool_call(tool_call, messages)
  assert "invalid tool arguments format" in messages[0]["content"].lower()


@pytest.mark.asyncio
async def test_handle_llm_conversation_with_tool_calls(assistant_plugin):
  messages = [{"role": "user", "content": "question without a real answer"}]

  tool_call = MagicMock()
  tool_call.function.name = "create_money_from_nothing_tool"
  tool_call.function.arguments = json.dumps({})
  tool_call.id = "call_id"
  first_llm_message = MagicMock()
  first_llm_message.content = None
  first_llm_message.tool_calls = [tool_call]
  second_llm_message = MagicMock()
  second_llm_message.content = "final answer"
  second_llm_message.tool_calls = None

  assistant_plugin._get_llm_response = AsyncMock(side_effect=[(first_llm_message, None), (second_llm_message, None)])
  assistant_plugin._execute_tool_call = AsyncMock(
    side_effect=lambda tool_call, msgs: (
      msgs.append({"role": "tool", "tool_call_id": tool_call.id, "content": "tool result"}) or "continue"
    )
  )

  response = await assistant_plugin._handle_llm_conversation(messages)
  assert response == "final answer"
  assert len(messages) == 4


@pytest.mark.asyncio
async def test_handle_llm_conversation_max_iterations(assistant_plugin):
  messages = [{"role": "user", "content": "question without a real answer"}]
  tool_call = MagicMock()
  tool_call.function.name = "create_money_from_nothing_tool"
  tool_call.function.arguments = json.dumps({})
  tool_call.id = "call_id"
  llm_message = MagicMock()
  llm_message.content = None
  llm_message.tool_calls = [tool_call]
  assistant_plugin._get_llm_response = AsyncMock(return_value=(llm_message, None))
  assistant_plugin._execute_tool_call = AsyncMock(return_value="continue")

  response = await assistant_plugin._handle_llm_conversation(messages)
  assert "max tool call iterations reached" in response


@pytest.mark.asyncio
async def test_handle_llm_conversation_tool_call_failure(assistant_plugin):
  messages = [{"role": "user", "content": "question without a real answer"}]
  tool_call = MagicMock()
  tool_call.function.name = "create_money_from_nothing_tool"
  tool_call.function.arguments = json.dumps({})
  tool_call.id = "call_id"
  llm_message = MagicMock()
  llm_message.content = None
  llm_message.tool_calls = [tool_call]
  assistant_plugin._get_llm_response = AsyncMock(return_value=(llm_message, None))
  assistant_plugin._execute_tool_call = AsyncMock(return_value=None)  # Indicates failure

  response = await assistant_plugin._handle_llm_conversation(messages)
  assert "failed" in response.lower()


@pytest.mark.asyncio
async def test_show_status(assistant_plugin, mock_update, mock_context):
  assistant_plugin.model = "openMai"
  assistant_plugin.api_key = "test-key"
  assistant_plugin.servers = [{"name": "grocery-shop-mcp-server"}, {"name": "server2"}]
  assistant_plugin.tools = [1, 2, 3]
  assistant_plugin.resources = [1]
  assistant_plugin.tool_to_server_map = {"tool1": "grocery-shop-mcp-server"}

  await assistant_plugin.show_status(mock_update, mock_context)
  reply_text = mock_update.message.reply_text.call_args[0][0]
  assert "openMai" in reply_text
  assert "✅" in reply_text
  assert "2" in reply_text  # servers count
  assert "3" in reply_text  # tools count
  assert "1" in reply_text  # resources count
  assert "1" in reply_text  # server mappings count
  assert "grocery-shop-mcp-server" in reply_text
  assert "server2" in reply_text


@pytest.mark.asyncio
async def test_show_tools(assistant_plugin, mock_update, mock_context):
  assistant_plugin.tools = [
    {
      "type": "function",
      "function": {"name": "create_money_from_nothing_tool", "description": "you can create money with this"},
    },
    {"type": "function", "function": {"name": "read_resource_mind", "description": "you can read the mind with this"}},
  ]
  assistant_plugin.tool_to_server_map = {"create_money_from_nothing_tool": {"name": "free-money-mcp-server"}}

  await assistant_plugin.show_tools(mock_update, mock_context)
  reply_text = mock_update.message.reply_text.call_args[0][0]
  assert "create_money_from_nothing_tool" in reply_text
  assert "you can create money with this" in reply_text
  assert "free-money-mcp-server" in reply_text
  assert "read_resource_mind" in reply_text
  assert "you can read the mind with this" in reply_text


@pytest.mark.asyncio
async def test_show_tools_empty(assistant_plugin, mock_update, mock_context):
  assistant_plugin.tools = []
  await assistant_plugin.show_tools(mock_update, mock_context)
  reply_text = mock_update.message.reply_text.call_args[0][0]
  assert "no tools available" in reply_text


@pytest.mark.asyncio
async def test_show_help(assistant_plugin, mock_update, mock_context):
  await assistant_plugin.show_help(mock_update, mock_context)
  reply_text = mock_update.message.reply_text.call_args[0][0]
  assert "🤖 Assistant help" in reply_text
  assert "/assistant <prompt>" in reply_text
  assert "/assistant tools" in reply_text
  assert "/assistant status" in reply_text


@pytest.mark.asyncio
async def test_generate_capabilities_summary_empty(assistant_plugin):
  assistant_plugin.tools = []
  assistant_plugin.resources = []
  summary = await assistant_plugin._generate_capabilities_summary()
  assert "no capabilities available at the moment" in summary


@pytest.mark.asyncio
async def test_generate_capabilities_summary_with_tools(assistant_plugin):
  assistant_plugin.tools = [
    {
      "type": "function",
      "function": {"name": "create_money_from_nothing_tool", "description": "you can create money from nothing"},
    }
  ]
  assistant_plugin.resources = []
  summary = await assistant_plugin._generate_capabilities_summary()
  assert "TOOLS" in summary
  assert "create_money_from_nothing_tool" in summary


@pytest.mark.asyncio
async def test_execute_help_command_via_main(assistant_plugin, mock_update, mock_context):
  mock_update.message.text = "/assistant help"
  await assistant_plugin.execute(mock_update, mock_context)
  mock_update.message.reply_text.assert_called()


@pytest.mark.asyncio
async def test_execute_status_command_via_main(assistant_plugin, mock_update, mock_context):
  mock_update.message.text = "/assistant status"
  await assistant_plugin.execute(mock_update, mock_context)
  mock_update.message.reply_text.assert_called()


@pytest.mark.asyncio
async def test_execute_with_empty_query(assistant_plugin, mock_update, mock_context):
  mock_update.message.text = "/assistant"
  await assistant_plugin.execute(mock_update, mock_context)
  reply_text = mock_update.message.reply_text.call_args[0][0]
  assert "Assistant help" in reply_text


@pytest.mark.asyncio
async def test_execute_with_blocked_input(assistant_plugin, mock_update, mock_context):
  mock_update.message.text = "/assistant <script>alert('xss')</script>"
  await assistant_plugin.execute(mock_update, mock_context)
  reply_text = mock_update.message.reply_text.call_args[0][0]
  assert "invalid input" in reply_text


@pytest.mark.asyncio
async def test_execute_with_special_commands(assistant_plugin, mock_update, mock_context):
  for cmd in ["help", "tools", "status"]:
    mock_update.message.text = f"/assistant {cmd}"
    await assistant_plugin.execute(mock_update, mock_context)
    mock_update.message.reply_text.assert_called()
    mock_update.message.reply_text.reset_mock()


@pytest.mark.asyncio
async def test_execute_with_empty_text_shows_help(assistant_plugin, mock_update, mock_context):
  mock_update.message.text = "/assistant"
  await assistant_plugin.execute(mock_update, mock_context)
  reply_text = mock_update.message.reply_text.call_args[0][0]
  assert "Assistant help" in reply_text


@pytest.mark.asyncio
async def test_execute_tool_call_failure_handling(assistant_plugin, mock_update, mock_context):
  tool_call = type("ToolCall", (), {})()
  tool_call.function = type("Function", (), {})()
  tool_call.function.name = "create_money_from_nothing_tool"
  tool_call.function.arguments = "{}"
  tool_call.id = "call_id"

  async def fake_get_llm_response(messages, tools=None):
    class Msg:
      content = None
      tool_calls = [tool_call]

    return Msg(), None

  async def fake_execute_tool_call(tool_call, messages):
    return None

  assistant_plugin._get_llm_response = fake_get_llm_response
  assistant_plugin._execute_tool_call = fake_execute_tool_call
  messages = [{"role": "user", "content": "test"}]
  result = await assistant_plugin._handle_llm_conversation(messages)
  assert "failed" in result.lower()


@pytest.mark.asyncio
async def test_execute_tool_call_success_handling(assistant_plugin):
  tool_call = type("ToolCall", (), {})()
  tool_call.function = type("Function", (), {})()
  tool_call.function.name = "create_money_from_nothing_tool"
  tool_call.function.arguments = "{}"
  tool_call.id = "call_id"

  async def fake_call_tool_from_session(server_cfg, tool_name, tool_args):
    return "tool result"

  assistant_plugin.tool_to_server_map = {
    "create_money_from_nothing_tool": {"name": "grocery-shop-mcp-server", "url": "http://test", "auth_value": "token"}
  }
  assistant_plugin.call_tool_from_session = fake_call_tool_from_session

  messages = []
  result = await assistant_plugin._execute_tool_call(tool_call, messages)
  assert result == "continue"
  assert any(m["content"] == "tool result" for m in messages)


@pytest.mark.asyncio
async def test__call_tool_from_session_exception_handling(assistant_plugin):
  async def raise_exception(*args, **kwargs):
    raise Exception("test exception")

  assistant_plugin.call_tool_from_session = raise_exception
  result = await assistant_plugin._handle_mcp_tool(
    "create_money_from_nothing_tool", {}, type("ToolCall", (), {"id": "id"}), []
  )
  assert result is None


@pytest.mark.asyncio
async def test_execute_tool_call_blocked_tool(assistant_plugin):
  tool_call = type("ToolCall", (), {})()
  tool_call.function = type("Function", (), {})()
  tool_call.function.name = "exec_shell"
  tool_call.function.arguments = "{}"
  tool_call.id = "call_id"

  messages = []
  result = await assistant_plugin._execute_tool_call(tool_call, messages)
  assert result is None
  assert any("security error" in m["content"].lower() for m in messages)


@pytest.mark.asyncio
async def test_save_and_get_conversation_history(assistant_plugin, mock_update):
  user_id = mock_update.effective_user.id
  chat_id = mock_update.effective_chat.id
  assistant_plugin.execute_query("DELETE FROM assistant WHERE user_id = ? AND chat_id = ?", (user_id, chat_id))

  for i in range(assistant_plugin.max_history + 1):
    assistant_plugin.save_message(user_id, chat_id, "user", f"message {i}")

  history = assistant_plugin.get_conversation_history(user_id, chat_id)
  assert len(history) == assistant_plugin.max_history
  assert history[0]["content"] == "message 1"


@pytest.mark.asyncio
async def test_handle_llm_conversation_with_no_tool_calls_and_error(assistant_plugin):
  messages = [{"role": "user", "content": "test"}]

  async def fake_get_llm_response(messages, tools=None):
    return None, "llm error: something went wrong"

  assistant_plugin._get_llm_response = fake_get_llm_response
  response = await assistant_plugin._handle_llm_conversation(messages)
  assert "llm error" in response.lower()


@pytest.mark.asyncio
async def test_handle_llm_conversation_max_iterations_reached(assistant_plugin):
  messages = [{"role": "user", "content": "test"}]

  tool_call = type("ToolCall", (), {})()
  tool_call.function = type("Function", (), {})()
  tool_call.function.name = "create_money_from_nothing_tool"
  tool_call.function.arguments = "{}"
  tool_call.id = "call_id"

  async def fake_get_llm_response(messages, tools=None):
    class Msg:
      content = None
      tool_calls = [tool_call]

    return Msg(), None

  assistant_plugin._get_llm_response = fake_get_llm_response
  assistant_plugin._execute_tool_call = AsyncMock(return_value="continue")
  response = await assistant_plugin._handle_llm_conversation(messages)
  assert "max tool call iterations" in response.lower()


@pytest.mark.asyncio
async def test_extract_command_text_various(assistant_plugin):
  assert assistant_plugin._extract_command_text("/assistant ehi I'm here") == "ehi I'm here"
  assert assistant_plugin._extract_command_text("/assistant   hello") == "hello"
  assert assistant_plugin._extract_command_text("/assistant") == ""
  assert assistant_plugin._extract_command_text("please call me") == "please call me"


@pytest.mark.asyncio
async def test_get_special_command_handler(assistant_plugin):
  assert assistant_plugin._get_special_command_handler("help") == assistant_plugin.show_help
  assert assistant_plugin._get_special_command_handler("tools") == assistant_plugin.show_tools
  assert assistant_plugin._get_special_command_handler("tool") == assistant_plugin.show_tools
  assert assistant_plugin._get_special_command_handler("status") == assistant_plugin.show_status
  assert assistant_plugin._get_special_command_handler("unknown") is None


@pytest.mark.asyncio
async def test_handle_resource_tool_no_resource(assistant_plugin):
  tool_call = type("ToolCall", (), {})()
  tool_call.function = type("Function", (), {})()
  tool_call.function.name = "read_resource_unknown"
  tool_call.function.arguments = "{}"
  tool_call.id = "call_id"

  assistant_plugin.tools = []
  messages = []
  result = await assistant_plugin._handle_resource_tool(tool_call.function.name, tool_call, messages)
  assert result == "continue"
  assert any("error" in m["content"].lower() for m in messages)


@pytest.mark.asyncio
async def test_handle_resource_tool_with_resource(assistant_plugin):
  tool_call = type("ToolCall", (), {})()
  tool_call.function = type("Function", (), {})()
  tool_call.function.name = "read_resource_mind"
  tool_call.function.arguments = "{}"
  tool_call.id = "call_id"

  assistant_plugin.tools = [{"type": "function", "function": {"name": "read_resource_mind"}, "_resource_uri": "uri1"}]
  assistant_plugin._read_resource = AsyncMock(return_value="resource content")

  messages = []
  result = await assistant_plugin._handle_resource_tool(tool_call.function.name, tool_call, messages)
  assert result == "continue"
  assert any("resource content" in m["content"] for m in messages)


@pytest.mark.asyncio
async def test_save_message_truncation_and_limit(assistant_plugin, mock_update):
  user_id = mock_update.effective_user.id
  chat_id = mock_update.effective_chat.id
  assistant_plugin.execute_query("DELETE FROM assistant WHERE user_id = ? AND chat_id = ?", (user_id, chat_id))

  long_content = "x" * 3000
  for i in range(assistant_plugin.max_history + 1):
    assistant_plugin.save_message(user_id, chat_id, "user", f"message {i}")
  assistant_plugin.save_message(user_id, chat_id, "assistant", long_content)
  history = assistant_plugin.get_conversation_history(user_id, chat_id)
  assert len(history) == assistant_plugin.max_history
  assert history[0]["content"] == "message 2"
  assert len(history[-1]["content"]) == 2000


@pytest.mark.asyncio
async def test_get_conversation_history_empty_db(assistant_plugin):
  assistant_plugin.db_cursor = None
  history = assistant_plugin.get_conversation_history(1, 1)
  assert history == []


@pytest.mark.asyncio
async def test_log_initialization_warnings(assistant_plugin, caplog):
  caplog.clear()
  plugin = Plugin()
  plugin.initialize()
  assert "no mcp servers configured" in caplog.text
  assert "no model configured" in caplog.text
  assert "no api key configured" in caplog.text


@pytest.mark.asyncio
async def test_validate_update(assistant_plugin):
  mock_update = MagicMock(spec=Update)
  mock_update.effective_chat = None
  assert assistant_plugin._validate_update(mock_update) is False
  mock_update.effective_chat = MagicMock()
  mock_update.message = None
  assert assistant_plugin._validate_update(mock_update) is False
  mock_update.message = MagicMock()
  assert assistant_plugin._validate_update(mock_update) is True
