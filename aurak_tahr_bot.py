import requests
import time
import json
import os
from datetime import datetime


class aurak_tahr_bot:
    def __init__(self):
        self.token = os.getenv("BOT_TOKEN", "").strip()
        self.base_url = f"https://api.telegram.org/bot{self.token}/"
        self.is_running = False
        self.last_update_id = 0

        # Data stores
        self.existing_ids = self.load_existing_ids()
        self.all_user_ids = self.load_all_user_ids()
        self.pending_requests = {}
        self.awaiting_ack = {}

        # Student ID range
        self.min_id = 1000
        self.max_id = 9999

    # ---------------- Load & Save ----------------
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
        url = self.base_url + "getUpdates"
        params = {"timeout": 100, "offset": self.last_update_id + 1}
        try:
            response = requests.get(url, params=params, timeout=120)
            if response.status_code == 200:
                return response.json().get("result", [])
            return []
        except Exception as e:
            print(f"⚠️ Error fetching updates: {e}")
            return []

    def send_message(self, chat_id, text):
        url = self.base_url + "sendMessage"
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        try:
            requests.post(url, json=payload)
        except Exception as e:
            print(f"⚠️ Error sending message: {e}")

    def approve_join_request(self, chat_id, user_id):
        url = self.base_url + "approveChatJoinRequest"
        payload = {"chat_id": chat_id, "user_id": user_id}
        try:
            requests.post(url, json=payload)
            print(f"✅ Approved join request for user {user_id} in chat {chat_id}")
        except Exception as e:
            print(f"⚠️ Error approving join request: {e}")

    def decline_join_request(self, chat_id, user_id):
        url = self.base_url + "declineChatJoinRequest"
        payload = {"chat_id": chat_id, "user_id": user_id}
        try:
            requests.post(url, json=payload)
            print(f"❌ Declined join request for user {user_id} in chat {chat_id}")
        except Exception as e:
            print(f"⚠️ Error declining join request: {e}")

    # ---------------- Handle Join Request ----------------
    def handle_join_request(self, update):
        join_request = update["chat_join_request"]
        chat_id = join_request["chat"]["id"]
        user_id = join_request["from"]["id"]
        user_name = join_request["from"].get("first_name", "User")
        timestamp = datetime.now().strftime("%H:%M:%S")

        self.pending_requests[user_id] = chat_id
        self.send_message(
            user_id,
            f"👋 Hello {user_name}! Please enter the last 4 digits of your student ID to join the AURAK Community.",
        )
        print(f"[{timestamp}] 📥 Join request from {user_name} ({user_id})")

    # ---------------- Student ID Verification ----------------
    def process_student_id(self, update):
        if "message" not in update:
            return
        message = update["message"]
        user_id = message["from"]["id"]
        text = message.get("text", "").strip().lower()

        self.all_user_ids.add(user_id)
        self.save_all_user_ids()

        # --- Handle acknowledgment step ---
        if user_id in self.pending_requests and user_id in self.awaiting_ack:
            if text == "yes":
                chat_id = self.pending_requests[user_id]
                self.send_message(
                    user_id,
                    "✅ Thank you for acknowledging the rules. Welcome to the AURAK Community!",
                )
                self.approve_join_request(chat_id, user_id)
                del self.pending_requests[user_id]
                del self.awaiting_ack[user_id]
                return
            else:
                self.send_message(
                    user_id,
                    "❌ You must acknowledge the rules by replying 'yes' to join.",
                )
                return

        if user_id not in self.pending_requests:
            return

        chat_id = self.pending_requests[user_id]
        user_name = message["from"].get("first_name", "User")
        timestamp = datetime.now().strftime("%H:%M:%S")

        if not (text.isdigit() and len(text) == 4):
            self.send_message(
                user_id, "❌ Please enter exactly 4 digits of your student ID."
            )
            return

        student_id = int(text)
        if student_id in self.existing_ids:
            self.send_message(
                user_id,
                "❌ Student ID already registered. Please contact admin if this is an error.",
            )
            self.decline_join_request(chat_id, user_id)
            del self.pending_requests[user_id]
            return

        if student_id < self.min_id or student_id > self.max_id:
            self.send_message(
                user_id, "❌ Invalid student ID. Please check your ID and try again."
            )
            self.decline_join_request(chat_id, user_id)
            del self.pending_requests[user_id]
            return

        # --- ID is valid, now send rules ---
        self.existing_ids.add(student_id)
        self.save_existing_ids()

        rules_text = """📜 <b>The rules for AURAK Community are:</b>

Welcome, AURAK students! This supergroup is your official platform for university community life, managed by your Student Government Association (SGA). To ensure a respectful, helpful, and safe environment for everyone, please adhere to the following rules.

<b>1. Respect and Etiquette</b>
- Respect all the Laws of the UAE, rules of the University, and the guidelines of this community.
- Be Respectful: Treat all members with courtesy and kindness. Debate is welcome; personal attacks, harassment, bullying, or hate speech are strictly forbidden.
- No Discrimination: Racist, sexist, homophobic, or otherwise discriminatory language will not be tolerated.
- Respect Privacy: Do not share anyone's personal information without consent.
- Cooperate with admins and follow their instructions.

<b>2. Identity and Spam</b>
- No Spamming or flooding chat.
- No Unsolicited Advertising (except in Student Marketing topic).

<b>3. Content Guidelines</b>
- Keep it SFW. No NSFW, pornographic, or violent content.
- Avoid sensitive topics like politics/religion in group chat.
- No Illegal Content.
- Use the right topic.

<b>4. Academic Integrity</b>
- Collaboration is fine, cheating is not. Do not share answers or plagiarize.

<b>5. Reporting Issues</b>
- If you see something inappropriate, report with /report or contact @Admin privately.

<b>6. Online Safety</b>
- Be cautious with files, links, and sharing personal info. You are responsible for your own safety.

👉 If you agree to these rules, type <b>yes</b> to continue.
"""
        self.send_message(user_id, rules_text)
        self.awaiting_ack[user_id] = True
        print(
            f"[{timestamp}] ✓ {user_name} verified ID {student_id}, now awaiting acknowledgment of rules."
        )

    # ---------------- Main Bot Loop ----------------
    def start_bot(self):
        if not self.token:
            print("⚠️ BOT_TOKEN not found. Waiting...")
            while not self.token:
                print("⏳ Still waiting for BOT_TOKEN...")
                self.token = os.getenv("BOT_TOKEN", "").strip()
                time.sleep(300)  # check every 5 minutes
            print("✅ BOT_TOKEN found. Starting bot.")

        print("🤖 Bot is now running and polling for updates...")
        last_update_time = time.time()

        while True:
            try:
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

            except Exception as e:
                print(f"⚠️ Unexpected error: {e}")
                time.sleep(5)


# ---------------- Run Bot ----------------
if __name__ == "__main__":
    bot = aurak_tahr_bot()
    bot.start_bot()
