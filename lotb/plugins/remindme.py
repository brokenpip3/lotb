import re
from datetime import datetime
from datetime import timedelta
from typing import Dict

from telegram import Update
from telegram.ext import ContextTypes
from telegram.ext import JobQueue

from lotb.common.plugin_class import PluginBase
from lotb.common.tools import plugin_tool
from lotb.common.tools import ToolResult


class Plugin(PluginBase):
  def __init__(self):
    super().__init__(
      "remindme",
      "set reminders with /remindme <delay> <message> or /remindme YYYY-MM-DD [HH:MM] <message> (default 09:00, server local time)",
      require_auth=False,
    )

  def initialize(self):
    self.initialize_plugin()
    self.create_table("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                message TEXT NOT NULL,
                remind_at TIMESTAMP NOT NULL,
                original_message_id INTEGER NOT NULL,
                requester_username TEXT NOT NULL
            )
        """)
    self.execute_query("CREATE INDEX IF NOT EXISTS reminders_chat_id_index ON reminders (chat_id)")
    self.execute_query("CREATE INDEX IF NOT EXISTS reminders_remind_at_index ON reminders (remind_at)")
    self.log_info("Remindme plugin initialized")

  def get_tools(self):
    absolute_tool = plugin_tool(
      "lotb_remindme_create_at",
      "Create a reminder on YYYY-MM-DD in server local time, default 09:00. Call lotb_remindme_current_time first to resolve relative dates. Past or invalid dates are rejected.",
      {
        "date": {"type": "string", "description": "YYYY-MM-DD"},
        "message": {"type": "string", "minLength": 1},
        "time": {"type": "string", "description": "HH:MM, defaults to 09:00"},
      },
      self.create_reminder_at,
    )
    absolute_tool.parameters["required"] = ["date", "message"]
    return [
      plugin_tool(
        "lotb_remindme_current_time",
        "Get the current date, HH:MM, and server timezone. Use before calculating reminder dates or delays.",
        {},
        self.current_datetime,
      ),
      absolute_tool,
      plugin_tool(
        "lotb_remindme_create",
        "Create a reminder after a delay; months and years mean 30 and 365 days. Call lotb_remindme_current_time first when calculating a delay from a calendar date.",
        {
          "amount": {"type": "integer", "minimum": 1},
          "unit": {"type": "string", "enum": ["m", "h", "d", "w", "M", "y"]},
          "message": {"type": "string", "minLength": 1},
        },
        self.create_reminder,
      ),
    ]

  async def execute(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat or not update.effective_user:
      await self.reply_message(
        update, context, "can't set reminder: missing message or chat info, this should not happen"
      )
      return
    arguments = self.command_arguments(update).strip()
    absolute = re.fullmatch(r"(\d{4}-\d{2}-\d{2})(?:\s+(\d{1,2}:\S+))?(?:\s+(.*))?", arguments, re.DOTALL)
    if absolute:
      date, time, note = absolute.groups()
      reply = update.message.reply_to_message
      message = note or (reply.text if reply else "") or ""
      if not message:
        await self.reply_message(update, context, "you need to reply to a message to set a reminder")
        return
      result = await self.create_reminder_at(update, context, date, message, time or "09:00")
      await self.reply_message(
        update, context, result.data["message"] if result.ok else result.error or "failed to set reminder"
      )
      return
    match = re.fullmatch(r"(\d+)([mhdwMy])(?:\s+(.*))?", self.command_arguments(update).strip(), re.DOTALL)
    if not match:
      await self.reply_message(
        update,
        context,
        "invalid format. Use: /remindme <time><unit> [optional note] or /remindme YYYY-MM-DD [HH:MM] [optional note] (default 09:00, server local time)\nunits: m=minutes, h=hours, d=days, w=weeks, M=months, y=years",
      )
      return
    amount, unit, note = match.groups()
    reply = update.message.reply_to_message
    message = note or (reply.text if reply else "") or ""
    if not message:
      await self.reply_message(update, context, "you need to reply to a message to set a reminder")
      return
    result = await self.create_reminder(update, context, int(amount), unit, message)
    await self.reply_message(
      update, context, result.data["message"] if result.ok else result.error or "failed to set reminder"
    )

  async def current_datetime(self, update, context) -> ToolResult:
    now = datetime.now().astimezone()
    return ToolResult(
      True, {"datetime": now.strftime("%Y-%m-%d %H:%M"), "timezone": now.tzname(), "utc_offset": now.strftime("%z")}
    )

  async def create_reminder_at(self, update, context, date: str, message: str, time: str = "09:00") -> ToolResult:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date) or not re.fullmatch(r"\d{2}:\d{2}", time):
      return ToolResult(False, {}, "invalid date or time. Use YYYY-MM-DD [HH:MM] (default 09:00, server local time)")
    try:
      remind_at = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
    except ValueError:
      return ToolResult(False, {}, "invalid date or time. Use a real calendar date and HH:MM")
    return await self.create_reminder(update, context, 1, "m", message, remind_at=remind_at)

  async def create_reminder(
    self, update, context, amount: int, unit: str, message: str, *, remind_at: datetime | None = None
  ) -> ToolResult:
    if not update.message or not update.effective_chat or not update.effective_user:
      return ToolResult(False, {}, "Missing message, user or chat information")
    if not context.job_queue:
      return ToolResult(False, {}, "Reminder scheduler is unavailable")
    if type(amount) is not int or amount <= 0 or unit not in ["m", "h", "d", "w", "M", "y"] or not message.strip():
      return ToolResult(False, {}, "Invalid reminder duration or message")
    if self.db_cursor is None or self.connection is None:
      return ToolResult(False, {}, "Reminder database is unavailable")
    absolute = remind_at is not None
    now = datetime.now()
    try:
      delta = remind_at - now if remind_at is not None else self._get_time_delta(amount, unit)
      remind_at = remind_at if remind_at is not None else now + delta
    except (OverflowError, ValueError):
      return ToolResult(False, {}, "invalid reminder date or duration: out of range")
    if delta.total_seconds() <= 0:
      return ToolResult(False, {}, "reminder date and time must be in the future (server local time)")
    job = None
    try:
      original = update.message.reply_to_message or update.message
      username = update.effective_user.username or str(update.effective_user.id)
      self.db_cursor.execute(
        "INSERT INTO reminders (chat_id, user_id, message, remind_at, original_message_id, requester_username) VALUES (?, ?, ?, ?, ?, ?)",
        (
          update.effective_chat.id,
          update.effective_user.id,
          message,
          remind_at.isoformat(sep=" "),
          original.message_id,
          username,
        ),
      )
      reminder_id = self.db_cursor.lastrowid
      job = context.job_queue.run_once(
        self._send_reminder,
        delta,
        name=f"reminder_{update.message.message_id}",
        chat_id=update.effective_chat.id,
        user_id=update.effective_user.id,
        data={
          "message": message,
          "original_message_id": original.message_id,
          "requester_username": username,
          "reminder_id": reminder_id,
        },
      )
      self.connection.commit()
      return ToolResult(
        True,
        {
          "message": (
            f"reminder set for {remind_at:%Y-%m-%d %H:%M} (server local time)"
            if absolute
            else f"reminder set for {amount}{unit} from now ({remind_at:%Y-%m-%d %H:%M})"
          ),
          "remind_at": remind_at.isoformat(),
        },
      )
    except Exception as error:
      self.connection.rollback()
      if job is not None:
        job.schedule_removal()
      self.log_error(f"failed to set reminder: {error}")
      return ToolResult(False, {}, "failed to set reminder due to database or scheduling error")

  def _get_time_delta(self, amount: int, unit: str) -> timedelta:
    unit_map: Dict[str, timedelta] = {
      "m": timedelta(minutes=amount),
      "h": timedelta(hours=amount),
      "d": timedelta(days=amount),
      "w": timedelta(weeks=amount),
      "M": timedelta(days=30 * amount),
      "y": timedelta(days=365 * amount),
    }
    return unit_map[unit]  # Will raise KeyError for invalid units

  async def _send_reminder(self, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.job:
      self.log_error("failed to send reminder: no job context")
      return

    job = context.job
    try:
      if not hasattr(job, "data") or not isinstance(job.data, dict):
        self.log_error("invalid job data format")
        return

      requester = job.data.get("requester_username", "")
      if not requester.startswith("@") and not requester.isdigit():
        requester = f"@{requester}"

      if not hasattr(job, "chat_id"):
        self.log_error("missing chat_id in job, this should not happen")
        return

      if job.chat_id is not None:
        await context.bot.send_message(
          chat_id=job.chat_id,
          text=f"⏰ reminder for {requester}: {job.data.get('message', '')}",
          reply_to_message_id=job.data.get("original_message_id", 0),
        )

      if self.db_cursor:
        if reminder_id := job.data.get("reminder_id"):
          self.execute_query("DELETE FROM reminders WHERE id = ?", (reminder_id,))
        else:
          self.execute_query(
            "DELETE FROM reminders WHERE chat_id = ? AND user_id = ? AND message = ?",
            (job.chat_id, getattr(job, "user_id", 0), job.data.get("message", "")),
          )
    except Exception as e:
      self.log_error(f"failed to send reminder: {e}")

  def set_job_queue(self, job_queue: JobQueue) -> None:
    if not self.db_cursor:
      self.log_error("no database available")
      return

    try:
      self.db_cursor.execute(
        "SELECT id, chat_id, user_id, message, remind_at, original_message_id, requester_username FROM reminders "
        "WHERE remind_at > datetime('now')"
      )
      results = self.db_cursor.fetchall()
      if not results:
        return

      for row in results:
        reminder_id, chat_id, user_id, message, remind_at, original_message_id, requester_username = row
        delta = datetime.fromisoformat(remind_at) - datetime.now()
        if delta.total_seconds() > 0:
          job_queue.run_once(
            self._send_reminder,
            delta,
            chat_id=chat_id,
            user_id=user_id,
            name=f"reminder_{original_message_id}",
            data={
              "message": message,
              "original_message_id": original_message_id,
              "requester_username": requester_username,
              "reminder_id": reminder_id,
            },
          )
    except Exception:
      self.log_error("no database available")
      return
