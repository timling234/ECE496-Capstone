# Stage 3: local AI review suggestions

The first increment adds **AI review suggestion** to private review cards. Click
it explicitly and refresh results after the local model finishes. The worker
returns Approve, Reject, or Needs review plus a short reason; the existing human
Approve/Reject/Withdraw controls remain the only publication authority. No
scheduled inference or automatic decisions are enabled.

Jarvis uses its already-installed `gemma4:e2b-it-qat` through local Ollama. No model
download, external LLM API, account credentials, or cloud key is required.
`ASAP_LLM_URL=http://host.lima.internal:11434` and `ASAP_LLM_MODEL` select the local
service in private `.env`. A model URL supplied by a browser is never accepted.
The current adapter accepts only localhost / Docker host aliases over HTTP.

A single background slot prevents an unbounded local model queue. Requests require
workspace authentication and CSRF and are throttled. Model timeout is 120 seconds,
output is capped at 64 KiB, redirects/proxies are disabled, and invalid output
becomes an error for manual retry. Read-only page views never invoke a model.

The system prompt treats post text as untrusted input and supplies a conservative,
generic editorial policy. Only post text, platform, and creation time are sent to
the local model; URLs are not fetched, no tools are available, and returned text
is escaped. A schema restricts the recommendation and bounded reason. Text beyond
6,000 characters always requires manual review. This is a baseline suggestion
model, not a demonstrated guarantee of editorial accuracy; tailor and evaluate the
policy before introducing automated decisions.

Each workspace stores immutable request/audit fields in its own SQLite
`ai_suggestions`: content fingerprint, policy, model, actor, timestamps, result or
safe failure. Model advice never writes editorial decisions. Identical unchanged
requests reuse a completed result; changed content marks advice stale, including
changes while the model is running. Startup marks interrupted jobs retryable.
Public feeds never include suggestions. Human decisions retain their existing
separate editorial action audit.

Validation: offline tests cover ownership/CSRF, background execution, caching,
staleness, restart, errors, endpoint limits, response validation, output escaping,
and unchanged publication status. One real **local** inference on a fictional
seminar announcement returned a valid Approve suggestion with a reason; no real
user post was submitted during deployment checks. Future work: workspace-specific
policy, evaluation cases, then explicit opt-in auto approve/reject with audit and
human override.

References: [Ollama chat API](https://docs.ollama.com/api/chat),
[structured output](https://docs.ollama.com/capabilities/structured-outputs).
