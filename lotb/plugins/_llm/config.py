from typing import Any
from typing import Dict
from typing import List


class LLMConfig:
  def __init__(self, config_dict: Dict[str, Any]):
    plugin_cfg = config_dict.get("plugins.llm", {}) if config_dict else {}
    self.apikey = plugin_cfg.get("apikey")
    self.model = plugin_cfg.get("model")
    self.max_history = plugin_cfg.get("maxhistory", 3)
    self.assistant_mode = plugin_cfg.get("assistant_mode", False)
    self.friendly_name = plugin_cfg.get("friendlyname")
    self.system_prompt = plugin_cfg.get("system_prompt")
    self.mcp_servers = plugin_cfg.get("mcpservers", [])

  def validate(self) -> List[str]:
    warnings = []

    if not self.apikey:
      warnings.append("missing api key in configuration")
    if not self.model:
      warnings.append("missing model in configuration")

    if self.assistant_mode:
      if not self.mcp_servers:
        warnings.append("Assistant mode enabled but no MCP servers configured")
      else:
        for server in self.mcp_servers:
          if not server.get("name"):
            warnings.append("MCP server missing name field")
          if not server.get("url"):
            warnings.append(f"MCP server '{server.get('name', 'unknown')}' missing url field")

    return warnings

  def get_info(self) -> str:
    mode = "assistant" if self.assistant_mode else "simple"
    server_count = len(self.mcp_servers) if self.assistant_mode else 0
    trigger = f" (trigger: {self.friendly_name})" if self.friendly_name else ""
    return f"LLM plugin initialized in {mode} mode with {self.max_history} message memory{trigger}, {server_count} MCP servers"
