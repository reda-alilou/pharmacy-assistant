"""Build a legacy SQLite input solely for read-only PostgreSQL import checks."""
from contextlib import closing
from pathlib import Path
import sqlite3
import time


class LegacyLedgerFixture:
    def __init__(self, path, *, clock=time.time):
        self.path, self.clock = Path(path), clock
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('CREATE TABLE quota_state (scope TEXT PRIMARY KEY,next_at REAL,blocked_until REAL,block_code TEXT,attempts INTEGER)')

    def reserve(self, scope, interval):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('INSERT INTO quota_state VALUES (?,?,0,NULL,1) ON CONFLICT(scope) DO UPDATE SET next_at=excluded.next_at,attempts=attempts+1', (scope,self.clock()+interval))

    def cooldown(self, scope, seconds, code):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('UPDATE quota_state SET blocked_until=?,block_code=? WHERE scope=?', (self.clock()+seconds,code,scope))

    def status(self, scope):
        with closing(sqlite3.connect(self.path)) as db, db:
            row = db.execute('SELECT attempts FROM quota_state WHERE scope=?', (scope,)).fetchone()
        return {'local_attempts_reserved': row[0] if row else 0}
