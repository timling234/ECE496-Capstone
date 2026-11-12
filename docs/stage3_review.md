# Stage 3: local AI review

Settings → Local AI lists installed local Ollama models and a small download catalog.
Download runs in the background; progress updates automatically, then select the installed
model and Apply. Model files are shared on the server; model selection, editorial
policy, action permissions and batch limit belong to each workspace. Cloud models
are excluded. The operator sets the local service URL in private environment
configuration; browser requests cannot supply a service URL or arbitrary model tag.

Individual cards and Suggest for queue generate
Approve / Reject / Needs review with reasons. To execute decisions, explicitly
select automatic approve and/or reject in Settings, then click Run automatic
review. This starts one bounded batch, not continuous unattended moderation.
Both permissions are checked by default; saved choices are preserved. No decisions run merely by opening a page. Existing human controls remain available.

Possible duplicates are analyzed together, with at most one selected representative.
Approving a pending representative and rejecting alternatives requires both action
permissions. An existing published representative can be preserved while pending
duplicates are rejected. Uncertain, oversized or inconsistent groups require manual
review. Completed human decisions are preserved. Content, group membership,
editorial decisions or settings changing during inference prevent stale execution.
Group actions commit atomically. Stop batch prevents further application; it does
not undo already committed decisions or immediately unload an active inference.

Each workspace SQLite stores settings, suggestions, batch progress, download status
and automation audit records with model, policy, reasons, actor and timestamps.
Identical unchanged analysis is reused. Public feeds never display private AI
advice. Restarted jobs are marked interrupted rather than replayed. Posts are
untrusted model input; the model has no tools, and output is validated and escaped.

One shared inference slot and one shared download slot bound background activity.
Authenticated POST routes require CSRF and rate limits. Download tags are
allowlisted; transport rejects redirects and proxies. Downloads use the server disk
and bandwidth and are not automatically applied.

Validation used targeted offline checks for workspace isolation, settings,
mocked downloads, guarded execution and duplicate transactions. One real local
inference used two fictional duplicate posts in a disposable database and approved
one while rejecting the other. No production posts were automatically moderated,
no new model was downloaded, and no social API was called for this increment.

References: [Ollama chat API](https://docs.ollama.com/api/chat),
[structured output](https://docs.ollama.com/capabilities/structured-outputs),
[model downloads](https://docs.ollama.com/api/pull).

Deployment note: the current Mac is temporary hosting. Migration of the website,
workspace databases, credentials and local models to a delivery server is deferred
until project handover. User-facing wording uses “Server”.

Console forms show success/error notifications over the current page. Background
progress updates use authenticated same-origin page reads; they never trigger
provider retrieval or model inference. Updates pause while editing a form.

Settings no longer displays the automatic review history list. Audit records
remain stored; per-post reasons and review batch progress remain available.
