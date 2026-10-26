from datetime import datetime
from datetime import timedelta
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from lotb.plugins.remindme import Plugin


@pytest.fixture
def remindme_plugin(mock_db):
  plugin = Plugin()
  plugin.set_config(MagicMock())
  plugin.log_error = MagicMock()
  plugin.initialize()
  return plugin


@pytest.mark.asyncio
async def test_remindme_minutes(mock_update, mock_context, remindme_plugin):
  mock_update.message.text = "/remindme 5m test"
  mock_update.message.message_id = 14071789
  mock_update.message.reply_to_message = MagicMock(text="I need to reply to this not important message", message_id=10)
  mock_update.effective_user.username = "random-unique-user"

  with patch("lotb.plugins.remindme.datetime") as mock_datetime:
    mock_datetime.now.return_value = datetime(2025, 1, 1, 12, 0)
    await remindme_plugin.execute(mock_update, mock_context)

  assert mock_context.job_queue.run_once.call_args[1]["name"] == "reminder_14071789"
  assert mock_context.job_queue.run_once.call_args[1]["data"]["requester_username"] == "random-unique-user"
  mock_update.message.reply_text.assert_called_once_with("reminder set for 5m from now (2025-01-01 12:05)")


@pytest.mark.asyncio
async def test_remindme_days(mock_update, mock_context, remindme_plugin):
  mock_update.message.text = "/remindme 2d"
  mock_update.message.reply_to_message = MagicMock(text="I need to reply to this not important message", message_id=10)

  with patch("lotb.plugins.remindme.datetime") as mock_datetime:
    mock_datetime.now.return_value = datetime(2025, 1, 1)
    await remindme_plugin.execute(mock_update, mock_context)

  assert mock_context.job_queue.run_once.call_args[0][1] == timedelta(days=2)


@pytest.mark.asyncio
async def test_remindme_invalid_format(mock_update, mock_context, remindme_plugin):
  mock_update.message.reply_to_message = MagicMock(text="I need to reply to this not important message", message_id=10)
  mock_update.message.text = "/remindme invalid"

  await remindme_plugin.execute(mock_update, mock_context)

  mock_update.message.reply_text.assert_called_once_with(
    "invalid format. Use: /remindme <time><unit> [optional note]\nunits: m=minutes, h=hours, d=days, w=weeks, M=months, y=years"
  )


@pytest.mark.asyncio
async def test_remindme_no_reply(mock_update, mock_context, remindme_plugin):
  mock_update.message.text = "/remindme 5m"
  mock_update.message.reply_to_message = None
  await remindme_plugin.execute(mock_update, mock_context)
  mock_update.message.reply_text.assert_called_once_with("you need to reply to a message to set a reminder")


@pytest.mark.asyncio
async def test_send_reminder(mock_context, remindme_plugin, mock_update):
  class SimpleJob:
    def __init__(self):
      self.chat_id = mock_update.effective_chat.id
      self.data = {
        "message": "This is not a test, I repeat: this is not a test",
        "original_message_id": 2424,
        "requester_username": "random-unique-user",
      }

  context = mock_context
  context.job = SimpleJob()

  await remindme_plugin._send_reminder(context)

  mock_context.bot.send_message.assert_called_once_with(
    chat_id=996699,
    text="⏰ reminder for @random-unique-user: This is not a test, I repeat: this is not a test",
    reply_to_message_id=2424,
  )


@pytest.mark.asyncio
async def test_send_reminder_with_user_id(mock_context, remindme_plugin, mock_update):
  class SimpleJob:
    def __init__(self):
      self.chat_id = mock_update.effective_chat.id
      self.data = {
        "message": "This is not a test, I repeat: this is not a test",
        "original_message_id": 10,
        "requester_username": "4815162342",
      }

  context = mock_context
  context.job = SimpleJob()

  await remindme_plugin._send_reminder(context)

  mock_context.bot.send_message.assert_called_once_with(
    chat_id=996699,
    text="⏰ reminder for 4815162342: This is not a test, I repeat: this is not a test",
    reply_to_message_id=10,
  )


@pytest.mark.asyncio
async def test_set_job_queue(mock_db, remindme_plugin):
  job_queue = MagicMock()
  mock_cursor = mock_db.mock_cursor
  mock_cursor.fetchall.return_value = [
    (1, 1045, 67890, "Test message", "2025-01-01 12:05:00", 10, "random-unique-user")
  ]
  remindme_plugin.db_cursor = mock_cursor

  with patch("lotb.plugins.remindme.datetime") as mock_datetime:
    mock_datetime.now.return_value = datetime(2025, 1, 1)
    mock_datetime.fromisoformat.side_effect = datetime.fromisoformat
    remindme_plugin.set_job_queue(job_queue)

  job_queue.run_once.assert_called_once()
  assert job_queue.run_once.call_args[1]["name"] == "reminder_10"
  assert job_queue.run_once.call_args[1]["data"]["requester_username"] == "random-unique-user"


@pytest.mark.asyncio
async def test_remindme_invalid_unit(mock_update, mock_context, remindme_plugin):
  mock_update.message.text = "/remindme 5x test"
  mock_update.message.reply_to_message = MagicMock(text="this message maybe exist in another timeline", message_id=10)

  await remindme_plugin.execute(mock_update, mock_context)
  mock_update.message.reply_text.assert_called_once_with(
    "invalid format. Use: /remindme <time><unit> [optional note]\n"
    "units: m=minutes, h=hours, d=days, w=weeks, M=months, y=years"
  )


@pytest.mark.asyncio
async def test_send_reminder_invalid_job_data(mock_context, remindme_plugin):
  class InvalidJob:
    def __init__(self):
      self.chat_id = None
      self.data = "invalid"

  context = mock_context
  context.job = InvalidJob()

  await remindme_plugin._send_reminder(context)
  remindme_plugin.log_error.assert_called_once_with("invalid job data format")


@pytest.mark.asyncio
async def test_send_reminder_missing_chat_id(mock_context, remindme_plugin):
  class NoChatJob:
    def __init__(self):
      self.data = {"message": "test", "original_message_id": 14711789, "requester_username": "another random user"}

  context = mock_context
  context.job = NoChatJob()

  await remindme_plugin._send_reminder(context)
  remindme_plugin.log_error.assert_called_once_with("missing chat_id in job, this should not happen")


@pytest.mark.asyncio
async def test_send_reminder_database_error(mock_context, remindme_plugin, mock_db):
  class SimpleJob:
    def __init__(self):
      self.chat_id = 123
      self.data = {"message": "test", "original_message_id": 14071789, "requester_username": "another random user"}

  mock_db.execute.side_effect = Exception("DB error")
  context = mock_context
  context.job = SimpleJob()

  await remindme_plugin._send_reminder(context)
  remindme_plugin.log_error.assert_called_with("failed to send reminder: DB error")


@pytest.mark.asyncio
async def test_set_job_queue_database_error(remindme_plugin, mock_db):
  mock_db.execute.side_effect = Exception("DB error")
  job_queue = MagicMock()

  remindme_plugin.set_job_queue(job_queue)
  remindme_plugin.log_error.assert_called_once_with("no database available")


@pytest.mark.asyncio
async def test_remindme_database_error(mock_update, mock_context, remindme_plugin, mock_db):
  mock_update.message.text = "/remindme 5m test"
  mock_update.message.reply_to_message = MagicMock(text="this message maybe exist in another timeline", message_id=10)
  mock_db.execute.side_effect = Exception("DB error")

  await remindme_plugin.execute(mock_update, mock_context)
  remindme_plugin.log_error.assert_called_once_with("failed to set reminder: DB error")


@pytest.mark.asyncio
@pytest.mark.parametrize("prefix", ["/", "!"])
async def test_reminder_explicit_text_without_reply(prefix, mock_update, mock_context, remindme_plugin):
  mock_update.message.text = f"{prefix}remindme 10m Check the oven"
  await remindme_plugin.execute(mock_update, mock_context)
  job = mock_context.job_queue.run_once.call_args
  assert job.kwargs["data"]["message"] == "Check the oven"
  assert job.kwargs["data"]["original_message_id"] == mock_update.message.message_id


@pytest.mark.asyncio
async def test_reminder_missing_scheduler(mock_update, mock_context, remindme_plugin):
  mock_context.job_queue = None
  remindme_plugin.db_cursor.execute.reset_mock()
  result = await remindme_plugin.create_reminder(mock_update, mock_context, 10, "m", "Check oven")
  assert not result.ok
  remindme_plugin.db_cursor.execute.assert_not_called()


@pytest.mark.asyncio
async def test_reminder_scheduling_failure_rolls_back(mock_update, mock_context):
  mock_update.message.message_id = 42
  mock_update.effective_user.username = "tester"
  plugin = Plugin()
  config = MagicMock()
  config.get.side_effect = lambda key, default=None: {"core.database": ":memory:"}.get(key, default)
  plugin.set_config(config)
  plugin.initialize()
  mock_context.job_queue.run_once.side_effect = RuntimeError("scheduler failed")
  result = await plugin.create_reminder(mock_update, mock_context, 10, "m", "Check oven")
  assert not result.ok
  assert plugin.db_cursor.execute("SELECT COUNT(*) FROM reminders").fetchone()[0] == 0


@pytest.mark.asyncio
async def test_reminder_restores_fractional_timestamp(mock_update, mock_context):
  mock_update.message.message_id = 42
  mock_update.effective_user.username = "tester"
  plugin = Plugin()
  config = MagicMock()
  config.get.side_effect = lambda key, default=None: {"core.database": ":memory:"}.get(key, default)
  plugin.set_config(config)
  plugin.initialize()
  result = await plugin.create_reminder(mock_update, mock_context, 10, "m", "Check oven")
  assert result.ok
  queue = MagicMock()
  plugin.set_job_queue(queue)
  queue.run_once.assert_called_once()


@pytest.mark.asyncio
async def test_same_text_reminders_keep_independent_persistence(mock_update, mock_context):
  from types import SimpleNamespace

  plugin = Plugin()
  config = MagicMock()
  config.get.side_effect = lambda key, default=None: {"core.database": ":memory:"}.get(key, default)
  plugin.set_config(config)
  plugin.initialize()
  mock_update.message.message_id = 42
  mock_update.effective_user.username = "tester"
  assert (await plugin.create_reminder(mock_update, mock_context, 10, "m", "Check oven")).ok
  first = mock_context.job_queue.run_once.call_args.kwargs
  assert (await plugin.create_reminder(mock_update, mock_context, 20, "m", "Check oven")).ok
  mock_context.job = SimpleNamespace(chat_id=first["chat_id"], user_id=first["user_id"], data=first["data"])
  await plugin._send_reminder(mock_context)
  assert plugin.db_cursor.execute("SELECT COUNT(*) FROM reminders").fetchone()[0] == 1
  queue = MagicMock()
  plugin.set_job_queue(queue)
  queue.run_once.assert_called_once()
  assert "reminder_id" in queue.run_once.call_args.kwargs["data"]


@pytest.mark.asyncio
async def test_reminder_commit_failure_cancels_job(mock_update, mock_context):
  plugin = Plugin()
  config = MagicMock()
  config.get.side_effect = lambda key, default=None: {"core.database": ":memory:"}.get(key, default)
  plugin.set_config(config)
  plugin.initialize()
  mock_update.message.message_id = 42
  mock_update.effective_user.username = "tester"
  connection = plugin.connection
  plugin.connection = MagicMock(wraps=connection)
  plugin.connection.commit.side_effect = RuntimeError("Commit failed")
  result = await plugin.create_reminder(mock_update, mock_context, 10, "m", "Check oven")
  assert not result.ok
  mock_context.job_queue.run_once.return_value.schedule_removal.assert_called_once()
  assert plugin.db_cursor.execute("SELECT COUNT(*) FROM reminders").fetchone()[0] == 0
