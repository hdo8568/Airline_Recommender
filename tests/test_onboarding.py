import tempfile
import unittest
from pathlib import Path
from essos_travel.onboarding import Enrollment, WELCOME
from essos_travel.storage import Store

class Reader:
    def latest(self): return 42

class EnrollmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name)/'state.sqlite3')
        self.sent = []
        self.flow = Enrollment(self.store, Reader(), lambda p,t:self.sent.append((p,t)))
    def tearDown(self):
        self.store.db.close()
        self.temp.cleanup()
    def test_consent_and_invalid_numbers_do_not_send(self):
        for phone, consent in [('+13125550123',False),('name@example.com',True),('3125550123',True)]:
            with self.assertRaises(ValueError): self.flow.enroll(phone,consent)
        self.assertEqual(self.sent,[])
    def test_welcome_registers_cursor_and_blocks_duplicate(self):
        self.flow.enroll('+1 (312) 555-0123', True)
        self.assertEqual(self.sent,[('+13125550123',WELCOME)])
        self.assertEqual(self.flow.active,'+13125550123')
        self.flow.last=0
        with self.assertRaises(ValueError): self.flow.enroll('+13125550123',True)
        self.assertEqual(len(self.sent),1)
        self.assertEqual(self.store.db.execute('SELECT status FROM events').fetchone()[0],'submitted_unverified')
    def test_uncertain_send_not_retried_after_restart(self):
        def fail(*args): raise TimeoutError()
        self.flow.sender=fail
        with self.assertRaises(ValueError): self.flow.enroll('+13125550123',True)
        restarted=Enrollment(self.store,Reader(),lambda *args:self.sent.append(args))
        with self.assertRaises(ValueError): restarted.enroll('+13125550123',True)
        self.assertEqual(self.sent,[])
        self.assertEqual(self.store.db.execute('SELECT status FROM events').fetchone()[0],'needs_review')
    def test_rate_limit_blocks_different_number(self):
        self.flow.enroll('+13125550123',True)
        with self.assertRaises(ValueError): self.flow.enroll('+13125550124',True)
        self.assertEqual(len(self.sent),1)
