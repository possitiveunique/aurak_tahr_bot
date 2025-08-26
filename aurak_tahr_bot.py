import requests
import time
import json
import os
from datetime import datetime
import traceback


class aurak_tahr_bot:
    def __init__(self):
        self.is_running = False
        self.last_update_id = 0
        self.min_id = 1000
        self.max_id = 9999
        self.token = os.getenv("BOT_TOKEN", "").strip()

        # Storage
        self.existing_ids = self.load_existing_ids()
        self.pending_requests = {}   # user_id -> chat_id
        self.awaiting_ack = {}       # user_id -> True if waiting for "yes"
        self.all_user_ids = self.load_all_user_ids()

    # ---------------- Data Persistence ----------------
    def load_existing_ids(self):
        if os.path.exists("existing_ids.json"):
            with open("existing_ids.json", "r") as f:
                return set(json.load(f))
        return set()

    def save_existing_ids(self):
        with open("existing_ids.json", "w") as f:
            json.dump(list(self.existing_ids), f)

    def load_all_user_ids(self):
        if os.path.exists("all_user_ids.json"):
            with open("all_user_ids.json", "r") as f:
                return set(json.load(f))
        return set()

    def save_all_user_ids(self):
        with open("all_user_ids.json", "w") as f:
            json.dump(list(self.all_user_ids), f)

    # ---------------- Telegram API ----------------
    def get_updates(self):
        try:
            url = f"https://api.telegram.org/bot{self.token}/getUpdates"
            params = {"offset": self.last_update_id + 1, "timeout": 30}
            response = requests.get(url, params=params, timeout=35)
            if response.st
