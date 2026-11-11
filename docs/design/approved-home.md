# Approved ASAP homepage

The user approved the sapphire editorial concept on 2026-11-10, after reviewing
several alternatives. Preserve this direction when making future visual edits.

- Official name: **Automated Social-media Aggregation Platform**.
- Large three-line serif heading: Automated / Social-media / Aggregation Platform.
- One supporting sentence: “Collect, review, and share what matters.”
- Sapphire blue `#2e63a5`, dark navy `#0c1535`, white, pale blue `#e4eef8`.
- Original offset-block ASAP mark; Sign in / Get started navigation.
- Main CTA: Create your feed, linking to registration.
- A blue architectural news example in a white card, subtle stacked outlines and
  pale-blue circular backdrop. It is illustrative content, not a live post.
- Bottom line: Collect / Review / Publish.
- No PawSense visual style, extra orange accents, feature grids or dense copy.
- The public homepage is separate from the matching sign-in/registration forms.

Implementation: `src/portal_ui.py`, `src/portal.css`; Flask serves only the local
public asset folder at `/assets`. The image is
`src/static/architecture-sapphire-v1.png`. Static assets have one-day public caching;
account pages and cookies retain existing security controls. No authentication,
provider, credentials, Store schema or source polling behavior was changed.

## Asset provenance

Generated with the built-in imagegen tool from the user's approved concept. The
full source concept is `exec-96af1c0a-4dca-40f1-b022-68c1a6dca903.png` in the session
image directory. The derived image is an architectural illustration for the example
card, not a photograph of an identified customer's premises.

Final asset prompt:

> Extract/recreate ONLY the architectural photograph inside the right news card of the supplied approved website concept, as a clean standalone photographic website asset. The output must be JUST the same sweeping modern curved building facade with sapphire / steel blue metal panels and reflective glass windows, natural clear blue sky and soft white cloud reflections. Closely preserve the photograph's composition and architectural shapes, the curved facade runs diagonally from lower left toward upper right, sophisticated natural muted sapphire color grading, luminous real daylight. Landscape 16:9 crop. Edge-to-edge photograph, no white borders, no rounded corners, no UI card, no drop shadow, no circle, no text, no logo, no buttons, no watermark. This asset will be placed into the actual HTML implementation of the approved card. Do not render the full website or include any surrounding design. Photorealistic architectural photography, crisp detail, restrained beautiful blues consistent with the supplied image.

## Verification

- 117 offline regression tests passed in Docker; final account suite passed again
  after the presentation fixes.
- Browser inspected the same rendered homepage at desktop and 390px mobile widths,
  plus matching mobile sign-in/registration pages, using a preview containing no
  real identities, sessions or credentials.
- 320px DOM geometry verified document width equals viewport width (no horizontal
  overflow). The header omits its redundant registration shortcut only at this
  smallest width; the main registration CTA remains available.
- The initially overstretched photo found during browser inspection was corrected
  with intrinsic dimensions and `height:auto`.
- No actual platform API request or SMTP delivery is needed for this presentation
  change. Google live sign-in acceptance remains a separate pending user action.

Production HTTPS acceptance passed for `/`, `/signin`, `/register`, `/feed`,
`/embed-demo`, the exact image bytes and static cache policy, original admin login
and Secure cookie, and the unchanged local Google authorization redirect. The
full pre-deployment data archive is
`/data/backups/stage2-20261111T034848Z/`, also copied to the private host backup
folder. The prior image remains `jarvis-asap-stage2:before-approved-home`.
