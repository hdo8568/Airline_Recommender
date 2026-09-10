"""Local, direct-chat Messages bridge. Reading is separate from sending."""
from __future__ import annotations

import base64
import fcntl
import hashlib
import sqlite3
import subprocess
import time
import unicodedata
from pathlib import Path

from .config import LOCAL, ROOT, private_dir, write_private

SEND_SCRIPT = '''on run argv
    set recipientAddress to item 1 of argv
    set replyText to item 2 of argv
    tell application "Messages"
        set imService to first account whose service type = iMessage and enabled = true
        set recipientBuddy to participant recipientAddress of imService
        send replyText to recipientBuddy
    end tell
end run
'''

ACCESS_SCRIPT = '''tell application "Messages"
    return count of (accounts whose service type = iMessage and enabled = true)
end tell
'''


def sending_error(exc):
    """Expose useful error codes without echoing message contents or recipient data."""
    if isinstance(exc, subprocess.TimeoutExpired):
        return "Messages did not respond in time. Check for a macOS permission prompt. Delivery is uncertain; no automatic retry."
    if isinstance(exc, subprocess.CalledProcessError):
        import re
        detail = exc.stderr or ""
        if isinstance(detail, bytes):
            detail = detail.decode("utf-8", errors="replace")
        codes = re.findall(r"\((-?\d+)\)", detail)
        code = codes[-1] if codes else None
        if code == "-1743":
            return "Automation permission denied (-1743). Open System Settings → Privacy & Security → Automation → Terminal and enable Messages."
        if code == "-1728":
            return "Messages could not find the account or recipient (-1728). Check that your iMessage account is signed in and the tester address is correct."
        if code == "-1712":
            return "Messages timed out (-1712). Check for a permission prompt. Delivery is uncertain; no automatic retry."
        return f"AppleScript failed (error {code or exc.returncode}). Keep Messages open and share this error code."
    if isinstance(exc, OSError):
        return f"Could not start Messages automation (OS error {exc.errno})."
    return f"Response processing failed ({type(exc).__name__}). No automatic retry."


def check_sending_access():
    print("Checking Terminal’s permission to control Messages. No message will be sent. If asked, click Allow.", flush=True)
    try:
        result = subprocess.run(["/usr/bin/osascript", "-e", ACCESS_SCRIPT],
            capture_output=True, text=True, check=True, timeout=55)
    except (subprocess.SubprocessError, OSError) as exc:
        raise ValueError(sending_error(exc)) from None
    if result.stdout.strip() == "0":
        raise ValueError("Messages has no enabled iMessage account. Open Messages → Settings → iMessage and sign in.")
    if not result.stdout.strip().isdigit():
        raise ValueError("Messages returned an unexpected account status.")
    print("Messages automation is accessible. Actual sending/delivery still needs testing.", flush=True)


def readable_text(value):
    """Drop Apple attachment placeholders and invisible-only bodies."""
    if not isinstance(value, str):
        return ""
    cleaned = "".join(c for c in value if c != "\ufffc" and unicodedata.category(c) != "Cf")
    return cleaned.strip()


def normalize_peer(value):
    value = value.strip()
    import re
    if "@" in value:
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid iMessage email address.")
        return value.lower()
    number = re.sub(r"[\s().-]", "", value)
    if not re.fullmatch(r"\+[1-9][0-9]{6,14}", number):
        raise ValueError("Enter the tester’s number with country code, such as +13125550123.")
    return number


class MessagesReader:
    def __init__(self, path=None, decoder=None):
        self.path = Path(path) if path else Path.home() / "Library/Messages/chat.db"
        self.decoder = decoder or LOCAL / "decode-message"
        try:
            self.db = sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True)
            self.db.row_factory = sqlite3.Row
            self.columns = {row[1] for row in self.db.execute("PRAGMA table_info(message)")}
            required = {"guid", "text", "is_from_me", "handle_id", "date", "service"}
            if not required <= self.columns:
                raise ValueError("This Messages database schema is not supported.")
        except sqlite3.Error:
            raise ValueError("Cannot read Messages. Give Terminal Full Disk Access, reopen Terminal, and try again.") from None

    def latest(self):
        return self.db.execute("SELECT COALESCE(MAX(ROWID),0) FROM message").fetchone()[0]

    def new_messages(self, after, peer):
        body = 'm.attributedBody AS body' if "attributedBody" in self.columns else 'NULL AS body'
        associated = "AND COALESCE(m.associated_message_type,0)=0" if "associated_message_type" in self.columns else ""
        system = "AND COALESCE(m.is_system_message,0)=0" if "is_system_message" in self.columns else ""
        rows = self.db.execute(f"""
            SELECT DISTINCT m.ROWID AS rowid, m.guid, m.text, {body}, m.date
            FROM message m JOIN handle h ON h.ROWID=m.handle_id
            JOIN chat_message_join cmj ON cmj.message_id=m.ROWID
            JOIN chat c ON c.ROWID=cmj.chat_id
            WHERE m.ROWID>? AND m.is_from_me=0 AND m.service='iMessage'
              AND lower(h.id)=lower(?)
              AND (CASE WHEN m.date>1000000000000 THEN m.date/1000000000.0 ELSE m.date END)>?
              AND (SELECT COUNT(*) FROM chat_handle_join chj WHERE chj.chat_id=c.ROWID)=1
              {associated} {system}
            ORDER BY m.ROWID LIMIT 50
        """, (after, peer, time.time() - 978307200 - 600)).fetchall()
        messages = []
        for row in rows:
            # Apple timestamps use seconds or nanoseconds since 2001.
            stamp = row["date"]
            if stamp > 1e12:
                stamp /= 1e9
            if time.time() - (stamp + 978307200) > 600:
                continue  # Do not reply to old messages after a long outage.
            text = readable_text(row["text"])
            if not text and row["body"] and self.decoder.exists():
                try:
                    result = subprocess.run([str(self.decoder)], input=base64.b64encode(row["body"]),
                        capture_output=True, timeout=5, check=True)
                    text = readable_text(result.stdout.decode("utf-8"))
                except (subprocess.SubprocessError, UnicodeError, OSError):
                    text = None
            messages.append({"rowid": row["rowid"], "guid": row["guid"], "text": text})
        return messages


def send_message(peer, text):
    # Arguments, never interpolation into script/shell code.
    subprocess.run(["/usr/bin/osascript", "-e", SEND_SCRIPT, peer, text], capture_output=True,
        text=True, check=True, timeout=20)


def build_decoder():
    private_dir()
    subprocess.run(["/usr/bin/swiftc", "-module-cache-path", str(LOCAL / "swift-cache"),
        str(ROOT / "scripts/decode_message.swift"), "-o", str(LOCAL / "decode-message")], check=True)


def run_bridge(agent, store, peer, send=False, reader=None, sender=send_message, once=False, lock_held=False):
    peer = normalize_peer(peer)
    private_dir()
    # One owner across dry-run and sending prevents two responders on this checkout.
    lock = open(LOCAL / "messages.lock", "a")
    try:
        if not lock_held:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock.close()
        raise ValueError("Another reply window is already running. In that Terminal window press Control+C, then reopen this launcher.") from None
    try:
        reader = reader or MessagesReader()
        identity = hashlib.sha256(peer.encode()).hexdigest()[:16]
        channel = f"imessage:{identity}:{'send' if send else 'dry'}"
        after = store.cursor(channel)
        if after is None:
            after = reader.latest()
            store.set_cursor(channel, after)
        print("SEND MODE: replies will be submitted to Messages." if send else "DRY RUN: replies appear here only; nothing will be sent.")
        print("Only the specified tester’s new direct iMessages are processed. Ctrl+C stops.\n", flush=True)
        print("Waiting for a NEW message from the tester you entered. Existing history is not a new test.", flush=True)
        while True:
            # Take watermark before reading, so later arrivals cannot be skipped.
            watermark = reader.latest()
            messages = reader.new_messages(after, peer)
            for message in messages:
                event = channel + ":" + message["guid"]
                if not store.claim(event, channel):
                    continue
                message["text"] = readable_text(message["text"])
                if not message["text"]:
                    store.mark(event, "unsupported_body")
                    print("Skipped a message without readable text. Check the decoder; attachments are not supported.", flush=True)
                    continue
                control = message["text"].strip().lower()
                if control in ("stop", "start"):
                    store.set_cursor(channel + ":paused", int(control == "stop"))
                    store.mark(event, "paused" if control == "stop" else "resumed")
                    print("Tester paused replies." if control == "stop" else "Tester resumed replies.", flush=True)
                    continue
                if store.cursor(channel + ":paused"):
                    store.mark(event, "ignored_while_paused")
                    continue
                try:
                    started = time.monotonic()
                    print("Processing tester message; a live search can take up to roughly 30 seconds. Please wait.", flush=True)
                    reply = agent.reply(channel, message["text"])
                    print(f"Reply prepared in {time.monotonic() - started:.1f}s.", flush=True)
                    store.mark(event, "prepared", reply)
                    print(f"Tester: {message['text']}\nAssistant: {reply}\n", flush=True)
                    if send:
                        store.mark(event, "submitting")
                        sender(peer, reply)
                        store.mark(event, "submitted_unverified")
                        print("Reply submitted to Messages; receipt on the phone is not independently verified.", flush=True)
                    else:
                        store.mark(event, "dry_run")
                except Exception as exc:
                    # A timeout could occur after sending. Never retry automatically.
                    store.mark(event, "needs_review")
                    detail = sending_error(exc)
                    write_private(LOCAL / "last-send-error.json", {"error": detail, "time": time.time()})
                    print(detail + "\nThe response was not retried automatically.", flush=True)
            # If the batch is full, preserve messages beyond it for the next pass.
            after = messages[-1]["rowid"] if len(messages) == 50 else watermark
            store.set_cursor(channel, after)
            if once:
                return
            time.sleep(2)
    finally:
        lock.close()
