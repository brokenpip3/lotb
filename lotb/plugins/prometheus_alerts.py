from collections import defaultdict

import httpx
from telegram import Update
from telegram.ext import ContextTypes
from telegram.ext import JobQueue

from lotb.common.plugin_class import PluginBase


class Plugin(PluginBase):
  def __init__(self):
    super().__init__("prometheus_alerts", "Fetch and send prometheus alerts", require_auth=False)
    self.job_queue = None

  def initialize(self):
    plugin_config = self.config.get(f"plugins.{self.name}", {})
    self.prometheusUrl = plugin_config.get("prometheusUrl")
    self.alert_interval = plugin_config.get("alert_interval", 120)
    self.chat_id = plugin_config.get("chatid")

    if not self.prometheusUrl or not self.chat_id:
      raise ValueError("Prometheus URL and chat ID must be specified in the configuration.")

    self.create_table("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_name TEXT,
            alert_severity TEXT,
            alert_description TEXT,
            alert_labels TEXT,
            alert_hash TEXT UNIQUE,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

    self.log_info(f"Prometheus Alerts plugin initialized with URL: {self.prometheusUrl}")

  def set_job_queue(self, job_queue: JobQueue):
    self.job_queue = job_queue
    self.job_queue.run_repeating(self.fetch_and_store_alerts, interval=self.alert_interval * 60, first=0)
    self.log_info(f"Job queue set to fetch alerts every {self.alert_interval} minutes")

  async def fetch_prometheus_alerts(self):
    async with httpx.AsyncClient() as client:
      response = await client.get(f"{self.prometheusUrl}/api/v2/alerts")
      self.log_info(f"Received response status code: {response.status_code}")
      response.raise_for_status()
      self.log_info(f"Response content: {response.json()}")
      return response.json()

  def store_alerts(self, alerts):
    new_alerts = []
    for alert in alerts:
      self.log_info(alert)
      labels = alert.get("labels", {})
      alert_name = labels.get("alertname", "Unknown")
      alert_severity = labels.get("severity", "Unknown")
      alert_description = alert.get("annotations", {}).get("description", "No description")
      alert_active = alert.get("startsAt", "Unknown")

      alert_hash = hash(f"{alert_name}{alert_severity}{alert_description}{alert_active}{str(labels)}")
      self.log_info(f"Name: {alert_name}, hash: {alert_hash}")

      try:
        cursor = self.connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM alerts WHERE alert_hash = ?", (alert_hash,))
        count = cursor.fetchone()[0]

        if count == 0:
          self.log_info(f"Alert does not exist, storing it with hash: {alert_hash}")
          cursor.execute(
            "INSERT INTO alerts (alert_name, alert_severity, alert_description, alert_labels, alert_hash) VALUES (?, ?, ?, ?, ?)",
            (alert_name, alert_severity, alert_description, str(labels), alert_hash),
          )
          self.connection.commit()
          new_alerts.append(alert)
          self.log_info(f"Stored alert: {alert_name}")
        else:
          self.log_info(f"Alert already exists: {alert_name}")
      except Exception as e:
        self.log_error(f"Error storing alert: {e}")

    return new_alerts

  async def send_alerts(self, context: ContextTypes.DEFAULT_TYPE, alerts):
    if not alerts:
      self.log_info("No new alerts to send.")
      return

    # super ugly way to group alerts by name, severity, and description
    # TODO: refactor this to be less ugly and more readable
    grouped_alerts = defaultdict(list)
    for alert in alerts:
      key = (
        alert.get("labels", {}).get("alertname", "Unknown"),
        alert.get("labels", {}).get("severity", "Unknown"),
        alert.get("annotations", {}).get("description", "No description"),
      )
      grouped_alerts[key].append(alert)

    alert_messages = []
    for (alert_name, severity, description), group in grouped_alerts.items():
      severity_emoji = {"critical": "🚨", "warning": "⚠️", "info": "ℹ️"}.get(severity.lower(), "❓")

      merged_labels = defaultdict(set)
      for alert in group:
        for key, value in alert.get("labels", {}).items():
          if key not in ("alertname", "severity"):
            merged_labels[key].add(value)

      formatted_labels = []
      for key, values in merged_labels.items():
        if len(values) == 1:
          formatted_labels.append(f"  • `{key}`: `{next(iter(values))}`")
        else:
          formatted_labels.append(f"  • `{key}`:")
          for value in values:
            formatted_labels.append(f"    ◦ `{value}`")

      group_message = (
        f"{severity_emoji} *Alert*: `{self.escape_markdown(alert_name)}`\n"
        f"*Severity*: `{self.escape_markdown(severity)}`\n"
        f"*Description*: {self.escape_markdown(description)}\n"
        "*Labels*:\n" + "\n".join(formatted_labels)
      )
      alert_messages.append(group_message)

    message = "\n\n".join(alert_messages)
    await context.bot.send_message(chat_id=self.chat_id, text=message, parse_mode="MarkdownV2")
    self.log_info(f"Sent {len(alert_messages)} grouped alerts to chat ID {self.chat_id}")

  async def fetch_and_store_alerts(self, context: ContextTypes.DEFAULT_TYPE):
    try:
      alerts = await self.fetch_prometheus_alerts()
      self.log_info(f"Fetched alerts: {alerts}")
      self.log_info("1 {alerts}")
      new_alerts = self.store_alerts(alerts)
      self.log_info("2 {new_alerts}")
      await self.send_alerts(context, new_alerts)
    except Exception as e:
      self.log_error(f"Failed to fetch and store alerts: {e}")

  async def execute(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    await self.reply_message(update, context, "The plugin is running in background.")
