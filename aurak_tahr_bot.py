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
        self.min_id = 4500
        self.max_id = 7700
        self.existing_ids = self.load_existing_ids()
        self.all_user_ids = self.load_all_user_ids()
        self.pending_requests = {}
        self.awaiting_ack = {}  # track users waiting to acknowledge rules

    # ---------------- Load / Save ----------------
    def load_existing_ids(self):
        try:
            if os.path.exists("existing_ids.json"):
                with open("existing_ids.json", "r") as f:
                    return set(json.load(f))
        except:
            pass
        return {6966, 6203, 6653, 6881, 6810, 6306, 7231, 6637}

    def save_existing_ids(self):
        try:
            with open("existing_ids.json", "w") as f:
                json.dump(list(self.existing_ids), f)
        except Exception as e:
            print(f"Error saving IDs: {e}")

    def load_all_user_ids(self):
        try:
            if os.path.exists("all_user_ids.json"):
                with open("all_user_ids.json", "r") as f:
                    return set(json.load(f))
        except:
            pass
        return set()

    def save_all_user_ids(self):
        try:
            with open("all_user_ids.json", "w") as f:
                json.dump(list(self.all_user_ids), f)
        except Exception as e:
            print(f"Error saving all user IDs: {e}")

    # ---------------- Bot Startup ----------------
    def start_bot(self):
        self.token = os.getenv("BOT_TOKEN", "").strip()
        while not self.token:
            print("[heartbeat] Waiting for BOT_TOKEN...")
            self.token = os.getenv("BOT_TOKEN", "").strip()
            time.sleep(120)  # heartbeat every 2 mins

        self.is_running = True

        # Try to connect to Telegram until successful
        while not self.get_bot_info():
            print("[heartbeat] Cannot connect to Telegram, retrying in 2 minutes...")
            time.sleep(120)

        print("\n✓ Bot is running and ready to handle join requests!")
        print("Existing student IDs:", ", ".join(str(id) for id in sorted(self.existing_ids)))

        try:
            self.poll_updates()
        except Exception as e:
            print(f"⚠️ Polling crashed: {e}")
            traceback.print_exc()
            time.sleep(5)

    # ---------------- Telegram API Helpers ----------------
    def get_bot_info(self):
        try:
            url = f"https://api.telegram.org/bot{self.token}/getMe"
            response = requests.get(url, timeout=10)
            data = response.json()
            if data["ok"]:
                bot_info = data["result"]
                print(f"✓ Connected as: {bot_info['first_name']} (@{bot_info['username']})")
                return True
            else:
                print(f"✗ Error: {data.get('description', 'Unknown error')}")
                return False
        except Exception as e:
            print(f"✗ Connection failed: {str(e)}")
            return False

    def send_message(self, chat_id, text, reply_markup=None):
        try:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
            if reply_markup:
                payload["reply_markup"] = reply_markup
            return requests.post(url, json=payload, timeout=10).json()
        except Exception as e:
            print(f"Error sending message: {str(e)}")
            return {"ok": False}

    def approve_join_request(self, chat_id, user_id):
        try:
            url = f"https://api.telegram.org/bot{self.token}/approveChatJoinRequest"
            payload = {"chat_id": chat_id, "user_id": user_id}
            return requests.post(url, json=payload, timeout=10).json()
        except Exception as e:
            print(f"Error approving request: {str(e)}")
            return {"ok": False}

    def decline_join_request(self, chat_id, user_id):
        try:
            url = f"https://api.telegram.org/bot{self.token}/declineChatJoinRequest"
            payload = {"chat_id": chat_id, "user_id": user_id}
            return requests.post(url, json=payload, timeout=10).json()
        except Exception as e:
            print(f"Error declining request: {str(e)}")
            return {"ok": False}

    # ---------------- Join Request Processing ----------------
    def process_join_request(self, update):
        if "chat_join_request" not in update:
            return
        request = update["chat_join_request"]
        user_id = request["from"]["id"]
        chat_id = request["chat"]["id"]
        user_name = request["from"].get("first_name", "User")
        username = request["from"].get("username", "")
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] 📨 Join request from {user_name} (@{username})")

        self.pending_requests[user_id] = chat_id
        self.all_user_ids.add(user_id)
        self.save_all_user_ids()

        message = f"👋 Welcome, {user_name}!\nTo join the group, please verify your student status.\nPlease send me the <b>last 4 digits</b> of your student ID."
        self.send_message(user_id, message)
        print(f"[{timestamp}] ✓ Sent verification request to {user_name}")

    # ---------------- Student ID Verification ----------------
    def process_student_id(self, update):
        if "message" not in update:
            return
        message = update["message"]
        user_id = message["from"]["id"]
        text = message.get("text", "").strip().lower()

        self.all_user_ids.add(user_id)
        self.save_all_user_ids()

        # --- If awaiting acknowledgment ---
        if user_id in self.awaiting_ack:
            if text == "yes":
                chat_id = self.pending_requests[user_id]
                self.send_message(user_id, "✅ Thank you! You are now approved to join the AURAK Community.")
                self.approve_join_request(chat_id, user_id)
                del self.pending_requests[user_id]
                del self.awaiting_ack[user_id]
            else:
                self.send_message(user_id, "❌ You must reply <b>yes</b> to acknowledge the rules.")
            return

        if user_id not in self.pending_requests:
            return
        chat_id = self.pending_requests[user_id]
        user_name = message["from"].get("first_name", "User")
        timestamp = datetime.now().strftime("%H:%M:%S")

        if not (text.isdigit() and len(text) == 4):
            self.send_message(user_id, "❌ Please enter exactly 4 digits of your student ID.")
            return

        student_id = int(text)
        if student_id in self.existing_ids:
            self.send_message(user_id, "❌ Student ID already registered. Please contact admin if this is an error.")
            self.decline_join_request(chat_id, user_id)
            del self.pending_requests[user_id]
            return

        if student_id < self.min_id or student_id > self.max_id:
            self.send_message(user_id, "❌ Invalid student ID. Please check your ID and try again.")
            self.decline_join_request(chat_id, user_id)
            del self.pending_requests[user_id]
            return

        self.existing_ids.add(student_id)
        self.save_existing_ids()

        # --- Send rules instead of approving immediately ---
        rules_text = (
            "📜 <b>The rules for AURAK Community are:</b>\n\n"
            "Welcome, AURAK students! This supergroup is your official platform for university community life, "
            "managed by your Student Government Association (SGA). To ensure a respectful, helpful, and safe environment "
            "for everyone, please adhere to the following rules.\n\n"
            "1. <b>Respect and Etiquette</b>\n"
            "• Respect all the Laws of the UAE, rules of the University, and the guidelines of this community.\n"
            "• Be Respectful: Treat all members with courtesy and kindness. Debate is welcome; personal attacks, harassment, bullying, or hate speech are strictly forbidden.\n"
            "• No Discrimination: Racist, sexist, homophobic, or otherwise discriminatory language will not be tolerated.\n"
            "• Respect Privacy: Do not share anyone's personal information without their consent.\n"
            "• Cooperate with admins and follow their instructions.\n\n"
            "2. <b>Identity and Spam</b>\n"
            "• No Spamming or flooding the chat.\n"
            "• No unsolicited advertising without admin permission.\n\n"
            "3. <b>Content Guidelines</b>\n"
            "• Keep it Safe For Work.\n"
            "• No NSFW, pornographic, violent, or illegal content.\n"
            "• Avoid sensitive topics like politics and religion here.\n\n"
            "4. <b>Academic Integrity</b>\n"
            "• Collaboration is encouraged, but cheating or plagiarism is strictly prohibited.\n\n"
            "5. <b>Reporting Issues</b>\n"
            "• If you see a post that breaks the rules, use /report or message an admin privately.\n\n"
            "6. <b>Online Safety</b>\n"
            "• Be cautious with files, links, and personal information.\n\n"
            "➡️ Please reply <b>yes</b> to acknowledge the rules and complete your verification."
        )
        self.send_message(user_id, rules_text)
        self.awaiting_ack[user_id] = True
        print(f"[{timestamp}] ✓ {user_name} verified ID {student_id}, awaiting rules acknowledgment.")

    # ---------------- Polling Loop ----------------
    def poll_updates(self):
        last_heartbeat = time.time()
        while self.is_running:
            try:
                url = f"https://api.telegram.org/bot{self.token}/getUpdates"
                params = {
                    "timeout": 30,
                    "offset": self.last_update_id + 1,
                    "allowed_updates": ["chat_join_request", "message"]
                }
                response = requests.get(url, params=params, timeout=35)
                data = response.json()
                if data["ok"] and data["result"]:
                    for update in data["result"]:
                        self.last_update_id = update["update_id"]
                        if "chat_join_request" in update:
                            self.process_join_request(update)
                        if "message" in update and "text" in update["message"]:
                            self.process_student_id(update)
                # heartbeat every 2 minutes
                if time.time() - last_heartbeat >= 120:
                    print("[heartbeat] Bot is alive and polling...")
                    last_heartbeat = time.time()
            except requests.exceptions.Timeout:
                continue
            except requests.exceptions.ConnectionError:
                print("[heartbeat] Connection error. Retrying in 2 minutes...")
                time.sleep(120)
            except Exception as e:
                print(f"[heartbeat] Error in polling: {e}")
                traceback.print_exc()
                time.sleep(5)
            time.sleep(1)


# ---------------- Main Entry ----------------
if __name__ == "__main__":
    while True:
        try:
            bot = aurak_tahr_bot()
            bot.start_bot()
        except Exception as e:
            print(f"[heartbeat] Bot crashed: {e}")
            traceback.print_exc()
            print("[heartbeat] Restarting bot in 2 minutes...")
            time.sleep(120)
        except KeyboardInterrupt:
            print("[heartbeat] KeyboardInterrupt caught. Ignoring on Railway...")
            time.sleep(120)
