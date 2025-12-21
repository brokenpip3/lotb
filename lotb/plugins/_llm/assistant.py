import re
from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Optional
from typing import TYPE_CHECKING

from telegram import Update
from telegram.ext import ContextTypes

from .history import ConversationHistory
from .mcp_manager import MCPManager
from .prompts import ASSISTANT_DEFAULT_PROMPT
from .prompts import SystemPromptBuilder
from .tool_handler import ToolHandler

if TYPE_CHECKING:
  from lotb.common.plugin_class import PluginBase
  from .config import LLMConfig


class AssistantHandler:
  def __init__(self, plugin: "PluginBase", config: "LLMConfig"):
    self.plugin = plugin
    self.config = config
    self.history = ConversationHistory(plugin, config.max_history)
    self.mcp = MCPManager(plugin, config.mcp_servers)
    self.tool_handler = ToolHandler(plugin, self.mcp)
    self.pattern_actions: Dict[str, Callable] = {}

    system_prompt_template = config.system_prompt or ASSISTANT_DEFAULT_PROMPT
    self.system_prompt_builder = SystemPromptBuilder(system_prompt_template)

    self.tools: Optional[List[Dict[str, Any]]] = None
    self.resources: Optional[List[Dict[str, Any]]] = None
    self.capabilities_summary: Optional[str] = None

  def initialize(self):
    self.history.create_table()

    if self.config.friendly_name:
      trigger_pattern = rf"(?i)\b(?:hey\s+)?{re.escape(self.config.friendly_name)}\b[\s,:!?]*"
      self.pattern_actions = {trigger_pattern: self.handle_trigger}
      self.plugin.log_info(f"Assistant trigger enabled with name: {self.config.friendly_name}")

  async def handle_trigger(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
      return

    if self.config.friendly_name:
      trigger_pattern = rf"(?i)\b(?:hey\s+)?{re.escape(self.config.friendly_name)}\b[\s,:!?]*"
      text = re.sub(trigger_pattern, "", update.message.text, count=1).strip()

      if not text:
        await self.plugin.reply_message(update, context, "yes? 🦕")
      return

    await self.process_query(update, context, text)

  async def _ensure_tools_loaded(self) -> List[Dict[str, Any]]:
    if self.tools is None and self.config.mcp_servers:
      self.plugin.log_info("starting lazy loading of tools and resources")
      regular_tools = await self.mcp.load_all_tools()
      self.plugin.log_info(f"loaded {len(regular_tools)} regular tools")

      if self.resources is None:
        self.resources = await self.mcp.load_all_resources()
        self.plugin.log_info(f"loaded {len(self.resources)} resources")

      resource_tools = await self.tool_handler.create_resource_tools(self.resources)
      self.plugin.log_info(f"created {len(resource_tools)} resource tools")

      self.tools = regular_tools + resource_tools
      self.plugin.log_info("generating capabilities summary...")
      self.capabilities_summary = await self._generate_capabilities_summary()
      self.plugin.log_info(f"capabilities summary generated ({len(self.capabilities_summary)} chars)")
      self.plugin.log_info(f"total tools available: {len(self.tools)}")

      tool_names = [tool["function"]["name"] for tool in self.tools if tool.get("type") == "function"]
      self.plugin.log_info(f"available tool names: {tool_names}")
      self.plugin.log_info(f"tool-to-server mappings: {list(self.mcp.tool_to_server_map.keys())}")
      self.plugin.log_info(f"resource-to-server mappings: {list(self.mcp.resource_to_server_map.keys())}")

    return self.tools or []

  async def _generate_capabilities_summary(self) -> str:
    if not self.tools and not self.resources:
      return "no capabilities available at the moment"

    summary_parts = []

    mcp_tools = []
    for tool in self.tools or []:
      if tool.get("type") == "function" and not tool["function"]["name"].startswith("read_resource_"):
        name = tool["function"]["name"]
        description = tool["function"].get("description", "no description")
        mcp_tools.append(f"  • {name}: {description}")

    if mcp_tools:
      summary_parts.append("TOOLS:\n" + "\n".join(mcp_tools))

    if self.resources:
      resource_list = []
      for r in self.resources:
        name = r.get("name", "Unknown")
        description = r.get("description", "no description")
        resource_list.append(f"  • {name}: {description}")

      summary_parts.append("RESOURCES:\n" + "\n".join(resource_list))

    return "\n\n".join(summary_parts) if summary_parts else "no capabilities available at the moment"

  async def _ensure_system_message(self, messages: List[Dict[str, Any]]):
    system_content = self.system_prompt_builder.with_capabilities(
      self.capabilities_summary or "loading capabilities..."
    ).build()
    if not messages or messages[0].get("role") != "system":
      messages.insert(0, {"role": "system", "content": system_content})
    else:
      messages[0]["content"] = system_content

  async def _get_llm_response(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None):
    kwargs: Dict[str, Any] = {"messages": messages, "model": self.config.model, "api_key": self.config.apikey}
    if tools:
      kwargs["tools"] = tools
    response = await self.plugin.llm_completion(**kwargs)
    if not response.choices or not hasattr(response.choices[0], "message"):
      return None, "llm error: invalid response"

    return response.choices[0].message, None

  async def _handle_llm_conversation(
    self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None
  ) -> str:
    await self._ensure_system_message(messages)

    max_iterations = 3
    iteration = 0

    while iteration < max_iterations:
      iteration += 1
      content, error = await self._get_llm_response(messages, tools)
      if error:
        return error

      if not (hasattr(content, "tool_calls") and content.tool_calls):
        return content.content or ""

      messages.append({"role": "assistant", "content": content.content or "", "tool_calls": content.tool_calls})

      all_successful = True
      for tool_call in content.tool_calls:
        result = await self.tool_handler.execute_tool_call(tool_call, messages, tools or [])
        if result == "failed" or result is None:
          all_successful = False

      if not all_successful:
        return "tool execution failed"

    return "max tool call iterations reached"

  def _get_special_command_handler(self, text: str) -> Optional[Callable]:
    commands = {
      ("tools", "tool"): self.show_tools,
      ("help",): self.show_help,
      ("status",): self.show_status,
    }

    text_lower = text.lower()
    for command_variants, handler in commands.items():
      if text_lower in command_variants:
        return handler
    return None

  async def show_tools(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    tools = await self._ensure_tools_loaded()

    if not tools:
      await self.plugin.reply_message(update, context, "no tools available")
      return

    response = "🛠️Available Tools:\n\n"
    regular_tools = []
    resource_tools = []

    for tool in tools:
      if tool.get("type") == "function":
        name = tool["function"]["name"]
        desc = tool["function"].get("description", "no description")

        if name.startswith("read_resource_"):
          resource_tools.append(f"📖 `{name}`: {desc}")
        else:
          server_name = self.mcp.tool_to_server_map.get(name, {}).get("name", "unknown")
          regular_tools.append(f"⚙️ `{name}` [{server_name}]: {desc}")

    if regular_tools:
      response += "mcp tools:\n" + "\n".join(regular_tools) + "\n\n"

    if resource_tools:
      response += "resource tools:\n" + "\n".join(resource_tools)

    await self.plugin.reply_message(update, context, response)

  async def show_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """🤖 Assistant help

Commands:
• /llm <prompt> - ask something using available tools
• /llm tools - show available mcp tools and resources
• /llm status - show plugin status
• /llm help - show this help
"""
    await self.plugin.reply_message(update, context, help_text)

  async def show_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    tools = await self._ensure_tools_loaded()
    status = f"""🔧 Assistant status

Configuration:
• model: {self.config.model or "❌"}
• api key: {"✅" if self.config.apikey else "❌"}
• servers: {len(self.config.mcp_servers)}

Loaded:
• tools: {len(tools)}
• resources: {len(self.resources or [])}
• server mappings: {len(self.mcp.tool_to_server_map)}

Servers:
{chr(10).join(f"• {s.get('name', 'unknown')}" for s in self.config.mcp_servers) if self.config.mcp_servers else "❌"}
"""
    await self.plugin.reply_message(update, context, status)

  async def process_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    is_valid, error_msg = self.plugin.security_validator.validate_user_input(text)
    if not is_valid:
      self.plugin.log_warning(f"user input blocked: {error_msg}")
      await self.plugin.reply_message(update, context, f"invalid input: {error_msg}")
      return

    if handler := self._get_special_command_handler(text):
      await handler(update, context)
      return

    self.plugin.log_info(f"processing user request: '{text[:50]}...'")

    try:
      user = update.effective_user
      chat = update.effective_chat
      if user and chat:
        user_id = user.id
        chat_id = chat.id
        tools = await self._ensure_tools_loaded()
        self.plugin.log_info(f"using {len(tools)} tools for this request")
        history = self.history.get_conversation_history(user_id, chat_id)
        messages = [*history, {"role": "user", "content": text}]
        await self.plugin.send_typing_action(update, context)
        response = await self._handle_llm_conversation(messages, tools)
        self.plugin.log_info(f"responding with: '{response[:100]}...'")
        self.history.save_message(user_id, chat_id, "user", text)
        self.history.save_message(user_id, chat_id, "assistant", response)
        await self.plugin.reply_message(update, context, response)
    except Exception as e:
      await self.plugin.reply_message(
        update, context, f"sorry, something went wrong while processing your request: {str(e)}"
      )

  async def execute(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await self.plugin.intercept_patterns(update, context, self.pattern_actions):
      return

    if not update or not update.effective_chat or not update.message:
      return

    if not update.message.text:
      await self.show_help(update, context)
      return

    text = update.message.text.replace("/llm", "", 1).strip()
    if not text:
      await self.show_help(update, context)
      return

    await self.process_query(update, context, text)
