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
  function focusNotification() {
    const query=new URL(location.href).searchParams;
    const selectors=query.has('reauth_source') ? ['[data-source-key]','sourceKey',query.get('reauth_source')] : query.has('focus_group') ? ['[data-group]','group',query.get('focus_group')] : ['article[data-post-id]','postId',query.get('focus_post')];
    if (!selectors[2]) return;
    const node=[...document.querySelectorAll(selectors[0])].find(node => node.dataset[selectors[1]]===selectors[2] && (!query.has('focus_platform') || node.dataset.platform===query.get('focus_platform')));
    if (node) { node.style.outline='2px solid #80bded'; node.scrollIntoView({block:'center'}); }
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
    if (view === 'mock' || document.querySelector('[data-account-choice]')) return;
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
  function updateMock() {
    const controls = document.querySelector('.mock-controls');
    if (!controls) return;
    const height = Math.round(Math.max(320, Math.min(1000, Number(document.getElementById('mock-height').value) || 620)));
    const width = document.getElementById('mock-width').value;
    const demo = new URL(controls.dataset.demoUrl, location.origin);
    demo.searchParams.set('sample', document.getElementById('mock-content').value === 'sample' ? '1' : '0');
    demo.searchParams.set('template', document.getElementById('mock-template').value);
    demo.searchParams.set('theme', document.getElementById('mock-theme').value);
    demo.searchParams.set('height', height);
    document.getElementById('mock-viewport').style.width = width + 'px';
    const feed = new URL(controls.dataset.feedUrl);
    const appearance = {accent: document.getElementById('mock-accent').value, font_size: Math.round(Math.max(12, Math.min(24, Number(document.getElementById('mock-font').value) || 16))), show_origin: document.getElementById('mock-origin').checked ? '1' : '0'};
    for (const [key, value] of Object.entries(appearance)) { demo.searchParams.set(key, value); feed.searchParams.set(key, value); }
    document.getElementById('mock-open').href = demo.href;
    const frame = document.getElementById('mock-frame'); frame.src = demo.href; frame.style.height = (height + 680) + 'px';
    const code = document.getElementById('mock-code');
    const embed = document.createElement('iframe'); embed.src = feed.href; embed.title = 'ASAP news'; embed.loading = 'lazy';
    embed.setAttribute('style', 'display:block;width:100%;height:' + height + 'px;border:0;border-radius:12px');
    code.value = embed.outerHTML;
  }
  function updateFeed() {
    const controls = document.querySelector('[data-feed-controls]'), list = document.querySelector('[data-feed-preview-list]');
    if (!controls || !list) return;
    const platforms = [...controls.querySelectorAll('input:checked')].map(input => input.value);
    const layout = controls.querySelector('select').value;
    const locationUrl = new URL(location.href); locationUrl.searchParams.set('feed_platforms',platforms.join(',') || 'none'); locationUrl.searchParams.set('feed_layout',layout);
    history.replaceState(null,'',locationUrl);
    const labels = {x:'X',bluesky:'Bluesky',linkedin:'LinkedIn'};
    const groups = layout === 'separate' ? platforms.map(p => [labels[p],[p]]) : [['All selected platforms',platforms]];
    list.replaceChildren();
    if (!platforms.length) { const empty = document.createElement('p'); empty.textContent = 'No platforms selected.'; list.append(empty); return; }
    groups.forEach(([label, selected], index) => {
      const url = new URL(list.dataset.feedUrl); if (selected.length !== 3) url.searchParams.set('platforms',selected.join(','));
      const section = document.createElement('section'); section.className = 'panel';
      const heading = document.createElement('h3'); heading.textContent = label;
      const instruction = document.createElement('p'); instruction.textContent = 'Copy this code into your website:';
      const frame = document.createElement('iframe'); frame.src = url.href; frame.title = label + ' public feed preview'; frame.dataset.publicFeedFrame = '';
      frame.style.cssText = 'display:block;width:100%;max-width:1120px;height:620px;margin:0 auto;border:0';
      const embed = document.createElement('iframe'); embed.setAttribute('src',url.href); embed.title = 'ASAP news'; embed.setAttribute('style','width:100%;height:620px;border:0');
      const code = document.createElement('textarea'); code.id = 'feed-embed-code' + (index ? '-' + index : ''); code.readOnly = true; code.rows = 3; code.setAttribute('aria-label','Feed embed code'); code.style.cssText = 'width:100%;max-width:100%;font-family:monospace'; code.value = embed.outerHTML;
      const copy = document.createElement('button'); copy.type = 'button'; copy.dataset.copy = code.id; copy.textContent = 'Copy embed code';
      const title = document.createElement('h4'); title.textContent = 'Iframe preview';
      section.append(heading,instruction,code,copy,title,frame); list.append(section);
    });
  }
  document.addEventListener('change', event => {
    if (event.target.closest('[data-feed-controls]')) updateFeed();
    else if (event.target.closest('.mock-controls')) updateMock();
  });
  document.addEventListener('click', async event => {
    const multi = event.target.closest('[data-multi-select]');
    if (multi) {
      const active = multi.getAttribute('aria-pressed') !== 'true';
      multi.setAttribute('aria-pressed', String(active)); multi.textContent = active ? 'Cancel selection' : 'Select posts';
      document.getElementById('post-bulk').hidden = !active;
      document.querySelectorAll('.post-select').forEach(label => { label.hidden = !active; label.querySelector('input').checked = false; });
      dirty = active; updateSelection(); return;
    }
    const button = event.target.closest('[data-copy]');
    if (!button) return;
    const field = document.getElementById(button.dataset.copy);
    try { await navigator.clipboard.writeText(field.value); toast('Embed code copied.'); }
    catch (_) { field.focus(); field.select(); toast('Code selected. Copy it using your keyboard.', true); }
  });
  addEventListener('message', event => {
    const frame = [...document.querySelectorAll('[data-public-feed-frame]')].find(node => node.contentWindow === event.source);
    if (!frame || event.source !== frame.contentWindow || event.origin !== location.origin || event.data?.type !== 'asap-feed-height') return;
    const height = Number(event.data.height);
    if (Number.isFinite(height) && height > 0 && height < 50000) frame.style.height = Math.max(620, height) + 'px';
  });
  function updateSelection() {
    const boxes = [...document.querySelectorAll('.post-select input')];
    const count = boxes.filter(box => box.checked).length;
    const all = document.querySelector('[data-select-all]');
    if (all) { all.checked = boxes.length > 0 && count === boxes.length; all.indeterminate = count > 0 && count < boxes.length; }
    const label = document.querySelector('[data-selection-count]'); if (label) label.textContent = count + ' selected';
  }
  document.addEventListener('change', e => {
    if (e.target.matches('[data-select-all]')) document.querySelectorAll('.post-select input').forEach(box => box.checked = e.target.checked);
    if (e.target.matches('[data-select-all],.post-select input')) { dirty = true; updateSelection(); }
  });
  document.addEventListener('input', e => { if (e.target.closest('main form')) dirty = true; });
  document.addEventListener('change', e => { if (e.target.closest('main form')) dirty = true; });
  document.addEventListener('change', event => {
    if (event.target.matches('[data-auto-submit]') || event.target.form?.matches('[data-auto-save]')) {
      const form=event.target.form;
      if (event.target.type==='checkbox') form.dataset.autoCheckbox=event.target.name;
      form.requestSubmit();
    }
  });
  document.addEventListener('submit', async event => {
    const form = event.target;
    if (form.method.toLowerCase() !== 'post') return;
    const url = new URL(form.action);
    if (url.origin !== location.origin || url.pathname.endsWith('/connect') || ['/logout','/linkedin/pages','/linkedin/select'].includes(url.pathname)) return;
    event.preventDefault(); if (posting) return;
    posting = true; clearTimeout(timer);
    const buttons = [...form.querySelectorAll('button')];
    const body = new URLSearchParams(new FormData(form));
    if (event.submitter?.name) body.set(event.submitter.name, event.submitter.value);
    const automatic = form.dataset.autoCheckbox;
    const switches = [...document.querySelectorAll('[data-auto-submit],form[data-auto-save] input,form[data-auto-save] select,form[data-auto-save] textarea')].filter(input => !input.disabled);
    let saved = false;
    switches.forEach(input => input.disabled = true);
    buttons.forEach(button => button.disabled = true);
    try {
      const response = await fetch(url, {method:'POST', body, credentials:'same-origin', headers:{'X-ASAP-Console':'1'}, signal:AbortSignal.timeout(30000)});
      const doc = new DOMParser().parseFromString(await response.text(), 'text/html');
      if (!response.ok) {
        toast(doc.querySelector('p')?.textContent || doc.querySelector('h1')?.textContent || 'Request failed. Please try again.', true);
      } else if (new URL(response.url).pathname === '/admin' && doc.querySelector('main')) {
        const note = doc.querySelector('main > .notice');
        const message = note?.textContent || 'Request accepted.'; note?.remove();
        saved = true; replace(doc); dirty = false;
        history.replaceState(null, '', clean(response.url)); toast(message);
      } else {
        toast('Your session may have expired. Sign in again to continue.', true);
      }
    } catch (_) { toast('Could not confirm the result. Check the connection before trying again.', true); }
    finally {
      if (automatic && !saved) { const input = form.elements.namedItem(automatic); if (input?.type === 'checkbox') input.checked = input.defaultChecked; }
      if (!saved) form.querySelectorAll('input[type=radio]').forEach(input => input.checked = input.defaultChecked);
      delete form.dataset.autoCheckbox;
      switches.forEach(input => input.disabled = false);
      buttons.forEach(button => button.disabled = false); posting = false; schedule();
    }
  });
  focusNotification(); notices(document); history.replaceState(null, '', clean(location.href)); schedule();
})();
