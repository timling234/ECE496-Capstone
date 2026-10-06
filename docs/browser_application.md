# Browser application

From the ECE496 repository root:

```powershell
python run_app.py
```

If `ASAP_ADMIN_PASSWORD` is already set, it is used. Otherwise enter a password at the hidden terminal prompt; the launcher places it in this process's environment for this run. It is never saved, printed or included in SQLite. Sign in with that same password. There is one administrator (`admin`), no registration and no SSO. Sessions expire after eight hours and do not survive server restart. Cookies are HttpOnly and SameSite Strict; every write requires CSRF validation. The server binds only to loopback HTTP. Public hosting needs a separate HTTPS deployment setup.

- Admin: http://localhost:5000/admin
- Public feed: http://localhost:5000/feed
- Mock embedding page: http://localhost:5000/embed-demo

The default database is the existing `.tmp/store_poc.sqlite3`, containing the previously fetched X/Bluesky posts. `--db PATH` selects another Store; `--port NUMBER` changes the port. Launch does not fetch APIs. It initializes separate derived/editorial tables and reprocesses stored candidates with current MVP rules; original source rows are retained.

## Try it

1. Sign in and open Pending / Needs Review.
2. Approve a post, open the Public feed, and see it appear.
3. In Approved, withdraw or reject it; refresh the feed and see it disappear.
4. In Duplicate Groups, select & approve one member. Only that member is publishable. Selecting another member atomically switches the representative.
5. Create a manual announcement. It starts pending. Approve it to publish; editing requires review again. Previous manual text is retained.
6. Approved items support pin/unpin and a numeric manual order. Smaller positive numbers come first; 0 uses newest-first. Pins come before unpinned items.
7. Feed appearance changes link color, font size and origin visibility without modifying stored source/editorial data.
8. Source configuration saves account/enabled/interval settings to the database directory's `polling.local.json`. Restart the separate polling worker with this file to apply changes. Saving is not a live fetch. The existing token file reference is preserved and its contents are never displayed.

Source configuration worker example (explicit live requests):

```powershell
python run_polling.py --config .tmp/polling.local.json --db .tmp/store_poc.sqlite3 --live
```

LinkedIn remains planned and externally pending. The mock page is not a production MSRG integration.

## Verification

```powershell
python run_tests.py
python run_demo.py
```

73 tests pass. HTTP acceptance tests exercise login, CSRF refusal, favicon-session regression, publication/withdrawal, configuration, iframe route, duplicate switching, manual lifecycle, ordering and presentation separation. Browser checks verified real stored content using a disposable copied database, preserving the original database's source records.
