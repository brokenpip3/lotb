# How to develop a new plugin

## Disclaimer

These code is free to use, do what you prefer with it, but if you developed a nice plugin or a nice new class method please consider to fork the project and create a PR :)

## Create a new plugin

### Create a new plugin file

Create a new python file in the `lotb/plugins` directory. The file name should be the name of your plugin. For example, if you are creating a plugin named `example`, create a file named `example.py`.

### Import required modules

Import the necessary modules, including the `PluginBase` class from `lotb.common.plugin_class`.

```python
import logging
from telegram import Update
from telegram.ext import ContextTypes
from lotb.common.plugin_class import PluginBase
```

### Define your plugin class

Define a new class that inherits from `PluginBase`. Implement the required methods and any additional functionality your plugin needs.

```python
class Plugin(PluginBase):
    def __init__(self):
        super().__init__("example", "This is an example plugin", require_auth=False)

    def initialize(self):
        # Perform any initialization tasks here
        self.log_info("Example plugin initialized.")

    async def execute(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Handle the command execution here
        await self.reply_message(update, context, "Example plugin executed successfully.")
```

### Implement required methods

Your plugin class must implement the following methods:

- `__init__(self)`: Initialize the plugin with its name, description, and whether it requires authorization.
- `initialize(self)`: Perform any initialization tasks, such as setting up a database or loading configuration.
- `execute(self, update: Update, context: ContextTypes.DEFAULT_TYPE)`: Handle the command execution.

### Use PluginBase methods

The `PluginBase` class provides several useful methods that you can use in your plugin, here some of them:

TDB

### Add plugin to configuration

Add your plugin to the configuration file (`config.toml`) under the `[plugins]` section. For example:

```toml
[plugins.example]
anyconfiguration = value
```

### Load and enable the plugin

Lotb will automatically load and enable the plugin based on the configuration.

## Complete example plugin

```python
from telegram import Update
from telegram.ext import ContextTypes
from lotb.common.plugin_class import PluginBase


class Plugin(PluginBase):
  def __init__(self):
    super().__init__("example", "Example plugin to demonstrate intercept_patterns", require_auth=False)

  def initialize(self):
    self.initialize_plugin()
    self.pattern_actions = {
      r"\bhome\b": self.react_home,
      r"\bwork\b": self.react_work,
      "work": self.react_work,
    }
    self.log_info("Example plugin initialized.")

  async def execute(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await self.intercept_patterns(update, context, self.pattern_actions):
      return

  async def react_home(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    await self.reply_message(update, context, "You mentioned home!")

  async def react_work(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    await self.reply_message(update, context, "You mentioned work!")
```
