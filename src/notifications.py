"""FR-8: opt-in email outbox for newly queued review candidates. Independent code."""
import os
import re
import smtplib
import ssl
import time
from email.message import EmailMessage


def initialize(conn):
    # Individual DDL statements preserve the caller's ingestion transaction.
    conn.execute("CREATE TABLE IF NOT EXISTS notification_settings (id INTEGER PRIMARY KEY CHECK(id=1), enabled INTEGER NOT NULL, channel TEXT NOT NULL, recipient TEXT NOT NULL)")
    conn.execute("CREATE TABLE IF NOT EXISTS notification_outbox (id INTEGER PRIMARY KEY, platform TEXT NOT NULL, post_id TEXT NOT NULL, recipient TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0, next_attempt REAL NOT NULL DEFAULT 0, error_type TEXT, sent_at REAL)")
    conn.execute("CREATE TABLE IF NOT EXISTS notification_seen (platform TEXT NOT NULL, post_id TEXT NOT NULL, PRIMARY KEY(platform,post_id))")


def settings(conn):
    initialize(conn)
    row = conn.execute('SELECT enabled,channel,recipient FROM notification_settings WHERE id=1').fetchone()
    return dict(zip(('enabled','channel','recipient'), row or (0,'email','')))


def valid_email(value):
    return len(value) <= 254 and bool(re.fullmatch(r'[^\s@<>;,]+@[^\s@<>;,]+\.[^\s@<>;,]+', value))


def save_settings(conn, enabled, channel, recipient):
    """FR-8: settings are separate from SMTP secrets; SMS explicitly deferred."""
    recipient = recipient.strip()
    if channel != 'email':
        raise ValueError('SMS is not available yet; choose Email')
    if (enabled or recipient) and not valid_email(recipient):
        raise ValueError('Enter one valid email address')
    with conn:
        initialize(conn)
        conn.execute('INSERT OR REPLACE INTO notification_settings VALUES (1,?,?,?)', (int(enabled),channel,recipient))


def queue_candidates(conn, results):
    """FR-8: once per source identity, in the same transaction as candidate state.

    Existing candidates are never retroactively notified. Disabled notifications
    consume the event, so enabling later only applies to future new candidates.
    """
    config = settings(conn)
    # First upgrade seeds existing candidates before relevance overwrites them.
    conn.execute("INSERT OR IGNORE INTO notification_seen SELECT platform,post_id FROM relevance WHERE status='candidate'")
    for platform, post_id, status in results:
        if status != 'candidate':
            continue
        fresh = conn.execute('INSERT OR IGNORE INTO notification_seen VALUES (?,?)', (platform,post_id)).rowcount
        if fresh and config['enabled']:
            conn.execute('INSERT INTO notification_outbox(platform,post_id,recipient) VALUES (?,?,?)', (platform,post_id,config['recipient']))


def smtp_ready():
    return bool(os.environ.get('ASAP_SMTP_HOST') and os.environ.get('ASAP_SMTP_FROM'))


def send_email(recipient, platform, post_id):
    """Credentials from environment only. TLS is mandatory for remote SMTP."""
    host = os.environ['ASAP_SMTP_HOST']
    mode = os.environ.get('ASAP_SMTP_SECURITY','starttls')
    if mode not in ('starttls','ssl'):
        raise ValueError('SMTP security must be starttls or ssl')
    port = int(os.environ.get('ASAP_SMTP_PORT','465' if mode=='ssl' else '587'))
    message = EmailMessage()
    message['From'] = os.environ['ASAP_SMTP_FROM']
    message['To'] = recipient
    message['Subject'] = 'ASAP: new post queued for review'
    message.set_content('A new post has been queued for administrator review.\nSource: '+platform+'\nPost ID: '+post_id+'\nOpen the ASAP admin Review Queue. Passing relevance does not approve publication.')
    cls = smtplib.SMTP_SSL if mode=='ssl' else smtplib.SMTP
    kwargs = dict(timeout=15)
    if mode=='ssl': kwargs['context']=ssl.create_default_context()
    with cls(host,port,**kwargs) as client:
        if mode=='starttls': client.starttls(context=ssl.create_default_context())
        username = os.environ.get('ASAP_SMTP_USERNAME')
        if username: client.login(username,os.environ.get('ASAP_SMTP_PASSWORD',''))
        client.send_message(message)


def deliver_pending(conn, sender=None, now=None):
    """FR-8: single worker; persistent retry. SMTP delivery is at-least-once.

    A crash after SMTP acceptance but before the sent marker may repeat an email.
    No delivery error changes ingestion, approvals, or publication eligibility.
    """
    now = time.time() if now is None else now
    config = settings(conn)
    conn.commit()
    if not config['enabled'] or (sender is None and not smtp_ready()): return 0
    sender = sender or send_email
    rows = conn.execute("SELECT id,platform,post_id,recipient,attempts FROM notification_outbox WHERE state='pending' AND next_attempt<=? ORDER BY id LIMIT 10", (now,)).fetchall()
    sent = 0
    for key,platform,post_id,recipient,attempts in rows:
        try:
            sender(recipient,platform,post_id)
        except Exception as error:
            with conn:
                conn.execute('UPDATE notification_outbox SET attempts=attempts+1,next_attempt=?,error_type=? WHERE id=?', (now+min(3600,60*2**min(attempts,6)),type(error).__name__,key))
        else:
            with conn:
                conn.execute("UPDATE notification_outbox SET state='sent',attempts=attempts+1,error_type=NULL,sent_at=? WHERE id=?", (now,key))
            sent += 1
    return sent


def summary(conn):
    initialize(conn)
    pending = conn.execute("SELECT count(*) FROM notification_outbox WHERE state='pending'").fetchone()[0]
    sent = conn.execute("SELECT count(*) FROM notification_outbox WHERE state='sent'").fetchone()[0]
    error = conn.execute("SELECT error_type FROM notification_outbox WHERE state='pending' AND error_type IS NOT NULL ORDER BY id DESC LIMIT 1").fetchone()
    return dict(pending=pending,sent=sent,error=error[0] if error else '')
