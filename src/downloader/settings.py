# src/downloader/settings.py
"""
Handles configuration loading, saving, and encryption.
"""
import json
from pathlib import Path

from cryptography.fernet import Fernet

CONFIG_DIR = Path.home() / ".litnexus"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = CONFIG_DIR / "settings.json"
KEY_FILE = CONFIG_DIR / "key.key"

def get_key() -> bytes:
    """Retrieves or generates the encryption key."""
    if KEY_FILE.exists():
        return KEY_FILE.read_bytes()
    key = Fernet.generate_key()
    KEY_FILE.write_bytes(key)
    return key

KEY = get_key()
FERNET = Fernet(KEY)

def load_config() -> dict | None:
    """Loads and decrypts the configuration."""
    if CONFIG_FILE.exists():
        try:
            encrypted_data = CONFIG_FILE.read_bytes()
            decrypted_data = FERNET.decrypt(encrypted_data)
            return json.loads(decrypted_data)
        except Exception:
            return None
    return None

def save_config_data(cfg: dict) -> None:
    """Encrypts and saves the configuration."""
    encrypted_data = FERNET.encrypt(json.dumps(cfg, indent=2).encode())
    CONFIG_FILE.write_bytes(encrypted_data)

def clear_config_files() -> None:
    """Deletes configuration and key files."""
    if CONFIG_FILE.exists():
        CONFIG_FILE.unlink()
    if KEY_FILE.exists():
        KEY_FILE.unlink()

def should_show_debug(settings: dict) -> bool:
    """Helper to check debug flag."""
    return settings.get("ui_mode", "research") == "debug"