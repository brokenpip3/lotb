import json
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import TYPE_CHECKING

from mcp import ClientSession
from pydantic import AnyUrl
from pydantic import parse_obj_as

from .mcp_manager import MCPSessionManager

if TYPE_CHECKING:
  from lotb.common.plugin_class import PluginBase
  from .mcp_manager import MCPManager


class ToolHandler:
  def __init__(self, plugin: "PluginBase", mcp_manager: "MCPManager"):
    self.plugin = plugin
    self.mcp = mcp_manager

  @MCPSessionManager.with_session("reading resource", "")
  async def read_resource_from_session(self, session: ClientSession, server_cfg: Dict[str, Any], uri: str) -> str:
    url_obj = parse_obj_as(AnyUrl, uri)
    result = await session.read_resource(url_obj)

    if hasattr(result, "contents") and result.contents:
      content_parts = []
      for content in result.contents:
        if hasattr(content, "text"):
          content_parts.append(content.text)
        elif hasattr(content, "blob"):
          continue
        else:
          content_parts.append(str(content))
      return "\n".join(content_parts)
    return str(result)

  @MCPSessionManager.with_session("calling tool", "")
  async def call_tool_from_session(
    self, session: ClientSession, server_cfg: Dict[str, Any], tool_name: str, tool_args: Dict[str, Any]
  ) -> str:
    self.plugin.log_info(f"calling tool '{tool_name}' with args: {tool_args}")

    result = await session.call_tool(tool_name, tool_args)

    if hasattr(result, "content"):
      if isinstance(result.content, list) and result.content:
        first_item = result.content[0]
        return getattr(first_item, "text", str(first_item))
      else:
        return getattr(result.content, "text", str(result.content))
    return str(result)

  async def read_resource(self, uri: str) -> str:
    server_cfg = self.mcp.resource_to_server_map.get(uri)
    if not server_cfg:
      return f"error: no server found for resource '{uri}'"

    try:
      return await self.read_resource_from_session(server_cfg, uri)
    except Exception as e:
      self.plugin.log_warning(f"failed to read resource {uri}: {e}")
      return f"error reading resource: {e}"

  async def call_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> str:
    server_cfg = self.mcp.tool_to_server_map.get(tool_name)
    if not server_cfg:
      self.plugin.log_warning(
        f"no server found for tool '{tool_name}'. available: {list(self.mcp.tool_to_server_map.keys())}"
      )
      return f"error: No server found for tool '{tool_name}'"

    try:
      tool_result = await self.call_tool_from_session(server_cfg, tool_name, tool_args)
      self.plugin.log_info(f"tool '{tool_name}' returned: {tool_result[:200]}...")
      return tool_result
    except Exception as e:
      self.plugin.log_warning(f"tool call failed: {e}")
      return f"tool call failed: {e}"

  async def create_resource_tools(self, resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    resource_tools = []

    for resource in resources:
      uri = resource.get("uri", "")
      name = resource.get("name", uri.split("/")[-1] if uri else "unknown")
      description = resource.get("description", f"access resource: {uri}")
      clean_name = name.replace(" ", "_").replace("-", "_").replace(".", "_")

      resource_tools.append(
        {
          "type": "function",
          "function": {
            "name": f"read_resource_{clean_name}",
            "description": f"read resource: {description}",
            "parameters": {"type": "object", "properties": {}, "required": []},
          },
          "_resource_uri": uri,
        }
      )

    return resource_tools

  def find_resource_uri_for_tool(self, tool_name: str, tools: List[Dict[str, Any]]) -> Optional[str]:
    for tool in tools:
      if tool.get("type") == "function" and tool["function"]["name"] == tool_name and "_resource_uri" in tool:
        return tool["_resource_uri"]
    return None

  async def execute_tool_call(
    self, tool_call, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]
  ) -> Optional[str]:
    tool_name = tool_call.function.name
    tool_args_str = tool_call.function.arguments
    self.plugin.log_info(f"attempting to call tool: {tool_name}")

    is_valid, error_msg = self.plugin.security_validator.llm_validate_tool_name(tool_name)
    if not is_valid:
      self.plugin.log_warning(f"tool '{tool_name}' blocked by security: {error_msg}")
      messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": f"security error: {error_msg}"})
      return "failed"

    try:
      tool_args = json.loads(tool_args_str) if isinstance(tool_args_str, str) else tool_args_str
    except json.JSONDecodeError as e:
      self.plugin.log_error(f"failed to parse tool arguments: {e}")
      messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": "error: invalid tool arguments format"})
      return "failed"

    if tool_name.startswith("read_resource_"):
      return await self._handle_resource_tool(tool_name, tool_call, messages, tools)

    return await self._handle_mcp_tool(tool_name, tool_args, tool_call, messages)

  async def _handle_resource_tool(
    self, tool_name: str, tool_call, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]
  ) -> Optional[str]:
    resource_uri = self.find_resource_uri_for_tool(tool_name, tools)
    if not resource_uri:
      content = f"error: resource not found for tool '{tool_name}'"
    else:
      content = await self.read_resource(resource_uri)

    messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": content})
    return "continue"

  async def _handle_mcp_tool(
    self, tool_name: str, tool_args: Dict[str, Any], tool_call, messages: List[Dict[str, Any]]
  ) -> Optional[str]:
    content = await self.call_tool(tool_name, tool_args)
    messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": content})
    return "continue" if not content.startswith("error") else None
