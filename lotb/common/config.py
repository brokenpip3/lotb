import os
import tomllib


class Config:
  def __init__(self, config_file="config.toml", env_prefix="LOTB_"):
    self.env_prefix = env_prefix
    self.config = self.load_config(config_file)

  def load_config(self, config_file):
    if os.path.exists(config_file):
      with open(config_file, "rb") as f:
        config = tomllib.load(f)
    else:
      config = {}

    for env_key, env_value in os.environ.items():
      if env_key.startswith(self.env_prefix):
        stripped_key = env_key[len(self.env_prefix) :].lower()
        key_path = stripped_key.replace("_", ".")
        self.set_config_value(config, key_path, env_value)

    return config

  def set_config_value(self, config_dict, key_path, value):
    keys = key_path.split(".")
    d = config_dict
    for key in keys[:-1]:
      if key not in d or not isinstance(d[key], dict):
        d[key] = {}
      d = d[key]
    d[keys[-1]] = value

  def get(self, key, default=None):
    keys = key.split(".")
    value = self.config
    for k in keys:
      if isinstance(value, dict) and k in value:
        value = value[k]
      else:
        return default
    return value
