# MSRG integration candidate — 2026-11-11

Prepared against the current public [Hugo template](https://github.com/MSRG/msrg.github.io/blob/main/layouts/index.html).
This patch is for review; the MSRG website has not been changed.

The patch adds an optional `site.Params.news.asap_feed_url`. When configured it
uses the approved-only ASAP iframe in the existing News panel, retaining its heading
and LinkedIn link. Without that setting the existing widget continues to render.
Set `asap_feed_url` under the existing `[params.news]` TOML section (or its YAML
counterpart) to the exact public feed URL copied from the intended ASAP workspace.
Do not use the legacy `/feed` unless that legacy workspace is deliberately chosen.

Before installation, agree with Thomas: owning workspace, placement, feed height,
mobile behavior, origin labels and appearance. Use Mock Website to demonstrate
MSRG News / Community layouts, Desktop / Tablet / Mobile widths, Light / Dark
surroundings and 320–1000px iframe heights, link color, font size and source-origin visibility. These controls change only the demo;
the public feed appearance remains in Settings. Parent CSS cannot style a
cross-origin feed. Copy code includes validated appearance parameters in the feed URL and the chosen iframe height. Parameters change only rendering, never stored workspace settings.

Apply the patch in the MSRG repository using `git apply --check` before `git apply`,
configure the URL, build Hugo, and review the resulting site before publishing.
If the website uses CSP, permit `https://asap.surf` in `frame-src`. Feed HTML is
public and requires no credentials or CORS; admin pages retain framing denial.
ASAP sends no social API requests while serving a feed. An existing loaded iframe
shows publication changes on its next load; automatic cross-origin resizing and
live host-site updates require a separately agreed contract.

Rollback: remove the `asap_feed_url` setting to use the existing widget. No source
records, authorization grants or editorial decisions are affected by this patch.
Actual site installation and Thomas acceptance remain pending; no message has
been sent to Thomas.

## Confirmed stakeholder scope

Tim supplied the only Thomas correspondence (September 24, 2026): the replacement
website is the MSRG GitHub Pages project; the iframe should offer colors, font
sizes and showing/hiding the website origin of posts. No additional placement,
resizing protocol or production-installation approval is inferred from that email.
Tim also supplied old/new News screenshots. The MSRG News mock follows the newer
light background, rounded white panel, horizontal cards and LinkedIn footer link.
Like/comment/share controls are not simulated.

Public appearance parameters: `accent=%23215e95`, `font_size=12..24`,
`show_origin=0|1`. Invalid parameters are ignored; content filtering and approval
eligibility are unchanged. Saved Settings appearance is the fallback.

## Mock samples and real test posting

Mock Website defaults to **Fictional sample posts**. Its demonstration page is
explicitly labelled “Mock website for testing purpose” and is not an official
MSRG page. Dedicated original test SVGs and invented research-style text exercise
image cards, long paragraphs and Read more / Hide. Samples are served only at
`/demo-feed`, never inserted into a workspace or served by its real public feed.
Switch Content to Your published posts for the actual approval pipeline. Copy
embed code always targets the workspace's real public feed, even in sample mode.

Tim selected `asaptestlab.bsky.social` for a later single real image-post check.
The current server has no configured test-post app password; identity-only
Bluesky authorization cannot publish. No real social post or fetch has been made
for this increment. Once the dedicated credential is privately configured, use
one labelled test post and one retrieval; do not silently retry or enable polling.
