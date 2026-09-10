"""Read-only local diagnostics. Does not read the Messages inbox or contact providers."""
import fcntl
import json
import sqlite3
from .config import LOCAL, settings


def main():
    config = settings()
    token = config.get('DUFFEL_ACCESS_TOKEN', '')
    print('Flight key:', 'live configured' if token.startswith('duffel_live_') else 'test configured' if token else 'missing')
    print('AI:', 'configured (not necessarily enabled)' if config.get('ANTHROPIC_API_KEY') and config.get('ANTHROPIC_MODEL') else 'not configured; phrase parser available')
    active = False
    lock = LOCAL / 'messages.lock'
    if lock.exists():
        with lock.open('r') as stream:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                active = True
    print('Reply program:', 'running' if active else 'stopped')
    path = LOCAL / 'state.sqlite3'
    if not path.exists():
        print('No conversation database yet.')
        return
    with sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True) as db:
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'events' in tables:
            print('Recent message processing (submitted does not prove delivery):')
            for stamp, state in db.execute('SELECT created,status FROM events ORDER BY rowid DESC LIMIT 5'):
                print(' ', stamp, 'UTC', state)
        if 'searches' in tables:
            row = db.execute('SELECT created,value FROM searches ORDER BY id DESC LIMIT 1').fetchone()
            if row:
                print('Latest conversation search:', row[0], 'UTC')
                print(json.dumps(json.loads(row[1]), indent=2))
            else:
                print('No conversation searches recorded by the updated version yet.')
    report = LOCAL / 'duffel-evaluation.json'
    if report.exists():
        value = json.loads(report.read_text())
        print('Latest standalone evaluation:', value.get('checked_at'), value.get('status'), value.get('mode'))
        if value.get('error'):
            print(value['error'])
        else:
            print('Received:', value.get('offers_received'), 'Eligible:', value.get('offers_eligible'))
    print('For real flights open Start Live iMessage Replies.command. Stop any other bridge first.')


if __name__ == '__main__':
    main()
