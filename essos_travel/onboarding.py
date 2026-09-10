"""Local-only tester enrollment UI; one active demo conversation at a time."""
import fcntl
import hashlib
import json
import re
import secrets
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from .config import LOCAL, ROOT, private_dir, load_context, settings
from .storage import Store
from .advanced_agent import AdvancedAgent
from .llm_interpreter import SafeClaudeIntent
from .providers import DuffelFlights
from .messages import MessagesReader, normalize_peer, send_message, run_bridge, check_sending_access

WELCOME = ('Hi! This is the Essos flight demo. I can help find flights for your selected clinic. '
           'We are using a fictional Istanbul clinic and real flight prices. '
           'Which airport are you leaving from, and what is your budget? '
           'Nothing will be booked. Reply STOP to pause automated replies.')

class Enrollment:
    def __init__(self, store, reader, sender=send_message):
        self.store, self.reader, self.sender = store, reader, sender
        self.active = None
        self.last = 0

    def enroll(self, phone, consent):
        if consent is not True:
            raise ValueError('Confirm that this is your number and you want an automated iMessage.')
        if not isinstance(phone, str) or len(phone) > 40:
            raise ValueError('Enter your phone number with its country code.')
        peer = normalize_peer(phone)
        if '@' in peer or (peer.startswith('+1') and len(peer) != 12):
            raise ValueError('Enter a phone number with country code, for example +13125550123.')
        if time.monotonic() - self.last < 30:
            raise ValueError('Please wait 30 seconds before starting another conversation.')
        identity = hashlib.sha256(peer.encode()).hexdigest()[:16]
        channel = f'imessage:{identity}:send'
        event = f'welcome:{identity}:{int(time.time() // 86400)}'
        if not self.store.claim(event, channel):
            self.active = peer
            raise ValueError('A welcome was already attempted for this number today. Reply in Messages; uncertain sends are not retried.')
        self.last = time.monotonic()
        self.store.set_cursor(channel, self.reader.latest())
        self.store.set_cursor(channel + ':paused', 0)
        self.active = peer
        self.store.mark(event, 'submitting', WELCOME)
        try:
            self.sender(peer, WELCOME)
        except Exception:
            self.store.mark(event, 'needs_review')
            raise ValueError('Messages could not confirm submission. Check Messages on the Mac before trying again; no automatic retry.') from None
        self.store.mark(event, 'submitted_unverified')
        return 'Welcome submitted to Messages. Check your iPhone and reply there. Phone delivery is not yet confirmed.'


def main():
    private_dir()
    with open(LOCAL / 'messages.lock', 'a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit('Stop the existing reply Terminal with Control+C, then reopen this page launcher.')
        check_sending_access()
        config = settings()
        store = Store(LOCAL / 'state.sqlite3')
        reader = MessagesReader()
        agent = AdvancedAgent(store, load_context(), DuffelFlights(config.get('DUFFEL_ACCESS_TOKEN')),
                              SafeClaudeIntent(config.get('ANTHROPIC_API_KEY'), config.get('ANTHROPIC_MODEL')))
        enrollment = Enrollment(store, reader)
        csrf = secrets.token_urlsafe(32)
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def respond(self, status, body, kind='application/json'):
                raw = body.encode()
                self.send_response(status)
                self.send_header('Content-Type', kind + '; charset=utf-8')
                self.send_header('Cache-Control', 'no-store')
                self.send_header('X-Frame-Options', 'DENY')
                self.send_header('Content-Length', str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
            def do_GET(self):
                if self.path != '/' or self.headers.get('Host') != '127.0.0.1:8765':
                    return self.respond(404, '{}')
                page = (ROOT / 'web/onboarding.html').read_text().replace('__TOKEN__', csrf)
                self.respond(200, page, 'text/html')
            def do_POST(self):
                if self.path != '/enroll' or self.headers.get('Host') != '127.0.0.1:8765' or self.headers.get('Origin') != 'http://127.0.0.1:8765' or self.headers.get('X-Demo-Token') != csrf:
                    return self.respond(403, json.dumps({'error': 'Refresh the local page and try again.'}))
                try:
                    size = int(self.headers.get('Content-Length', '0'))
                    if not 0 < size < 2048: raise ValueError('Invalid request size.')
                    data = json.loads(self.rfile.read(size))
                    if not isinstance(data, dict): raise ValueError('Invalid request.')
                    result = enrollment.enroll(data.get('phone'), data.get('consent'))
                    self.respond(200, json.dumps({'message': result}))
                except (ValueError, TypeError) as exc:
                    self.respond(400, json.dumps({'error': str(exc)}))
        with HTTPServer(('127.0.0.1', 8765), Handler) as server:
            server.timeout = 2
            print('Open http://127.0.0.1:8765 — keep this Terminal open. Control+C stops.', flush=True)
            webbrowser.open('http://127.0.0.1:8765')
            while True:
                server.handle_request()
                if enrollment.active:
                    run_bridge(agent, store, enrollment.active, send=True, reader=reader, once=True, lock_held=True)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Demo stopped.')
    except (ValueError, OSError) as exc:
        print(str(exc))
