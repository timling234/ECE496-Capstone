/* Same-origin console updates only. Polling never starts provider fetches or AI jobs. */
(() => {
  let busy = false, posting = false, dirty = false, timer;
  const main = () => document.querySelector('main');
  function toast(text, error = false) {
    document.querySelector('.console-toast')?.remove();
    const bar = document.createElement('div');
    bar.className = 'console-toast ' + (error ? 'toast-error' : 'toast-success');
    bar.setAttribute('role', error ? 'alert' : 'status');
    const message = document.createElement('span'); message.textContent = text;
    const close = document.createElement('button'); close.textContent = '×';
    close.setAttribute('aria-label', 'Dismiss notification'); close.onclick = () => bar.remove();
    bar.append(message, close); document.body.append(bar);
    if (!error) setTimeout(() => bar.remove(), 7000);
  }
  function notices(doc) {
    const notice = doc.querySelector('main > .notice');
    const text = notice?.textContent;
    const error = new URL(location.href).searchParams.get('error') === '1';
    notice?.remove();
    if (text) toast(text, error);
  }
  function clean(url) {
    const value = new URL(url); value.searchParams.delete('notice'); value.searchParams.delete('error');
    return value;
  }
  function replace(doc) {
    const fresh = doc.querySelector('main');
    if (!fresh || !main()) return false;
    const y = scrollY; main().replaceWith(fresh); scrollTo(0, y); return true;
  }
  function schedule() {
    clearTimeout(timer);
    if (!main()) return;
    const active = main().dataset.busy === 'true';
    const view = new URL(location.href).searchParams.get('view') || 'dashboard';
    if (active || ['dashboard', 'sources', 'pending', 'testing', 'approved', 'rejected'].includes(view))
      timer = setTimeout(refresh, active ? 3000 : 15000);
  }
  async function refresh() {
    if (document.hidden || busy || posting || dirty || main()?.contains(document.activeElement) && document.activeElement.matches('input,textarea,select')) { schedule(); return; }
    busy = true;
    try {
      const response = await fetch(clean(location.href), {credentials: 'same-origin', signal: AbortSignal.timeout(15000)});
      if (!response.ok || new URL(response.url).pathname !== '/admin') return;
      const doc = new DOMParser().parseFromString(await response.text(), 'text/html');
      const wasRunning = main()?.dataset.busy === 'true';
      if (posting || dirty || main()?.contains(document.activeElement) && document.activeElement.matches('input,textarea,select')) return;
      if (replace(doc) && wasRunning && main().dataset.busy !== 'true')
        toast(main().dataset.failed === 'true' ? 'Task finished with errors. See the results below.' : 'Task finished. Results updated.', main().dataset.failed === 'true');
    } catch (_) { /* Preserve the page through temporary connection failures. */ }
    finally { busy = false; schedule(); }
  }
  document.addEventListener('input', e => { if (e.target.closest('main form')) dirty = true; });
  document.addEventListener('change', e => { if (e.target.closest('main form')) dirty = true; });
  document.addEventListener('submit', async event => {
    const form = event.target;
    if (form.method.toLowerCase() !== 'post') return;
    const url = new URL(form.action);
    if (url.origin !== location.origin || url.pathname.endsWith('/connect') || ['/logout','/linkedin/pages','/linkedin/select'].includes(url.pathname)) return;
    event.preventDefault(); if (posting) return;
    posting = true; clearTimeout(timer);
    const buttons = [...form.querySelectorAll('button')];
    const body = new URLSearchParams(new FormData(form));
    buttons.forEach(button => button.disabled = true);
    try {
      const response = await fetch(url, {method:'POST', body, credentials:'same-origin', headers:{'X-ASAP-Console':'1'}, signal:AbortSignal.timeout(30000)});
      const doc = new DOMParser().parseFromString(await response.text(), 'text/html');
      if (!response.ok) {
        toast(doc.querySelector('p')?.textContent || doc.querySelector('h1')?.textContent || 'Request failed. Please try again.', true);
      } else if (new URL(response.url).pathname === '/admin' && doc.querySelector('main')) {
        const note = doc.querySelector('main > .notice');
        const message = note?.textContent || 'Request accepted.'; note?.remove();
        replace(doc); dirty = false;
        history.replaceState(null, '', clean(response.url)); toast(message);
      } else {
        toast('Your session may have expired. Sign in again to continue.', true);
      }
    } catch (_) { toast('Could not confirm the result. Check the connection before trying again.', true); }
    finally { buttons.forEach(button => button.disabled = false); posting = false; schedule(); }
  });
  notices(document); history.replaceState(null, '', clean(location.href)); schedule();
})();
