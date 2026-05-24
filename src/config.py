import os
import json

# This file is located in <project_root>/src/config.py
PROJECT_ROOT = os.environ.get("RAG_POC_PROJECT_ROOT", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def project_path(*parts):
    return os.path.join(PROJECT_ROOT, *parts)

_config_cache = None

def load_config():
    global _config_cache
    if _config_cache is not None:
        return _config_cache

    config_path = project_path("config.json")
    config = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception:
            pass
    _config_cache = config
    return config
