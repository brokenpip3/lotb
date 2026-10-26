import re


def parse_command(text: str) -> tuple[str, list[str]] | None:
  match = re.match(r"^([/!])([a-z][a-z0-9_]*)(?:@([a-zA-Z0-9_]+))?(?:\s+(.*))?$", text, re.DOTALL)
  if not match or (match[1] == "!" and match[3]):
    return None
  return match[2], (match[4] or "").split()


def command_arguments(text: str) -> str:
  parts = text.split(maxsplit=1)
  return parts[1] if len(parts) == 2 else ""
