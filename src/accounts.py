"""Local identities and opaque, revocable sessions; never store browser bearer tokens."""
from contextlib import closing
import hashlib
import hmac
import os
from pathlib import Path
import secrets
import sqlite3
import time
from .notifications import valid_email


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    key = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1)
    return salt + ':' + key.hex()


def password_matches(password, encoded):
    try:
        return hmac.compare_digest(password_hash(password, encoded.split(':')[0]), encoded)
    except (ValueError, TypeError):
        return False


class Accounts:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as conn, conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL,
                    password_hash TEXT, google_sub TEXT UNIQUE,
                    email_verified INTEGER NOT NULL DEFAULT 0, created_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY, user_id TEXT, csrf TEXT NOT NULL,
                    expires REAL NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id));
                CREATE TABLE IF NOT EXISTS oauth_states (
                    state_hash TEXT PRIMARY KEY, session_hash TEXT NOT NULL,
                    nonce TEXT NOT NULL, verifier TEXT NOT NULL, link_user TEXT,
                    expires REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS auth_attempts (
                    bucket TEXT NOT NULL, attempted_at REAL NOT NULL);
                CREATE INDEX IF NOT EXISTS attempt_time ON auth_attempts(attempted_at);
            ''')
        os.chmod(self.path, 0o600)
        self.dummy_hash = password_hash(secrets.token_urlsafe(32))

    def connect(self):
        conn = sqlite3.connect(self.path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON')
        return conn

    def user(self, uid):
        with closing(self.connect()) as conn:
            row = conn.execute('SELECT id,email,email_verified,google_sub FROM users WHERE id=?', (uid,)).fetchone()
            return dict(row) if row else None

    def ids(self):
        with closing(self.connect()) as conn:
            return [r[0] for r in conn.execute('SELECT id FROM users')]

    def register(self, email, password):
        email = email.strip().lower()
        if not valid_email(email) or not 12 <= len(password) <= 256:
            raise ValueError('Use a valid email and a password of 12–256 characters.')
        encoded = password_hash(password)
        with closing(self.connect()) as conn, conn:
            conn.execute('BEGIN IMMEDIATE')
            if conn.execute('SELECT count(*) FROM users').fetchone()[0] >= 100:
                raise ValueError('Registration capacity reached. Contact the administrator.')
            uid = secrets.token_hex(16)
            try:
                conn.execute('INSERT INTO users VALUES (?,?,?,NULL,0,?)', (uid, email, encoded, time.time()))
            except sqlite3.IntegrityError:
                raise ValueError('Registration unavailable for this email. Sign in or use another address.') from None
        return self.user(uid)

    def authenticate(self, email, password):
        with closing(self.connect()) as conn:
            row = conn.execute('SELECT * FROM users WHERE email=?', (email.strip().lower(),)).fetchone()
        encoded = row['password_hash'] if row and row['password_hash'] else self.dummy_hash
        valid = password_matches(password, encoded)
        return self.user(row['id']) if valid and row and row['password_hash'] else None

    def google_user(self, claims, link_user=None):
        # Cryptographic verification happens before entering this method.
        sub, email = claims.get('sub'), str(claims.get('email', '')).strip().lower()
        if not sub or not valid_email(email) or claims.get('email_verified') is not True:
            raise ValueError('Google must provide a verified email address.')
        with closing(self.connect()) as conn, conn:
            conn.execute('BEGIN IMMEDIATE')
            existing = conn.execute('SELECT id FROM users WHERE google_sub=?', (sub,)).fetchone()
            if existing:
                if link_user and existing[0] != link_user:
                    raise ValueError('This Google account is already linked to another account.')
                return self.user(existing[0])
            if link_user:
                row = conn.execute('SELECT email,google_sub FROM users WHERE id=?', (link_user,)).fetchone()
                if not row or row['email'] != email or row['google_sub']:
                    raise ValueError('Link the Google account with the same email as your signed-in account.')
                conn.execute('UPDATE users SET google_sub=?,email_verified=1 WHERE id=?', (sub, link_user))
                uid = link_user
            else:
                if conn.execute('SELECT 1 FROM users WHERE email=?', (email,)).fetchone():
                    raise ValueError('Sign in with your password first, then link Google from Account. Accounts are never linked by email alone.')
                if conn.execute('SELECT count(*) FROM users').fetchone()[0] >= 100:
                    raise ValueError('Registration capacity reached.')
                uid = secrets.token_hex(16)
                conn.execute('INSERT INTO users VALUES (?,?,NULL,?,1,?)', (uid, email, sub, time.time()))
        return self.user(uid)

    def new_session(self, uid=None, old_token=None):
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        with closing(self.connect()) as conn, conn:
            conn.execute('DELETE FROM sessions WHERE expires<=?', (time.time(),))
            if old_token:
                conn.execute('DELETE FROM sessions WHERE token_hash=?', (digest(old_token),))
            conn.execute('INSERT INTO sessions VALUES (?,?,?,?)', (digest(token), uid, csrf, time.time()+(28800 if uid else 600)))
        return token

    def session(self, token):
        if not token or len(token) > 128:
            return None
        with closing(self.connect()) as conn:
            row = conn.execute('SELECT * FROM sessions WHERE token_hash=? AND expires>?', (digest(token), time.time())).fetchone()
            return dict(row) if row else None

    def logout(self, token):
        with closing(self.connect()) as conn, conn:
            conn.execute('DELETE FROM sessions WHERE token_hash=?', (digest(token),))
            conn.execute('DELETE FROM oauth_states WHERE session_hash=?', (digest(token),))

    def limit(self, key, maximum=8, period=60):
        # Persistent atomic buckets; remote address is supplied by the trusted edge.
        now = time.time()
        with closing(self.connect()) as conn, conn:
            conn.execute('BEGIN IMMEDIATE')
            conn.execute('DELETE FROM auth_attempts WHERE attempted_at<?', (now-3600,))
            bucket = digest(key)
            count = conn.execute('SELECT count(*) FROM auth_attempts WHERE bucket=? AND attempted_at>?', (bucket, now-period)).fetchone()[0]
            if count >= maximum:
                return False
            conn.execute('INSERT INTO auth_attempts VALUES (?,?)', (bucket, now))
        return True

    def start_oauth(self, token, link_user=None):
        state, nonce, verifier = (secrets.token_urlsafe(32) for _ in range(3))
        with closing(self.connect()) as conn, conn:
            conn.execute('DELETE FROM oauth_states WHERE expires<=? OR session_hash=?', (time.time(), digest(token)))
            conn.execute('INSERT INTO oauth_states VALUES (?,?,?,?,?,?)',
                         (digest(state), digest(token), nonce, verifier, link_user, time.time()+600))
        return state, nonce, verifier

    def consume_oauth(self, state, token):
        with closing(self.connect()) as conn, conn:
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute('SELECT * FROM oauth_states WHERE state_hash=? AND session_hash=? AND expires>?',
                               (digest(state), digest(token), time.time())).fetchone()
            if not row:
                raise ValueError('Google sign-in expired. Start again.')
            conn.execute('DELETE FROM oauth_states WHERE state_hash=?', (digest(state),))
        return dict(row)
