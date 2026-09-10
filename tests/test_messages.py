import contextlib
import io
import sqlite3
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from essos_travel.config import sample_context
from essos_travel.conversation import Agent
from essos_travel.messages import MessagesReader, normalize_peer, run_bridge, send_message, sending_error, check_sending_access
from essos_travel.providers import MockFlights
from essos_travel.storage import Store


class MessagesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.path = self.folder / "messages.sqlite3"
        self.db = sqlite3.connect(self.path)
        self.addCleanup(self.db.close)
        self.db.executescript("""
          CREATE TABLE message(guid TEXT,text TEXT,attributedBody BLOB,is_from_me INTEGER,handle_id INTEGER,date INTEGER,service TEXT,associated_message_type INTEGER);
          CREATE TABLE handle(id TEXT);
          CREATE TABLE chat(guid TEXT);
          CREATE TABLE chat_message_join(chat_id INTEGER,message_id INTEGER);
          CREATE TABLE chat_handle_join(chat_id INTEGER,handle_id INTEGER);
          INSERT INTO handle VALUES ('+13125550123'),('+13125550124');
          INSERT INTO chat VALUES ('direct'),('group');
          INSERT INTO chat_handle_join VALUES (1,1),(2,1),(2,2);
        """)
        self.db.commit()

    def add(self, guid, sender=1, outgoing=0, chat=1, service="iMessage", reaction=0, age=0, nanos=True):
        stamp = (time.time() - 978307200 - age) * (1e9 if nanos else 1)
        row = self.db.execute("INSERT INTO message VALUES (?, 'Chicago', NULL, ?, ?, ?, ?, ?)", (guid, outgoing, sender, int(stamp), service, reaction)).lastrowid
        self.db.execute("INSERT INTO chat_message_join VALUES (?,?)", (chat, row))
        self.db.commit()
        return row

    def test_filters_sender_group_sms_own_reactions_and_old_messages(self):
        self.add("allowed")
        self.add("other", sender=2)
        self.add("outgoing", outgoing=1)
        self.add("group", chat=2)
        self.add("sms", service="SMS")
        self.add("reaction", reaction=2000)
        self.add("old", age=3600)
        self.add("seconds", nanos=False)
        reader = MessagesReader(self.path)
        self.addCleanup(reader.db.close)
        self.assertEqual([m["guid"] for m in reader.new_messages(0, "+13125550123")], ["allowed", "seconds"])
        with self.assertRaises(sqlite3.OperationalError):
            reader.db.execute("DELETE FROM message")

    def test_duplicate_delivery_not_replayed(self):
        self.add("one")
        self.add("one")
        reader = MessagesReader(self.path)
        self.addCleanup(reader.db.close)
        store = Store(self.folder / "state.sqlite3")
        self.addCleanup(store.db.close)
        agent = Agent(store, sample_context(), MockFlights())
        # Seed all channel cursors at 0 to simulate a bridge started before incoming messages.
        with patch.object(store, "cursor", return_value=0), patch("essos_travel.messages.LOCAL", self.folder), contextlib.redirect_stdout(io.StringIO()):
            sent = []
            run_bridge(agent, store, "+13125550123", send=True, reader=reader, sender=lambda p,t: sent.append((p,t)), once=True)
            run_bridge(agent, store, "+13125550123", send=True, reader=reader, sender=lambda p,t: sent.append((p,t)), once=True)
        self.assertEqual(len(sent), 1)
        self.assertEqual(store.db.execute("SELECT status FROM events").fetchone()[0], "submitted_unverified")

    def test_first_start_skips_history_and_dry_run_never_sends(self):
        self.add("existing")
        reader = MessagesReader(self.path)
        self.addCleanup(reader.db.close)
        store = Store(self.folder / "state.sqlite3")
        self.addCleanup(store.db.close)
        agent = Agent(store, sample_context(), MockFlights())
        with patch("essos_travel.messages.LOCAL", self.folder), contextlib.redirect_stdout(io.StringIO()):
            run_bridge(agent, store, "+13125550123", reader=reader, sender=lambda *a: self.fail("sent"), once=True)
            self.assertEqual(store.db.execute("SELECT COUNT(*) FROM events").fetchone()[0], 0)
            self.add("new")
            run_bridge(agent, store, "+13125550123", reader=reader, sender=lambda *a: self.fail("sent"), once=True)
        self.assertEqual(store.db.execute("SELECT status FROM events").fetchone()[0], "dry_run")

    def test_uncertain_send_is_not_automatically_retried(self):
        self.add("one")
        reader = MessagesReader(self.path)
        self.addCleanup(reader.db.close)
        store = Store(self.folder / "state.sqlite3")
        self.addCleanup(store.db.close)
        calls = []
        def uncertain(*args):
            calls.append(True)
            raise TimeoutError()
        with patch.object(store, "cursor", return_value=0), patch("essos_travel.messages.LOCAL", self.folder), contextlib.redirect_stdout(io.StringIO()):
            for _ in range(2):
                run_bridge(Agent(store, sample_context(), MockFlights()), store, "+13125550123", send=True, reader=reader, sender=uncertain, once=True)
        self.assertEqual(len(calls), 1)
        self.assertEqual(store.db.execute("SELECT status FROM events").fetchone()[0], "needs_review")

    def test_send_treats_content_as_data(self):
        hostile_text = '" & do shell script "touch /tmp/not-executed"'
        with patch("essos_travel.messages.subprocess.run") as call:
            send_message("+13125550123", hostile_text)
        args = call.call_args[0][0]
        self.assertEqual(args[-1], hostile_text)
        self.assertNotIn(hostile_text, args[2])
        self.assertNotIn("shell", call.call_args.kwargs)

    def test_stop_and_start_controls(self):
        for guid, text in [("1", "STOP"), ("2", "Chicago"), ("3", "START"), ("4", "Chicago")]:
            row = self.add(guid)
            self.db.execute("UPDATE message SET text=? WHERE ROWID=?", (text, row))
            self.db.commit()
        reader = MessagesReader(self.path)
        self.addCleanup(reader.db.close)
        store = Store(self.folder / "state.sqlite3")
        self.addCleanup(store.db.close)
        agent = Agent(store, sample_context(), MockFlights())
        import hashlib
        channel = "imessage:" + hashlib.sha256(b"+13125550123").hexdigest()[:16] + ":send"
        store.set_cursor(channel, 0)
        sent = []
        with patch("essos_travel.messages.LOCAL", self.folder), contextlib.redirect_stdout(io.StringIO()):
            run_bridge(agent, store, "+13125550123", send=True, reader=reader, sender=lambda *a: sent.append(a), once=True)
        self.assertEqual(len(sent), 1)
        self.assertEqual([r[0] for r in store.db.execute("SELECT status FROM events ORDER BY rowid")],
                         ["paused", "ignored_while_paused", "resumed", "submitted_unverified"])

    def test_peer_format(self):
        self.assertEqual(normalize_peer("+1 (312) 555-0123"), "+13125550123")
        with self.assertRaises(ValueError):
            normalize_peer("3125550123")

    def test_sending_diagnostics_do_not_leak_message(self):
        error = subprocess.CalledProcessError(1, ["osascript"], stderr="private message contents (-1743)")
        self.assertIn("Automation permission denied", sending_error(error))
        self.assertNotIn("private message", sending_error(error))
        self.assertIn("uncertain", sending_error(subprocess.TimeoutExpired("osascript", 20)))

    def test_permission_check_never_sends(self):
        with patch("essos_travel.messages.subprocess.run", return_value=subprocess.CompletedProcess([], 0, stdout="1\n")) as call, contextlib.redirect_stdout(io.StringIO()):
            check_sending_access()
        self.assertNotIn("send ", call.call_args[0][0][2])
        with patch("essos_travel.messages.subprocess.run", return_value=subprocess.CompletedProcess([], 0, stdout="0\n")), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ValueError, "no enabled"):
                check_sending_access()


if __name__ == "__main__":
    unittest.main()
