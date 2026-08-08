"""
Low-level settings management for the downloader.
"""

import json
from pathlib import Path

from cryptography.fernet import Fernet

CONFIG_DIR = Path.home() / ".litnexus"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = CONFIG_DIR / "settings.json"
KEY_FILE = CONFIG_DIR / "key.key"


def get_key():
    if KEY_FILE.exists():
        # --- THIS IS THE CORRECTED LINE ---
        key = KEY_FILE.read_bytes()
    else:
        key = Fernet.generate_key()
        KEY_FILE.write_bytes(key)
    return key


KEY = get_key()
FERNET = Fernet(KEY)


def read_config_raw():
    if not CONFIG_FILE.exists():
        return None
    try:
        encrypted_data = CONFIG_FILE.read_bytes()
        decrypted_data = FERNET.decrypt(encrypted_data)
        return json.loads(decrypted_data)
    except Exception:
        return None


def write_config_raw(cfg):
    encrypted_data = FERNET.encrypt(json.dumps(cfg, indent=2).encode())
    CONFIG_FILE.write_bytes(encrypted_data)


def delete_config_raw():
    if CONFIG_FILE.exists():
        CONFIG_FILE.unlink()
    if KEY_FILE.exists():
        KEY_FILE.unlink()
