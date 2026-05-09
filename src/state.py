import os
import json
import hashlib
from src.logger import logger

STATE_FILE = "sync_state.json"

def calculate_file_hash(filepath: str) -> str:
    """Calculate MD5 hash of a file."""
    if not os.path.exists(filepath):
        return ""
    hash_md5 = hashlib.md5()
    try:
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        logger.error(f"Error calculating hash for {filepath}: {e}")
        return ""

def calculate_dict_hash(d: dict) -> str:
    """Calculate MD5 hash of a dictionary (used for config)."""
    d_str = json.dumps(d, sort_keys=True)
    return hashlib.md5(d_str.encode('utf-8')).hexdigest()

class StateTracker:
    def __init__(self):
        self.state = {
            "config_hash": "",
            "files": {}
        }
        self.load_state()

    def load_state(self):
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    self.state = json.load(f)
            except Exception as e:
                logger.error(f"Error loading state file: {e}")

    def save_state(self):
        try:
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving state file: {e}")

    def clear_state(self):
        self.state = {
            "config_hash": "",
            "files": {}
        }
        self.save_state()

    def get_config_hash(self) -> str:
        return self.state.get("config_hash", "")

    def set_config_hash(self, hash_val: str):
        self.state["config_hash"] = hash_val
        self.save_state()

    def get_file_record(self, filepath: str) -> dict:
        """Returns the record for a file, or empty dict if not tracked."""
        return self.state.get("files", {}).get(filepath, {})

    def update_file_record(self, filepath: str, record: dict):
        if "files" not in self.state:
            self.state["files"] = {}
        self.state["files"][filepath] = record
        self.save_state()

    def remove_file_record(self, filepath: str):
        if "files" in self.state and filepath in self.state["files"]:
            del self.state["files"][filepath]
            self.save_state()

    def get_all_tracked_files(self) -> list:
        return list(self.state.get("files", {}).keys())
