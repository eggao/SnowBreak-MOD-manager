import json
import os
import sys

def get_app_dir() -> str:
    if getattr(sys, "frozen", False) and hasattr(sys, "executable"):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def resource_path(relative_path: str) -> str:
    """Get absolute path to resource, works for dev, PyInstaller and Nuitka"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

def normalize_path(path: str) -> str:
    path = (path or "").strip().strip('"')
    if not path:
        return ""
    return os.path.normpath(os.path.expanduser(path))

def get_config_path() -> str:
    return os.path.join(get_app_dir(), "mod_manager.config.json")

def load_config() -> dict:
    path = get_config_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        return data
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError):
        return {}

def save_config(cfg_data: dict) -> None:
    path = get_config_path()
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    # Merge with existing data to not lose other keys
    existing = load_config()
    existing.update(cfg_data)

    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)
