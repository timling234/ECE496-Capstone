"""Approved sapphire editorial homepage and matching account forms."""
from html import escape
from pathlib import Path

STYLE = Path(__file__).with_name('portal.css').read_text(encoding='utf-8')
FULL_NAME = 'Automated Social-media Aggregation Platform'


def header():
    return ('<header class="site-header"><a class="brand" href="/" aria-label="ASAP home">'
            '<span class="brand-mark" aria-hidden="true"></span>ASAP</a>'
            '<nav class="header-nav" aria-label="Account navigation"><a href="/signin">Sign in</a>'
            '<a class="button button-small" href="/register">Get started</a></nav></header>')


def document(title, body):
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta name="theme-color" content="#2e63a5"><title>'+escape(title)+'</title>'
            '<style>'+STYLE+'</style></head><body>'+header()+body+'</body></html>')


def home_page():
    return document('ASAP — '+FULL_NAME, '''
<main class="hero">
  <section class="hero-copy" aria-labelledby="product-name">
    <h1 id="product-name"><span>Automated</span> <span>Social-media</span> <span class="blue">Aggregation Platform</span></h1>
    <p class="hero-description">Collect, review, and share what matters.</p>
    <a class="button" href="/register">Create your feed <span aria-hidden="true">→</span></a>
  </section>
  <figure class="feed-art" aria-label="Example of an approved community news card">
    <div class="card-outline" aria-hidden="true"></div><div class="card-outline second" aria-hidden="true"></div>
    <div class="example-card">
      <img src="/assets/architecture-sapphire-v1.png" width="1672" height="941" alt="Curved blue architectural facade reflecting the sky" fetchpriority="high">
      <div class="example-copy"><p class="example-category">COMMUNITY NEWS</p>
        <h2>Ideas worth sharing.</h2><span class="example-date">NOV 10</span>
      </div>
    </div>
  </figure>
</main>
<footer class="site-footer" aria-label="Workflow">Collect <span aria-hidden="true">/</span> Review <span aria-hidden="true">/</span> Publish</footer>''')


def auth_page(*, register=False, google_ready=False, csrf='', error='', email=''):
    esc = lambda value: escape(str(value), quote=True)
    title = 'Create your ASAP account' if register else 'Sign in to ASAP'
    body = '<main class="auth-main"><section class="auth-box" aria-labelledby="auth-heading">'
    body += '<h1 id="auth-heading">'+('Create your account' if register else 'Welcome back')+'</h1>'
    body += '<p class="auth-context">'+FULL_NAME+'</p>'
    if error:
        body += '<p class="alert" role="alert">'+esc(error)+'</p>'
    if google_ready:
        body += '<a class="google-button" href="/auth/google"><span class="google-mark" aria-hidden="true">G</span>Continue with Google</a>'
    else:
        body += '<button class="google-button" type="button" disabled aria-describedby="google-note"><span class="google-mark" aria-hidden="true">G</span>Continue with Google</button><p class="google-note" id="google-note">Google sign-in is coming soon. You can use email below.</p>'
    body += '<div class="divider">or continue with email</div><form method="post" action="'+('/register' if register else '/signin')+'"><input type="hidden" name="csrf" value="'+esc(csrf)+'">'
    body += '<label class="field" for="email"><span>Email address</span><input id="email" type="email" name="email" value="'+esc(email)+'" maxlength="254" autocomplete="email" placeholder="you@organization.com" required></label>'
    body += '<label class="field" for="password"><span>Password</span><input id="password" type="password" name="password" '+('minlength="12" ' if register else '')+'maxlength="256" autocomplete="'+('new-password' if register else 'current-password')+'" required></label>'
    if register:
        body += '<label class="field" for="confirm-password"><span>Confirm password</span><input id="confirm-password" type="password" name="confirm_password" minlength="12" maxlength="256" autocomplete="new-password" required></label><p class="field-note">Use at least 12 characters to keep your workspace secure.</p>'
    body += '<button class="button submit" type="submit">'+('Create account' if register else 'Sign in')+'<span aria-hidden="true">→</span></button></form>'
    body += '<p class="auth-switch">'+('Already have an account? <a href="/signin">Sign in</a>' if register else 'New to ASAP? <a href="/register">Create an account</a>')+'</p></section></main>'
    return document(title, body)
