from datetime import date
from datetime import datetime
from datetime import timedelta
from html import unescape
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import httpx
import pytest

from lotb.common.config import Config
from lotb.plugins.tickets18 import normalize_venue
from lotb.plugins.tickets18 import Plugin
from lotb.plugins.tickets18 import ScheduleParser

VENUE = "https://example-cinema.18tickets.it/"
SCHEDULE_HTML = """
<div class="movie movie--preview">
  <div><a class="movie__title" href="/film/1001">THE LAST ORBIT</a></div>
  <div><a class="movie__title" href="/film/1001"><img alt="THE LAST ORBIT"></a></div>
  <div class="occupations">
    <a data-time="1792855800000" href="https://cinema.example-cinema.18tickets.it/film/1001/00000000-0000-4000-8000-000000000001#theater-init">17:30</a>
    <a data-time="1792863000000" href="https://cinema.example-cinema.18tickets.it/film/1001/booking-2">19:30</a>
    <a data-time="1792938600000" href="https://cinema.example-cinema.18tickets.it/film/1001/booking-3">15:30</a>
    <a data-time="1792945500000" href="https://cinema.example-cinema.18tickets.it/film/1001/booking-4">17:25</a>
    <a data-time="1792952400000" href="https://cinema.example-cinema.18tickets.it/film/1001/booking-5">19:20</a>
    <a data-time="1793124900000" href="https://cinema.example-cinema.18tickets.it/film/1001/booking-6">19:15</a>
    <a data-time="1793211300000" href="https://cinema.example-cinema.18tickets.it/film/1001/booking-7">19:15</a>
  </div>
</div>
"""
SCHEDULE_JS = '$("#movie-list").html(\'' + SCHEDULE_HTML.replace("\n", "\\n").replace("/", "\\/") + "');"
DESCRIPTION_HTML = '<meta property="og:description" content="A film about justice &amp; freedom.">'


@pytest.fixture
def plugin(tmp_path):
  path = tmp_path / "config.toml"
  path.write_text(f'[core]\ndatabase = "{tmp_path / "tickets.db"}"\n[plugins.tickets18]\nenabled = true\n')
  instance = Plugin()
  instance.set_config(Config(path, env_prefix="TICKETS18_TEST_"))
  instance.initialize()
  yield instance
  instance.connection.close()


@pytest.fixture
def cinema_http(monkeypatch):
  requests = []

  def respond(request):
    requests.append(request)
    if request.url.host == "broken.18tickets.it":
      return httpx.Response(503)
    if request.url.path == "/film/fetch_films":
      assert request.url.params["date"] == ""
      assert request.headers["X-Requested-With"] == "XMLHttpRequest"
      return httpx.Response(200, text=SCHEDULE_JS)
    if request.url.path == "/film/1001":
      return httpx.Response(200, text=DESCRIPTION_HTML)
    return httpx.Response(404)

  client = httpx.AsyncClient
  monkeypatch.setattr(
    "lotb.plugins.tickets18.httpx.AsyncClient",
    lambda **kwargs: client(transport=httpx.MockTransport(respond), **kwargs),
  )
  return requests


@pytest.mark.parametrize("url", [VENUE, "http://example-cinema.18tickets.it", "https://EXAMPLE-CINEMA.18tickets.it/"])
def test_normalize_venue(url):
  assert normalize_venue(url) == VENUE


@pytest.mark.parametrize(
  "url",
  [
    "https://example.com/",
    "https://example-cinema.18tickets.it.example.com/",
    "https://example-cinema.18tickets.it@localhost/",
    "https://example-cinema.18tickets.it:8080/",
    "https://example-cinema.18tickets.it/film/123",
    "https://18tickets.it/",
    "file:///tmp/cinema",
  ],
)
def test_reject_non_venue_urls(url):
  with pytest.raises(ValueError):
    normalize_venue(url)


@pytest.mark.asyncio
async def test_fetch_all_dates_and_descriptions(plugin, cinema_http):
  films = await plugin.fetch_schedule(VENUE)
  assert len(films) == 1
  film = films[0]
  assert film.title == "THE LAST ORBIT"
  assert film.description == "A film about justice & freedom."
  assert film.url == VENUE + "film/1001"
  assert len(film.showings) == 7
  assert film.showings[0][0].isoformat() == "2026-10-24T17:30:00+02:00"
  assert film.showings[2][0].isoformat() == "2026-10-25T15:30:00+01:00"
  assert film.showings[0][1] == (
    "https://cinema.example-cinema.18tickets.it/film/1001/00000000-0000-4000-8000-000000000001#theater-init"
  )
  assert len(cinema_http) == 2


@pytest.mark.asyncio
async def test_schedule_failure_is_not_an_empty_schedule(plugin, monkeypatch):
  client = httpx.AsyncClient
  monkeypatch.setattr(
    "lotb.plugins.tickets18.httpx.AsyncClient",
    lambda **kwargs: client(
      transport=httpx.MockTransport(lambda request: httpx.Response(200, text="login page")), **kwargs
    ),
  )
  with pytest.raises(ValueError):
    await plugin.fetch_schedule(VENUE)


@pytest.mark.asyncio
async def test_add_list_remove_are_chat_scoped(plugin, mock_update, mock_context):
  mock_context.args = ["add", VENUE, "monday"]
  await plugin.execute(mock_update, mock_context)
  await plugin.execute(mock_update, mock_context)
  plugin.db_cursor.execute("SELECT id, chat_id, venue, weekday FROM tickets18_subscriptions")
  rows = plugin.db_cursor.fetchall()
  assert len(rows) == 1
  subscription_id, chat_id, venue, weekday = rows[0]
  assert (chat_id, venue, weekday) == (996699, VENUE, "monday")

  mock_context.args = ["add", "https://other.18tickets.it/", "friday"]
  await plugin.execute(mock_update, mock_context)
  mock_context.args = ["list"]
  await plugin.execute(mock_update, mock_context)
  reply = mock_update.message.reply_text.call_args.args[0]
  assert VENUE in reply and "other.18tickets.it" in reply
  assert "monday" in reply and "friday" in reply

  mock_update.effective_chat.id = 123
  await plugin.execute(mock_update, mock_context)
  assert VENUE not in mock_update.message.reply_text.call_args.args[0]
  mock_context.args = ["remove", str(subscription_id)]
  await plugin.execute(mock_update, mock_context)
  plugin.db_cursor.execute("SELECT COUNT(*) FROM tickets18_subscriptions")
  assert plugin.db_cursor.fetchone()[0] == 2

  mock_update.effective_chat.id = 996699
  await plugin.execute(mock_update, mock_context)
  plugin.db_cursor.execute("SELECT venue FROM tickets18_subscriptions")
  assert plugin.db_cursor.fetchall() == [("https://other.18tickets.it/",)]


@pytest.mark.parametrize("args", [[], ["add"], ["add", VENUE, "sunday"], ["remove", "no"], ["unknown"]])
@pytest.mark.asyncio
async def test_invalid_commands_do_not_modify_subscriptions(plugin, args, mock_update, mock_context):
  mock_context.args = args
  await plugin.execute(mock_update, mock_context)
  mock_update.message.reply_text.assert_awaited_once()
  plugin.db_cursor.execute("SELECT COUNT(*) FROM tickets18_subscriptions")
  assert plugin.db_cursor.fetchone()[0] == 0


@pytest.mark.asyncio
async def test_subscriptions_survive_reinitialization(plugin, mock_update, mock_context):
  mock_context.args = ["add", VENUE, "friday"]
  await plugin.execute(mock_update, mock_context)
  second = Plugin()
  second.set_config(plugin.config)
  try:
    second.initialize()
    second.db_cursor.execute("SELECT venue, weekday FROM tickets18_subscriptions")
    assert second.db_cursor.fetchall() == [(VENUE, "friday")]
  finally:
    second.connection.close()


def test_jobs_use_local_delivery_time_and_correct_weekdays(plugin):
  queue = MagicMock()
  plugin.set_job_queue(queue)
  jobs = [call.kwargs for call in queue.run_daily.call_args_list]
  assert [job["days"] for job in jobs] == [(1,), (5,)]
  assert [job["data"] for job in jobs] == ["monday", "friday"]
  for job in jobs:
    assert job["time"].hour == 8
    assert job["time"].tzinfo == ZoneInfo("Europe/Rome")


@pytest.mark.parametrize(
  ("weekday", "now", "expected", "excluded"),
  [
    (
      "monday",
      "2026-10-19T08:00:00+02:00",
      ["<b>24/10</b> — <b>17:30, 19:30</b>", "<b>25/10</b> — <b>15:30, 17:25, 19:20</b>"],
      ["27/10"],
    ),
    (
      "friday",
      "2026-10-23T08:00:00+02:00",
      ["<b>24/10</b> — <b>17:30, 19:30</b>", "<b>25/10</b> — <b>15:30, 17:25, 19:20</b>"],
      ["27/10"],
    ),
    (
      "monday",
      "2026-10-26T08:00:00+01:00",
      ["<b>27/10</b> — <b>19:15</b>", "<b>28/10</b> — <b>19:15</b>"],
      ["24/10", "25/10"],
    ),
  ],
)
@pytest.mark.asyncio
async def test_delivery_filters_date_window(plugin, cinema_http, weekday, now, expected, excluded, monkeypatch):
  plugin.execute_query(
    "INSERT INTO tickets18_subscriptions (chat_id, venue, weekday) VALUES (?, ?, ?)", (42, VENUE, weekday)
  )
  clock = MagicMock(wraps=datetime)
  clock.now.return_value = datetime.fromisoformat(now)
  monkeypatch.setattr("lotb.plugins.tickets18.datetime", clock)
  context = MagicMock()
  context.job.data = weekday
  context.bot.send_message = AsyncMock()
  await plugin.send_summaries(context)
  messages = context.bot.send_message.call_args_list
  assert messages
  text = "\n".join(call.kwargs["text"] for call in messages)
  assert "<b>THE LAST ORBIT</b>" in text and "justice &amp; freedom" in text
  assert "https://cinema.example-cinema.18tickets.it/" not in text
  assert all(part in text for part in expected)
  assert all(part not in text for part in excluded)
  assert all(call.kwargs["chat_id"] == 42 for call in messages)
  assert all(call.kwargs["parse_mode"] == "HTML" for call in messages)


@pytest.mark.asyncio
async def test_failed_venue_does_not_block_other_chats(plugin, cinema_http):
  for chat, url in [(1, "https://broken.18tickets.it/"), (2, VENUE)]:
    plugin.execute_query(
      "INSERT INTO tickets18_subscriptions (chat_id, venue, weekday) VALUES (?, ?, 'friday')", (chat, url)
    )
  context = MagicMock()
  context.job.data = "friday"
  context.bot.send_message = AsyncMock()
  await plugin.send_summaries(context)
  assert 2 in [call.kwargs["chat_id"] for call in context.bot.send_message.call_args_list]


@pytest.mark.asyncio
async def test_long_summary_preserves_all_showings(plugin, cinema_http):
  films = await plugin.fetch_schedule(VENUE)
  film = films[0]
  film.description = "Description " * 1000
  film.showings = [
    (film.showings[0][0] + timedelta(minutes=index), f"{VENUE}film/1001/booking-{index}") for index in range(300)
  ]
  messages = plugin.format_summary(VENUE, films, date(2026, 10, 19), date(2026, 10, 25))
  assert len(messages) > 1
  assert all(len(text) <= 4000 for text in messages)
  text = "\n".join(messages)
  assert film.description in "".join(messages)
  assert all(when.strftime("%H:%M") in text for when, _ in film.showings)
  assert "booking-" not in text


@pytest.mark.asyncio
async def test_missing_description_keeps_showtimes(plugin, monkeypatch):
  client = httpx.AsyncClient

  def respond(request):
    if request.url.path == "/film/fetch_films":
      return httpx.Response(200, text=SCHEDULE_JS)
    return httpx.Response(503)

  monkeypatch.setattr(
    "lotb.plugins.tickets18.httpx.AsyncClient",
    lambda **kwargs: client(transport=httpx.MockTransport(respond), **kwargs),
  )
  films = await plugin.fetch_schedule(VENUE)
  assert films[0].description == ""
  assert len(films[0].showings) == 7


@pytest.mark.asyncio
async def test_empty_schedule_has_explicit_message(plugin, monkeypatch):
  client = httpx.AsyncClient
  monkeypatch.setattr(
    "lotb.plugins.tickets18.httpx.AsyncClient",
    lambda **kwargs: client(
      transport=httpx.MockTransport(lambda request: httpx.Response(200, text="$(\"#movie-list\").html('');")),
      **kwargs,
    ),
  )
  films = await plugin.fetch_schedule(VENUE)
  messages = plugin.format_summary(VENUE, films, date(2026, 10, 19), date(2026, 10, 25))
  assert len(messages) == 1
  assert "No published showings" in messages[0]


@pytest.mark.asyncio
async def test_shared_venue_fetched_once_and_only_due_subscriptions_sent(plugin, cinema_http):
  plugin.execute_query(
    "INSERT INTO tickets18_subscriptions (chat_id, venue, weekday) VALUES (?, ?, 'friday')", (1, VENUE)
  )
  plugin.execute_query(
    "INSERT INTO tickets18_subscriptions (chat_id, venue, weekday) VALUES (?, ?, 'friday')", (2, VENUE)
  )
  plugin.execute_query(
    "INSERT INTO tickets18_subscriptions (chat_id, venue, weekday) VALUES (?, ?, 'monday')", (3, VENUE)
  )
  context = MagicMock()
  context.job.data = "friday"
  context.bot.send_message = AsyncMock()
  await plugin.send_summaries(context)
  assert [call.kwargs["chat_id"] for call in context.bot.send_message.call_args_list] == [1, 2]
  assert len(cinema_http) == 2


def test_custom_delivery_settings(plugin):
  plugin.config.config["plugins"]["tickets18"].update(hour="10", timezone="UTC")
  plugin.initialize()
  queue = MagicMock()
  plugin.set_job_queue(queue)
  for call in queue.run_daily.call_args_list:
    assert call.kwargs["time"].hour == 10
    assert call.kwargs["time"].tzinfo == ZoneInfo("UTC")


@pytest.mark.parametrize("hour", [-1, 24, "invalid"])
def test_invalid_delivery_hour_rejected(plugin, hour):
  plugin.config.config["plugins"]["tickets18"]["hour"] = hour
  with pytest.raises(ValueError):
    plugin.initialize()


def test_unicode_summary_fits_telegram_limit(plugin):
  text = "🎬" * 5000
  messages = plugin.split_messages(text)
  assert "".join(messages) == text
  assert all(len(message.encode("utf-16-le")) // 2 <= 4000 for message in messages)


@pytest.mark.asyncio
async def test_escaped_title(plugin, monkeypatch):
  payload = SCHEDULE_JS.replace("THE LAST ORBIT", "L\\'ARTE &amp; CINEMA \\u00e8")
  client = httpx.AsyncClient

  def respond(request):
    if request.url.path == "/film/fetch_films":
      return httpx.Response(200, text=payload)
    return httpx.Response(200, text="<html></html>")

  monkeypatch.setattr(
    "lotb.plugins.tickets18.httpx.AsyncClient",
    lambda **kwargs: client(transport=httpx.MockTransport(respond), **kwargs),
  )
  films = await plugin.fetch_schedule(VENUE)
  assert films[0].title == "L'ARTE & CINEMA è"
  assert len(films[0].showings) == 7


def test_parser_separates_films_and_deduplicates_bookings():
  parser = ScheduleParser(VENUE, ZoneInfo("Europe/Rome"))
  parser.feed("""
    <div class="movie movie--preview">
      <div><a class="movie__title" href="/film/1">First film</a></div>
      <div>
        <a data-time="1792855800000" href="/film/1/booking-a">17:30</a>
        <a data-time="1792855800000" href="/film/1/booking-a">17:30</a>
      </div>
    </div>
    <div class="movie movie--preview">
      <div><a class="movie__title" href="/film/2">Second film</a></div>
      <div><a data-time="1792863000000" href="/film/2/booking-b">19:30</a></div>
    </div>
  """)
  assert [film.title for film in parser.films] == ["First film", "Second film"]
  assert [film.url for film in parser.films] == [VENUE + "film/1", VENUE + "film/2"]
  assert parser.films[0].showings == [
    (datetime(2026, 10, 24, 17, 30, tzinfo=ZoneInfo("Europe/Rome")), VENUE + "film/1/booking-a")
  ]
  assert parser.films[1].showings == [
    (datetime(2026, 10, 24, 19, 30, tzinfo=ZoneInfo("Europe/Rome")), VENUE + "film/2/booking-b")
  ]


@pytest.mark.asyncio
async def test_now_sends_current_week_once_per_chat_venue(plugin, cinema_http, mock_update, mock_context, monkeypatch):
  for chat_id, venue, weekday in [
    (996699, VENUE, "monday"),
    (996699, VENUE, "friday"),
    (123, "https://other.18tickets.it/", "monday"),
  ]:
    plugin.execute_query(
      "INSERT INTO tickets18_subscriptions (chat_id, venue, weekday) VALUES (?, ?, ?)", (chat_id, venue, weekday)
    )
  clock = MagicMock(wraps=datetime)
  clock.now.return_value = datetime.fromisoformat("2026-10-24T15:00:00+02:00")
  monkeypatch.setattr("lotb.plugins.tickets18.datetime", clock)
  mock_context.args = ["now"]
  mock_context.job = None
  await plugin.execute(mock_update, mock_context)
  mock_context.bot.send_message.assert_awaited_once()
  call = mock_context.bot.send_message.call_args.kwargs
  assert call["chat_id"] == 996699
  assert "THE LAST ORBIT" in call["text"]
  assert "19/10/2026 – 25/10/2026" in call["text"]
  assert "27/10" not in call["text"]
  assert "other.18tickets.it" not in call["text"]
  assert len(cinema_http) == 2


@pytest.mark.asyncio
async def test_now_without_subscriptions_explains_how_to_add_one(plugin, mock_update, mock_context):
  mock_context.args = ["now"]
  mock_context.job = None
  await plugin.execute(mock_update, mock_context)
  text = mock_context.bot.send_message.call_args.kwargs["text"]
  assert "No cinema subscriptions" in text
  assert "/tickets18 add" in text


@pytest.mark.asyncio
async def test_now_reports_failed_venue_and_continues(plugin, cinema_http, mock_update, mock_context):
  for venue in ["https://broken.18tickets.it/", VENUE]:
    plugin.execute_query(
      "INSERT INTO tickets18_subscriptions (chat_id, venue, weekday) VALUES (?, ?, 'monday')", (996699, venue)
    )
  mock_context.args = ["now"]
  mock_context.job = None
  await plugin.execute(mock_update, mock_context)
  texts = [call.kwargs["text"] for call in mock_context.bot.send_message.call_args_list]
  assert any("Could not retrieve" in text and "broken.18tickets.it" in text for text in texts)
  assert any(VENUE in text and "Could not retrieve" not in text for text in texts)


@pytest.mark.parametrize("edited", [False, True])
@pytest.mark.asyncio
async def test_real_telegram_add_command(plugin, mock_context, monkeypatch, edited):
  from telegram import Chat
  from telegram import Message
  from telegram import MessageEntity
  from telegram import Update
  from telegram.ext import CommandHandler
  from telegram.ext import ExtBot
  from lotb.lotb import handle_command

  bot = MagicMock(spec=ExtBot)
  bot.username = "lotb_test_bot"
  bot.send_message = AsyncMock()
  message = Message(
    message_id=1,
    date=datetime(2026, 10, 24, tzinfo=ZoneInfo("Europe/Rome")),
    chat=Chat(996699, "private"),
    text="/tickets18 add https://example-cinema.18tickets.it monday",
    entities=[MessageEntity(MessageEntity.BOT_COMMAND, 0, 10)],
  )
  message.set_bot(bot)
  update = Update(1, **{"edited_message" if edited else "message": message})
  handler = CommandHandler("tickets18", handle_command)
  check_result = handler.check_update(update)
  assert check_result
  monkeypatch.setattr("lotb.lotb.plugins", {"tickets18": plugin})
  await handler.handle_update(update, MagicMock(), check_result, mock_context)
  plugin.db_cursor.execute("SELECT chat_id, venue, weekday FROM tickets18_subscriptions")
  assert plugin.db_cursor.fetchall() == [(996699, VENUE, "monday")]
  bot.send_message.assert_awaited_once()


def test_summary_highlights_titles_and_times_and_escapes_html(plugin):
  from lotb.plugins.tickets18 import Film

  film = Film(
    "Rock & <Roll>",
    VENUE + "film/1",
    [(datetime(2026, 10, 24, 17, 30, tzinfo=ZoneInfo("Europe/Rome")), VENUE + "film/1?a=1&b=2")],
    "A <story> & friendship.",
  )
  text = "\n".join(plugin.format_summary(VENUE, [film], date(2026, 10, 19), date(2026, 10, 25)))
  assert "<b>Rock &amp; &lt;Roll&gt;</b>" in text
  assert "• <b>24/10</b> — <b>17:30</b>" in text
  assert "A &lt;story&gt; &amp; friendship." in text
  assert "film/1" not in text


def test_premiere_badge_does_not_replace_film_title():
  parser = ScheduleParser(VENUE, ZoneInfo("Europe/Rome"))
  parser.feed("""
    <div class="movie movie--preview">
      <h6><a class="movie__title" href="/film/1002">SECOND DAWN</a></h6>
      <div><a class="movie__title" href="/film/1002"><img alt="SECOND DAWN"></a></div>
      <a class="movie__title" href="/film/1002">ANTEPRIMA</a>
    </div>
  """)
  assert parser.films[0].title == "SECOND DAWN"


@pytest.mark.parametrize("language_label", ["Lingua", "Language"])
@pytest.mark.asyncio
async def test_film_details_include_full_plot_and_metadata(plugin, monkeypatch, language_label):
  client = httpx.AsyncClient
  details = f"""
    <meta property="og:description" content="Short preview...">
    <p class="movie__time">Durata: 112 min</p>
    <p class="movie__option"><strong>Regia:</strong> Alex Example</p>
    <p class="movie__option"><strong>Anno:</strong> 2026</p>
    <p class="movie__option"><strong>{language_label}:</strong> V. O. con sottotitoli in italiano</p>
    <div id="plotPanel"><div class="card-body">The full story &amp; its ending.</div></div>
  """
  monkeypatch.setattr(
    "lotb.plugins.tickets18.httpx.AsyncClient",
    lambda **kwargs: client(
      transport=httpx.MockTransport(
        lambda request: httpx.Response(200, text=SCHEDULE_JS if request.url.path == "/film/fetch_films" else details)
      ),
      **kwargs,
    ),
  )
  film = (await plugin.fetch_schedule(VENUE))[0]
  assert film.description == "The full story & its ending."
  assert (film.year, film.duration, film.director) == ("2026", "112 min", "Alex Example")
  assert film.language == "V. O. con sottotitoli in italiano"
  text = "\n".join(plugin.format_summary(VENUE, [film], date(2026, 10, 19), date(2026, 10, 25)))
  assert "2026 · 112 min · Director: Alex Example · Language: V. O. con sottotitoli in italiano" in text
  assert "• <b>24/10</b> — <b>17:30, 19:30</b>" in text
  assert "• <b>25/10</b> — <b>15:30, 17:25, 19:20</b>" in text


@pytest.mark.asyncio
async def test_full_description_survives_message_splitting_with_html_entities(plugin, cinema_http):
  film = (await plugin.fetch_schedule(VENUE))[0]
  film.description = "A & B < C. " * 1200 + "The complete ending."
  messages = plugin.format_summary(VENUE, [film], date(2026, 10, 19), date(2026, 10, 25))
  assert len(messages) > 1
  assert all(len(message) <= 4000 for message in messages)
  assert film.description in unescape("".join(messages))
  for message in messages:
    assert not message.endswith(("&", "&a", "&am", "&amp", "&l", "&lt"))
