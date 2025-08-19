import requests
import time
import json
import os
from datetime import datetime


class aurak_tahr_bot:
    def __init__(self):
        self.is_running = False
        self.last_update_id = 0
        self.min_id = 5600
        self.max_id = 7690
        self.existing_ids = self.load_existing_ids()
        self.pending_requests = {}

    def load_existing_ids(self):
        """Load existing IDs from a file, or use defaults if file doesn't exist"""
        try:
            if os.path.exists("existing_ids.json"):
                with open("existing_ids.json", "r") as f:
                    return set(json.load(f))
        except:
            pass
        # Default IDs if file doesn't exist or error loading
        return {6966, 6203, 6653, 6881, 6810, 6306, 7231, 6637}

    def save_existing_ids(self):
        """Save current IDs to a file"""
        try:
            with open("existing_ids.json", "w") as f:
                json.dump(list(self.existing_ids), f)
        except Exception as e:
            print(f"Error saving IDs: {e}")

    def start_bot(self):
        print("=== AURAK_TAHR_BOT ===")
        print("Student Verification System")
        print("")
        print("Make sure the bot is admin in your supergroup")
        print("with permissions to add members and manage join requests")
        print("")

        token = input("Enter your bot token: ").strip()

        if not token:
            print("Error: No token provided")
            return

        self.token = token
        self.is_running = True

        print("Connecting to Telegram...")
        if not self.get_bot_info():
            return

        print("")
        print("✓ Bot is running and ready to handle join requests!")
        print("Existing student IDs:", ", ".join(str(id) for id in sorted(self.existing_ids)))
        print("Press Ctrl+C to stop the bot")
        print("")

        try:
            self.poll_updates()
        except KeyboardInterrupt:
            print("\nBot stopped by user")
        finally:
            # Save IDs when bot stops
            self.save_existing_ids()

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
            payload = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML"
            }
            if reply_markup:
                payload["reply_markup"] = reply_markup

            response = requests.post(url, json=payload, timeout=10)
            return response.json()
        except Exception as e:
            print(f"Error sending message: {str(e)}")
            return {"ok": False}

    def approve_join_request(self, chat_id, user_id):
        try:
            url = f"https://api.telegram.org/bot{self.token}/approveChatJoinRequest"
            payload = {
                "chat_id": chat_id,
                "user_id": user_id
            }
            response = requests.post(url, json=payload, timeout=10)
            return response.json()
        except Exception as e:
            print(f"Error approving request: {str(e)}")
            return {"ok": False}

    def decline_join_request(self, chat_id, user_id):
        try:
            url = f"https://api.telegram.org/bot{self.token}/declineChatJoinRequest"
            payload = {
                "chat_id": chat_id,
                "user_id": user_id
            }
            response = requests.post(url, json=payload, timeout=10)
            return response.json()
        except Exception as e:
            print(f"Error declining request: {str(e)}")
            return {"ok": False}

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

        # Store the pending request
        self.pending_requests[user_id] = chat_id

        # Send verification message
        message = f"👋 Welcome, {user_name}!\n\n"
        message += "To join the group, please verify your student status.\n"
        message += "Please send me the <b>last 4 digits</b> of your student ID."

        self.send_message(user_id, message)
        print(f"[{timestamp}] ✓ Sent verification request to {user_name}")

    def process_student_id(self, update):
        if "message" not in update:
            return

        message = update["message"]
        user_id = message["from"]["id"]
        text = message.get("text", "").strip()

        # Check if this user has a pending join request
        if user_id not in self.pending_requests:
            return

        chat_id = self.pending_requests[user_id]
        user_name = message["from"].get("first_name", "User")
        timestamp = datetime.now().strftime("%H:%M:%S")

        if not (text.isdigit() and len(text) == 4):
            self.send_message(user_id, "❌ Please enter exactly 4 digits of your student ID.")
            return

        student_id = int(text)

        # Check if ID already exists
        if student_id in self.existing_ids:
            response = self.send_message(user_id,
                                         "❌ Student ID already registered. Please contact admin @ if this is an error.")
            print(f"[{timestamp}] ✗ {user_name} provided existing ID: {student_id}")

            # Decline the join request
            self.decline_join_request(chat_id, user_id)
            del self.pending_requests[user_id]
            return

        # Check if ID is in valid range
        if student_id < self.min_id or student_id > self.max_id:
            response = self.send_message(user_id, "❌ Invalid student ID. Please check your ID and try again.")
            print(f"[{timestamp}] ✗ {user_name} provided invalid ID: {student_id}")

            # Decline the join request
            self.decline_join_request(chat_id, user_id)
            del self.pending_requests[user_id]
            return

        # VALID ID - ADD IT TO EXISTING IDS AND APPROVE
        self.existing_ids.add(student_id)
        self.save_existing_ids()  # Save to file

        self.send_message(user_id, "✅ <b>Verification successful!</b>\n\nYou have been approved to join the group.")
        print(f"[{timestamp}] ✓ {user_name} provided valid ID: {student_id} - ADDED TO SYSTEM")

        # Approve the join request
        result = self.approve_join_request(chat_id, user_id)
        if result.get("ok"):
            print(f"[{timestamp}] ✓ Approved join request for {user_name}")
        else:
            print(f"[{timestamp}] ✗ Failed to approve {user_name}: {result.get('description')}")

        # Remove from pending requests
        if user_id in self.pending_requests:
            del self.pending_requests[user_id]

    def poll_updates(self):
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

                        # Process join requests
                        if "chat_join_request" in update:
                            self.process_join_request(update)

                        # Process messages (student ID responses)
                        if "message" in update and "text" in update["message"]:
                            self.process_student_id(update)

            except requests.exceptions.Timeout:
                # Timeout is expected, just continue polling
                continue
            except requests.exceptions.ConnectionError:
                print("Connection error. Retrying in 5 seconds...")
                time.sleep(5)
            except Exception as e:
                print(f"Error in polling: {str(e)}")
                time.sleep(5)


if __name__ == "__main__":
    bot = aurak_tahr_bot()
    bot.start_bot()