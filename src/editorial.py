"""Internal selection service for Option A; no UI, authentication or publishing."""

from datetime import datetime, timezone


class SelectionConflict(ValueError):
    """Another representative already has approval; replacement is not defined."""


def table_exists(conn, name):
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


# FR-6/FR-7: Explicit editorial decisions, independently stored from provenance
def get_group_approval(conn, group_id):
    """Read the recorded decision, not an authorization or public-feed query."""
    if not table_exists(conn, "group_approvals"):
        return None
    row = conn.execute("""SELECT group_id,platform,post_id,approved_by,approved_at
        FROM group_approvals WHERE group_id=?""", (group_id,)).fetchone()
    return dict(zip(("group_id", "platform", "post_id", "approved_by", "approved_at"), row)) if row else None


# FR-6/FR-7: Administrator-selected representative (Option A; independent code)
def approve_representative(conn, group_id, platform, post_id, actor):
    """Record one explicit approval for a current duplicate-candidate group.

    Caller supplies a trusted actor identity and owns commit/rollback. This
    internal API does not authenticate administrators. Only current stored
    review candidates are eligible. Repeating the same choice is idempotent;
    conflicting choices are blocked until a replacement workflow is decided.
    Group membership, source rows and legacy publication fields are untouched.
    """
    if not isinstance(actor, str) or not actor.strip():
        raise ValueError("A decision actor is required")
    if not all(table_exists(conn, name) for name in ("posts", "relevance", "duplicate_candidates")):
        raise ValueError("No processed duplicate group available")
    # Start a consistent transaction for membership checks and insertion.
    if not conn.in_transaction:
        conn.execute("BEGIN")
    rows = conn.execute("""SELECT p.platform,p.post_id FROM duplicate_candidates d
        JOIN posts p USING(platform,post_id)
        JOIN relevance r USING(platform,post_id)
        WHERE d.group_id=? AND r.status='candidate'""", (group_id,)).fetchall()
    members = {(row[0], row[1]) for row in rows}
    if len(members) < 2 or (platform, post_id) not in members:
        raise ValueError("Selection must be a current review candidate in this duplicate group")
    existing = get_group_approval(conn, group_id)
    if existing:
        if (existing["platform"], existing["post_id"]) == (platform, post_id):
            return existing
        raise SelectionConflict("Group already has a representative; replacement is not implemented")
    conn.execute("""CREATE TABLE IF NOT EXISTS group_approvals (
        group_id TEXT PRIMARY KEY NOT NULL,
        platform TEXT NOT NULL, post_id TEXT NOT NULL,
        approved_by TEXT NOT NULL, approved_at TEXT NOT NULL,
        UNIQUE(platform,post_id)
    )""")
    conn.execute("INSERT INTO group_approvals VALUES (?,?,?,?,?)",
                 (group_id, platform, post_id, actor.strip(), datetime.now(timezone.utc).isoformat()))
    return get_group_approval(conn, group_id)
