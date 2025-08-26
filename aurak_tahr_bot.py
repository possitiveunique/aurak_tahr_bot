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
            if response.status_code == 200:
                return response.json().get("result", [])
        except Exception as e:
            print(f"⚠️ Error getting updates: {e}")
        return []

    def send_message(self, chat_id, text):
        try:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
            requests.post(url, json=payload, timeout=10)
        except Exception as e:
            print(f"⚠️ Error sending message: {e}")

    def approve_join_request(self, chat_id, user_id):
        url = f"https://api.telegram.org/bot{self.token}/approveChatJoinRequest"
        payload = {"chat_id": chat_id, "user_id": user_id}
        requests.post(url, json=payload)

    def decline_join_request(self, chat_id, user_id):
        url = f"https://api.telegram.org/bot{self.token}/declineChatJoinRequest"
        payload = {"chat_id": chat_id, "user_id": user_id}
        requests.post(url, json=payload)

    # ---------------- Handlers ----------------
    def handle_join_request(self, update):
        chat_id = update["chat_join_request"]["chat"]["id"]
        user_id = update["chat_join_request"]["from"]["id"]

        self.pending_requests[user_id] = chat_id
        self.send_message(user_id, "👋 Welcome! Please enter the last 4 digits of your Student ID:")

    def process_student_id(self, update):
        if "message" not in update:
            return
        message = update["message"]
        user_id = message["from"]["id"]
        text = message.get("text", "").strip().lower()

        # Save all users
        self.all_user_ids.add(user_id)
        self.save_all_user_ids()

        # --- If user never started bot properly ---
        if user_id not in self.pending_requests and user_id not in self.awaiting_ack:
            self.send_message(
                user_id,
                "👋 Please send a join request first, or press 'Start' if you haven't. Then try again."
            )
            return

        # --- Handle acknowledgment step ---
        if user_id in self.awaiting_ack:
            if text == "yes":
                chat_id = self.pending_requests[user_id]
                self.send_message(
                    user_id,
                    "✅ Thank you for acknowledging the rules. Welcome to the AURAK Community!",
                )
                self.approve_join_request(chat_id, user_id)
                del self.pending_requests[user_id]
                del self.awaiting_ack[user_id]
            else:
                self.send_message(
                    user_id,
                    "❌ You must reply 'yes' to acknowledge the rules and join."
                )
            return

        # --- Handle ID input ---
        if not (text.isdigit() and len(text) == 4):
            self.send_message(user_id, "❌ Please enter exactly 4 digits of your student ID.")
            return

        student_id = int(text)
        chat_id = self.pending_requests[user_id]

        if student_id in self.existing_ids:
            self.send_message(
                user_id,
                "❌ Student ID already registered. Contact admin if this is an error."
            )
            self.decline_join_request(chat_id, user_id)
            del self.pending_requests[user_id]
            return

        if student_id < self.min_id or student_id > self.max_id:
            self.send_message(user_id, "❌ Invalid student ID. Please try again.")
            self.decline_join_request(chat_id, user_id)
            del self.pending_requests[user_id]
            return

        # --- Success: send rules next ---
        self.existing_ids.add(student_id)
        self.save_existing_ids()

        rules_text = "📜 Please read the rules carefully and reply <b>yes</b> to continue..."
        self.send_message(user_id, rules_text)
        self.awaiting_ack[user_id] = True

    # ---------------- Main Bot Loop ----------------
    def start_bot(self):
        if not self.token:
            print("⚠️ BOT_TOKEN not found. Waiting...")
            while not self.token:
                print("⏳ Still waiting for BOT_TOKEN...")
                self.token = os.getenv("BOT_TOKEN", "").strip()
                time.sleep(300)  # heartbeat every 5 minutes
            print("✅ BOT_TOKEN found. Starting bot.")

        print("🤖 Bot is now running and polling for updates...")
        last_update_time = time.time()

        while True:
            updates = self.get_updates()
            if updates:
                self.last_update_id = updates[-1]["update_id"] + 1
                for update in updates:
                    if "message" in update:
                        self.process_student_id(update)
                    elif "chat_join_request" in update:
                        self.handle_join_request(update)

            # Heartbeat log every 5 minutes
            if time.time() - last_update_time >= 300:
                print("💓 Bot heartbeat: still running...")
                last_update_time = time.time()

            time.sleep(1)


# ---------------- Entry Point ----------------
if __name__ == "__main__":
    while True:
        try:
            bot = aurak_tahr_bot()
            bot.start_bot()
        except Exception as e:
            print(f"⚠️ Bot crashed: {e}")
            traceback.print_exc()
            print("Restarting bot in 5 seconds...")
            time.sleep(5)
        except KeyboardInterrupt:
            print("Keyboard interrupt caught. Ignoring on Railway...")
            time.sleep(5)
