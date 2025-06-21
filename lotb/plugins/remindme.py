import re
from datetime import datetime
from datetime import timedelta
from typing import Dict

from telegram import Update
from telegram.ext import ContextTypes
from telegram.ext import JobQueue

from lotb.common.plugin_class import PluginBase


class Plugin(PluginBase):
  def __init__(self):
    super().__init__(
      "remindme",
      "set reminders with /remindme <time> <message> (example: '5d' for 5 days)\n you can use m,h,d,w,M,y",
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

  async def execute(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat or not update.effective_user:
      await self.reply_message(
        update, context, "can't set reminder: missing message or chat info, this should not happen"
      )
      return

    if not update.message.reply_to_message:
      await self.reply_message(update, context, "you need to reply to a message to set a reminder")
      return

    text = update.message.text or ""
    match = re.match(r"/remindme\s+(\d+)([mhdwMy])\s*(.*)", text)
    if not match:
      await self.reply_message(
        update,
        context,
        "invalid format. Use: /remindme <time><unit> [optional note]\n"
        "units: m=minutes, h=hours, d=days, w=weeks, M=months, y=years",
      )
      return

    amount, unit, note = match.groups()
    if unit not in ["m", "h", "d", "w", "M", "y"]:
      await self.reply_message(update, context, f"invalid time unit: {unit}")
      return

    try:
      amount = int(amount)
      delta = self._get_time_delta(amount, unit)
      remind_at = datetime.now() + delta
    except (ValueError, KeyError):
      await self.reply_message(
        update,
        context,
        "invalid format. Use: /remindme <time><unit> [optional note]\n"
        "units: m=minutes, h=hours, d=days, w=weeks, M=months, y=years",
      )
      return
    message = note if note else update.message.reply_to_message.text or ""

    try:
      self.execute_query(
        "INSERT INTO reminders (chat_id, user_id, message, remind_at, original_message_id, requester_username) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
          update.effective_chat.id,
          update.effective_user.id,
          message,
          remind_at,
          update.message.reply_to_message.message_id,
          update.effective_user.username or str(update.effective_user.id),
        ),
      )
    except Exception as e:
      self.log_error(f"failed to set reminder: {e}")
      await self.reply_message(update, context, "failed to set reminder due to database error")
      return

    await self.reply_message(
      update, context, f"reminder set for {amount}{unit} from now ({remind_at.strftime('%Y-%m-%d %H:%M')})"
    )

    if context and context.job_queue:
      job_name = f"reminder_{update.message.message_id}"
      context.job_queue.run_once(  # type: ignore
        self._send_reminder,
        delta,
        name=job_name,
        chat_id=update.effective_chat.id,
        user_id=update.effective_user.id,
        data={
          "message": message,
          "original_message_id": update.message.reply_to_message.message_id,
          "requester_username": update.effective_user.username or str(update.effective_user.id),
        },
      )

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
        "SELECT chat_id, user_id, message, remind_at, original_message_id, requester_username FROM reminders "
        "WHERE remind_at > datetime('now')"
      )
      results = self.db_cursor.fetchall()
      if not results:
        return

      for row in results:
        chat_id, user_id, message, remind_at, original_message_id, requester_username = row
        delta = datetime.strptime(remind_at, "%Y-%m-%d %H:%M:%S") - datetime.now()
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
            },
          )
    except Exception:
      self.log_error("no database available")
      return
