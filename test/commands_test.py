import pytest

from lotb.common.commands import command_arguments
from lotb.common.commands import parse_command


@pytest.mark.parametrize("prefix", ["/", "!"])
def test_command_parsing_preserves_arguments(prefix):
  text = f"{prefix}notes add Buy  coffee\nTomorrow"
  assert parse_command(text) == ("notes", ["add", "Buy", "coffee", "Tomorrow"])
  assert command_arguments(text) == "add Buy  coffee\nTomorrow"


@pytest.mark.parametrize("text", ["Hello !image cats", "!img@bot cats", "!!image cats", "!", " !image cats"])
def test_non_commands(text):
  assert parse_command(text) is None
