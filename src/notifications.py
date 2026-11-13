"""FR-8: opt-in email outbox for newly queued review candidates. Independent code."""
import os
import re
import smtplib
import ssl
import time
from email.message import EmailMessage


EVENTS={'ai_review':('AI needs human review','The AI flagged a post for human review. Open Review Queue.'),
        'reauth':('re-authentication needed','A connected source needs re-authentication. Open Sources.'),
        'duplicates':('possible duplicate detected','A possible duplicate group needs attention. Open Review Queue.'),
        'new_post':('new post queued for review','A new post has been queued for review. Passing relevance does not approve publication.')}


def initialize(conn):
    # Individual DDL statements preserve the caller's ingestion transaction.
    conn.execute("CREATE TABLE IF NOT EXISTS notification_settings (id INTEGER PRIMARY KEY CHECK(id=1), enabled INTEGER NOT NULL, channel TEXT NOT NULL, recipient TEXT NOT NULL)")
    conn.execute("CREATE TABLE IF NOT EXISTS notification_outbox (id INTEGER PRIMARY KEY, platform TEXT NOT NULL, post_id TEXT NOT NULL, recipient TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0, next_attempt REAL NOT NULL DEFAULT 0, error_type TEXT, sent_at REAL)")
    conn.execute("CREATE TABLE IF NOT EXISTS notification_seen (platform TEXT NOT NULL, post_id TEXT NOT NULL, PRIMARY KEY(platform,post_id))")
    conn.execute('CREATE TABLE IF NOT EXISTS notification_preferences (event TEXT PRIMARY KEY,enabled INTEGER NOT NULL)')
    conn.execute('CREATE TABLE IF NOT EXISTS notification_events_seen (event TEXT NOT NULL,subject TEXT NOT NULL,version TEXT NOT NULL,PRIMARY KEY(event,subject,version))')
    if 'event' not in {r[1] for r in conn.execute('PRAGMA table_info(notification_outbox)')}:
        conn.execute("ALTER TABLE notification_outbox ADD COLUMN event TEXT NOT NULL DEFAULT 'new_post'")



def settings(conn):
    initialize(conn)
    row = conn.execute('SELECT enabled,channel,recipient FROM notification_settings WHERE id=1').fetchone()
    result=dict(zip(('enabled','channel','recipient'), row or (0,'email','')))
    prefs=dict(conn.execute('SELECT event,enabled FROM notification_preferences'))
    result.update({event:bool(prefs.get(event,event=='new_post')) for event in EVENTS})
    return result


def valid_email(value):
    return len(value) <= 254 and bool(re.fullmatch(r'[^\s@<>;,]+@[^\s@<>;,]+\.[^\s@<>;,]+', value))


def save_settings(conn, enabled, channel, recipient, events=None):
    """FR-8: settings are separate from SMTP secrets; SMS explicitly deferred."""
    recipient = recipient.strip()
    if channel != 'email':
        raise ValueError('SMS is not available yet; choose Email')
    if (enabled or recipient) and not valid_email(recipient):
        raise ValueError('Enter one valid email address')
    with conn:
        initialize(conn)
        conn.execute('INSERT OR REPLACE INTO notification_settings VALUES (1,?,?,?)', (int(enabled),channel,recipient))
        if events is not None:
            conn.executemany('INSERT OR REPLACE INTO notification_preferences VALUES (?,?)',[(event,int(bool(events.get(event)))) for event in EVENTS])


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
        if fresh and config['enabled'] and config['new_post']:
            conn.execute('INSERT INTO notification_outbox(platform,post_id,recipient) VALUES (?,?,?)', (platform,post_id,config['recipient']))


def queue_event(conn,event,subject,version='',platform='system',post_id=None):
    if event not in EVENTS or event=='new_post':raise ValueError('Unknown notification event')
    config=settings(conn)
    fresh=conn.execute('INSERT OR IGNORE INTO notification_events_seen VALUES (?,?,?)',(event,subject,str(version))).rowcount
    if fresh and config['enabled'] and config[event]:
        conn.execute('INSERT INTO notification_outbox(platform,post_id,recipient,event) VALUES (?,?,?,?)',(platform,post_id or subject,config['recipient'],event))


def queue_ai_review(conn,post,model,policy):
    import hashlib
    from .web_editorial import fingerprint
    version=hashlib.sha256((fingerprint(post)+model+policy).encode()).hexdigest()
    queue_event(conn,'ai_review',post['platform']+':'+post['post_id'],version,post['platform'],post['post_id'])


def smtp_ready():
    return bool(os.environ.get('ASAP_SMTP_HOST') and os.environ.get('ASAP_SMTP_FROM'))


def send_email(recipient, platform, post_id, event="new_post"):
    """Credentials from environment only. TLS is mandatory for remote SMTP."""
    host = os.environ['ASAP_SMTP_HOST']
    mode = os.environ.get('ASAP_SMTP_SECURITY','starttls')
    if mode not in ('starttls','ssl'):
        raise ValueError('SMTP security must be starttls or ssl')
    port = int(os.environ.get('ASAP_SMTP_PORT','465' if mode=='ssl' else '587'))
    message = EmailMessage()
    message['From'] = os.environ['ASAP_SMTP_FROM']
    message['To'] = recipient
    message['Subject'] = 'ASAP: '+EVENTS[event][0]
    message.set_content(EVENTS[event][1]+'\nSource: '+platform+'\nItem: '+post_id)
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
    rows = conn.execute("SELECT id,platform,post_id,recipient,attempts,event FROM notification_outbox WHERE state='pending' AND next_attempt<=? ORDER BY CASE event WHEN 'ai_review' THEN 0 WHEN 'reauth' THEN 1 WHEN 'duplicates' THEN 2 ELSE 3 END,id LIMIT 10", (now,)).fetchall()
    sent = 0
    for key,platform,post_id,recipient,attempts,event in rows:
        if not config.get(event,False):
            with conn:conn.execute("UPDATE notification_outbox SET state='cancelled' WHERE id=?",(key,))
            continue
        try:
            if event=='new_post':sender(recipient,platform,post_id)
            else:sender(recipient,platform,post_id,event=event)
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
