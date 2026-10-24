import re
from dataclasses import dataclass
from dataclasses import field
from datetime import date
from datetime import datetime
from datetime import time
from datetime import timedelta
from html import escape
from html.parser import HTMLParser
from urllib.parse import urljoin
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import httpx
from telegram import Update
from telegram.ext import ContextTypes
from telegram.ext import JobQueue

from lotb.common.plugin_class import PluginBase


def normalize_venue(url: str) -> str:
  parts = urlsplit(url)
  host = parts.hostname or ""
  if (
    parts.scheme not in ("http", "https")
    or not re.fullmatch(r"(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+18tickets\.it", host)
    or parts.netloc.lower() != host
    or parts.path not in ("", "/")
    or parts.query
    or parts.fragment
  ):
    raise ValueError("Use a cinema homepage URL such as https://nosadella.18tickets.it/")
  return f"https://{host}/"


@dataclass
class Film:
  title: str
  url: str
  showings: list[tuple[datetime, str]] = field(default_factory=list)
  description: str = ""
  year: str = ""
  duration: str = ""
  director: str = ""
  language: str = ""


class ScheduleParser(HTMLParser):
  def __init__(self, venue: str, timezone: ZoneInfo):
    super().__init__()
    self.venue = venue
    self.timezone = timezone
    self.films: list[Film] = []
    self._film: Film | None = None
    self._depth = 0
    self._movie_depth = 0
    self._title: list[str] | None = None

  def handle_starttag(self, tag, attrs):
    attributes = dict(attrs)
    classes = (attributes.get("class") or "").split()
    if tag == "div":
      self._depth += 1
      if "movie" in classes:
        self._film = Film("", "")
        self.films.append(self._film)
        self._movie_depth = self._depth
    if tag != "a" or self._film is None:
      return
    href = urljoin(self.venue, attributes.get("href") or "")
    if "movie__title" in classes:
      if urlsplit(href).hostname != urlsplit(self.venue).hostname:
        raise ValueError("Unexpected cinema film URL")
      normalize_venue(f"{urlsplit(href).scheme}://{urlsplit(href).netloc}/")
      self._film.url = href
      self._title = []
    if attributes.get("data-time") and attributes.get("href"):
      parts = urlsplit(href)
      normalize_venue(f"{parts.scheme}://{parts.netloc}/")
      showing = (datetime.fromtimestamp(int(attributes["data-time"]) / 1000, self.timezone), href)
      if showing not in self._film.showings:
        self._film.showings.append(showing)

  def handle_data(self, data):
    if self._title is not None:
      self._title.append(data)

  def handle_endtag(self, tag):
    if tag == "a" and self._title is not None:
      title = " ".join(" ".join(self._title).split())
      if title and self._film is not None and not self._film.title:
        self._film.title = title
      self._title = None
    if tag == "div":
      if self._depth == self._movie_depth:
        self._film = None
      self._depth -= 1


class FilmDetailsParser(HTMLParser):
  def __init__(self):
    super().__init__()
    self.description = ""
    self.year = ""
    self.duration = ""
    self.director = ""
    self.language = ""
    self._option: list[str] | None = None
    self._plot: list[str] = []
    self._plot_depth = 0

  def handle_starttag(self, tag, attrs):
    attributes = dict(attrs)
    if tag == "meta" and (attributes.get("property") or attributes.get("name")) in (
      "og:description",
      "description",
    ):
      self.description = " ".join((attributes.get("content") or "").split())
    if tag == "p" and {"movie__time", "movie__option"}.intersection((attributes.get("class") or "").split()):
      self._option = []
    if tag == "div":
      if attributes.get("id") == "plotPanel":
        self._plot = []
        self._plot_depth = 1
      elif self._plot_depth:
        self._plot_depth += 1

  def handle_data(self, data):
    if self._option is not None:
      self._option.append(data)
    if self._plot_depth:
      self._plot.append(data)

  def handle_endtag(self, tag):
    if tag == "p" and self._option is not None:
      label, _, value = " ".join(" ".join(self._option).split()).partition(":")
      attribute = {
        "anno": "year",
        "year": "year",
        "durata": "duration",
        "duration": "duration",
        "regia": "director",
        "director": "director",
        "lingua": "language",
        "language": "language",
      }.get(label.strip().lower())
      if attribute and value.strip():
        setattr(self, attribute, value.strip())
      self._option = None
    if tag == "div" and self._plot_depth:
      self._plot_depth -= 1
      if not self._plot_depth:
        plot = " ".join(" ".join(self._plot).split())
        if plot:
          self.description = plot


class Plugin(PluginBase):
  def __init__(self):
    super().__init__("tickets18", "Cinema schedule subscriptions", require_auth=False)

  def initialize(self):
    self.initialize_plugin()
    settings = self.config.get("plugins.tickets18", {})
    self.timezone = ZoneInfo(settings.get("timezone", "Europe/Rome"))
    self.delivery_time = time(hour=int(settings.get("hour", 8)), tzinfo=self.timezone)
    self.create_table("""
      CREATE TABLE IF NOT EXISTS tickets18_subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER NOT NULL,
        venue TEXT NOT NULL,
        weekday TEXT NOT NULL CHECK (weekday IN ('monday', 'friday')),
        UNIQUE (chat_id, venue, weekday)
      )
    """)

  async def fetch_schedule(self, venue: str) -> list[Film]:
    venue = normalize_venue(venue)
    async with httpx.AsyncClient(timeout=30) as client:
      response = await client.get(
        urljoin(venue, "film/fetch_films"),
        params={"date": ""},
        headers={"Accept": "text/javascript", "X-Requested-With": "XMLHttpRequest"},
      )
      response.raise_for_status()
      match = re.search(r"""\$\(["']#movie-list["']\)\.html\('((?:\\.|[^'\\])*)'\);""", response.text)
      if not match:
        raise ValueError("Cinema schedule response was not recognized")
      html = re.sub(
        r"\\(u[0-9a-fA-F]{4}|.)",
        lambda m: chr(int(m[1][1:], 16)) if m[1].startswith("u") else {"n": "\n", "r": "\r", "t": "\t"}.get(m[1], m[1]),
        match[1],
      )
      parser = ScheduleParser(venue, self.timezone)
      parser.feed(html)
      films = parser.films
      if any(not film.title or not film.url for film in films) or ("data-time" in html and not films):
        raise ValueError("Cinema schedule markup was not recognized")
      for film in films:
        film.showings.sort()
        try:
          detail = await client.get(film.url)
          detail.raise_for_status()
          description = FilmDetailsParser()
          description.feed(detail.text)
          film.description = description.description
          film.year = description.year
          film.duration = description.duration
          film.director = description.director
          film.language = description.language
        except httpx.HTTPError as error:
          self.log_warning(f"Could not retrieve description for {film.url}: {error}")
      return films

  async def execute(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_message or not update.effective_chat or not self.db_cursor:
      return
    args = context.args or []
    chat_id = update.effective_chat.id
    if len(args) == 3 and args[0] == "add" and args[2] in ("monday", "friday"):
      try:
        venue = normalize_venue(args[1])
      except ValueError as error:
        await self.reply_message(update, context, str(error))
        return
      self.execute_query(
        "INSERT OR IGNORE INTO tickets18_subscriptions (chat_id, venue, weekday) VALUES (?, ?, ?)",
        (chat_id, venue, args[2]),
      )
      self.db_cursor.execute(
        "SELECT id FROM tickets18_subscriptions WHERE chat_id = ? AND venue = ? AND weekday = ?",
        (chat_id, venue, args[2]),
      )
      subscription_id = self.db_cursor.fetchone()[0]
      await self.reply_message(update, context, f"Subscription {subscription_id}: {venue} ({args[2]})")
    elif args == ["list"]:
      self.db_cursor.execute(
        "SELECT id, venue, weekday FROM tickets18_subscriptions WHERE chat_id = ? ORDER BY id", (chat_id,)
      )
      rows = self.db_cursor.fetchall()
      lines = [f"{subscription_id}: {venue} ({weekday})" for subscription_id, venue, weekday in rows]
      for text in self.split_messages("\n".join(lines) if lines else "No cinema subscriptions in this chat."):
        await self.reply_message(update, context, text)
    elif args == ["now"]:
      await self.send_summaries(context, chat_id=chat_id)
    elif len(args) == 2 and args[0] == "remove" and args[1].isascii() and args[1].isdigit() and len(args[1]) <= 18:
      self.execute_query("DELETE FROM tickets18_subscriptions WHERE id = ? AND chat_id = ?", (int(args[1]), chat_id))
      text = "Subscription removed." if self.db_cursor.rowcount else "Subscription not found in this chat."
      await self.reply_message(update, context, text)
    else:
      await self.reply_message(
        update,
        context,
        "Usage:\n/tickets18 add <cinema URL> monday|friday\n/tickets18 list\n/tickets18 remove <id>\n/tickets18 now",
      )

  def set_job_queue(self, job_queue: JobQueue):
    for weekday, day in (("monday", 1), ("friday", 5)):
      name = f"tickets18_{weekday}"
      for job in job_queue.get_jobs_by_name(name):
        job.schedule_removal()
      job_queue.run_daily(self.send_summaries, time=self.delivery_time, days=(day,), data=weekday, name=name)

  async def send_summaries(self, context: ContextTypes.DEFAULT_TYPE, chat_id: int | None = None):
    if not self.db_cursor or (chat_id is None and not context.job):
      return
    weekday = context.job.data if chat_id is None else "monday"
    today = datetime.now(self.timezone).date()
    monday = today - timedelta(days=today.weekday())
    start = monday if weekday == "monday" else monday + timedelta(days=4)
    end = monday + timedelta(days=6)
    if chat_id is None:
      self.db_cursor.execute(
        "SELECT chat_id, venue FROM tickets18_subscriptions WHERE weekday = ? ORDER BY id", (weekday,)
      )
    else:
      self.db_cursor.execute(
        "SELECT DISTINCT chat_id, venue FROM tickets18_subscriptions WHERE chat_id = ? ORDER BY venue", (chat_id,)
      )
    subscriptions = self.db_cursor.fetchall()
    if chat_id is not None and not subscriptions:
      await context.bot.send_message(
        chat_id=chat_id, text="No cinema subscriptions in this chat. Use /tickets18 add <cinema URL> monday|friday."
      )
    schedules: dict[str, list[Film]] = {}
    for recipient, venue in subscriptions:
      try:
        if venue not in schedules:
          schedules[venue] = await self.fetch_schedule(venue)
        for text in self.format_summary(venue, schedules[venue], start, end):
          await context.bot.send_message(chat_id=recipient, text=text, parse_mode="HTML", disable_web_page_preview=True)
      except Exception as error:
        self.log_error(f"Failed to deliver tickets18 summary for {venue} to {recipient}: {error}")
        if chat_id is not None:
          await context.bot.send_message(
            chat_id=recipient, text=f"Could not retrieve the schedule for {venue}. Try again later."
          )

  def format_summary(self, venue: str, films: list[Film], start: date, end: date) -> list[str]:
    lines = [f"Cinema: {venue}", f"{start:%d/%m/%Y} – {end:%d/%m/%Y}"]
    found = False
    for film in films:
      showings = [when for when, _ in film.showings if start <= when.date() <= end]
      if not showings:
        continue
      found = True
      lines.extend(["", f"<b>{escape(film.title)}</b>"])
      metadata = [
        value
        for value in (
          film.year,
          film.duration,
          f"Director: {film.director}" if film.director else "",
          f"Language: {film.language}" if film.language else "",
        )
        if value
      ]
      if metadata:
        lines.append(escape(" · ".join(metadata)))
      if film.description:
        lines.append(escape(film.description))
      by_date: dict[date, set[str]] = {}
      for when in showings:
        by_date.setdefault(when.date(), set()).add(when.strftime("%H:%M"))
      lines.append("")
      for day, times in sorted(by_date.items()):
        lines.append(f"• <b>{day:%d/%m}</b> — <b>{', '.join(sorted(times))}</b>")
    if not found:
      lines.append("No published showings for this period.")
    return self.split_messages("\n".join(lines))

  def split_messages(self, text: str) -> list[str]:
    messages = []
    remaining = text
    while remaining:
      cut = min(len(remaining), 4000)
      while len(remaining[:cut].encode("utf-16-le")) // 2 > 4000:
        cut -= 1
      if cut < len(remaining):
        newline = remaining.rfind("\n", 0, cut + 1)
        if newline > 0:
          cut = newline
      entity = re.search(r"&[^;\s&]*$", remaining[:cut])
      if entity and entity.start() > 0:
        cut = entity.start()
      messages.append(remaining[:cut])
      remaining = remaining[cut:].lstrip("\n")
    return messages
