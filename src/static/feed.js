/* Paginated news, isolated expansion, and real outbound social actions. */
(() => {
  const root = document.querySelector('.news-carousel');
  if (!root) return;
  const cards = [...root.querySelectorAll('.news-card')];
  const host = root.querySelector('.news-pages'), dots = root.querySelector('.news-dots');
  let page = 0, size = 0, pages = [];
  function announceHeight() {
    if (parent !== window) parent.postMessage({type:'asap-feed-height',height:Math.ceil(root.getBoundingClientRect().bottom + scrollY + 4)}, '*');
  }
  function show(next) {
    page = Math.max(0, Math.min(pages.length - 1, next));
    pages.forEach((node, i) => node.hidden = i !== page);
    [...dots.children].forEach((button, i) => { if (i === page) button.setAttribute('aria-current','page'); else button.removeAttribute('aria-current'); });
    root.querySelector('.news-prev').hidden = page === 0;
    root.querySelector('.news-next').hidden = page >= pages.length - 1;
    root.querySelector('[data-page-status]').textContent = pages.length ? `Page ${page + 1} of ${pages.length}` : '';
    announceHeight();
  }
  function paginate() {
    const next = innerWidth <= 560 ? 1 : innerWidth <= 900 ? 2 : 4;
    if (next === size) return;
    const first = page * (size || next); size = next; pages = []; host.replaceChildren(); dots.replaceChildren();
    for (let i = 0; i < cards.length; i += size) {
      const node = document.createElement('div'); node.className = 'news-page'; node.append(...cards.slice(i,i + size)); host.append(node); pages.push(node);
      const button = document.createElement('button'); button.type = 'button'; button.setAttribute('aria-label',`Page ${pages.length}`);
      const index = pages.length - 1; button.onclick = () => show(index); dots.append(button);
    }
    show(Math.floor(first / size));
  }
  for (const card of cards) {
    const texts = [...card.querySelectorAll('.content')], button = card.querySelector('[data-read-more]');
    if (texts.length && button) {
    texts.forEach(text => text.classList.add('collapsed'));
    button.onclick = () => {
      const expanded = button.getAttribute('aria-expanded') !== 'true';
      texts.forEach(text => text.classList.toggle('collapsed', !expanded)); button.setAttribute('aria-expanded',String(expanded)); button.textContent = expanded ? 'Hide' : 'Read more'; announceHeight();
    };
    }
    card.querySelector('[data-share]')?.addEventListener('click', async event => {
      const button = event.currentTarget, url = button.dataset.share;
      try { if (navigator.share) await navigator.share({url}); else { await navigator.clipboard.writeText(url); button.querySelector('span').textContent='Copied'; setTimeout(() => button.querySelector('span').textContent='Share',2000); } }
      catch (_) { /* A cancelled share leaves the card unchanged. */ }
    });
  }
  const query = new URLSearchParams(location.search), streamMode = query.get('stream') === '1';
  function sameSource(card, source) { return card.dataset.platform === source.platform && card.dataset.accountId === source.account; }
  function expandStream(nodes, host) {
    nodes.forEach(card => {
      card.querySelectorAll('.content').forEach(text => text.classList.remove('collapsed'));
      card.querySelectorAll('[data-read-more]').forEach(button => button.remove());
      const link = card.querySelector('[data-gallery]');
      if (link) {
        const media = JSON.parse(link.dataset.gallery), box = document.createElement('div'); box.className = 'news-media news-stream-media';
        let index = 0;
        const content = document.createElement('div'); box.append(content);
        function display(next) {
          index = (next + media.length) % media.length;
          const item = media[index], image = document.createElement(item.type === 'video' ? 'video' : 'img'); image.src = item.url;
          if (image.tagName === 'VIDEO') { image.controls = true; image.preload = 'none'; }
          else { image.alt = item.alt || 'Post image'; image.loading = 'lazy'; image.referrerPolicy = 'no-referrer'; }
          content.replaceChildren(image);
        }
        if (media.length > 1) for (const step of [-1,1]) {
          const button = document.createElement('button'); button.type = 'button'; button.className = 'news-stream-photo ' + (step < 0 ? 'previous' : 'next'); button.textContent = step < 0 ? '‹' : '›';
          button.setAttribute('aria-label', step < 0 ? 'Previous photo' : 'Next photo'); button.onclick = () => display(index + step); box.append(button);
        }
        display(0); link.replaceWith(box);
      }
      // Cloned grid cards need their own functional Share action.
      if (!streamMode) card.querySelector('[data-share]')?.addEventListener('click', async event => {
        const url = event.currentTarget.dataset.share;
        try { if (navigator.share) await navigator.share({url}); else await navigator.clipboard.writeText(url); } catch (_) {}
      });
      host.append(card);
    });
  }
  function focusPost(host, id, scroller) {
    const target = [...host.querySelectorAll('.news-card')].find(card => card.dataset.postId === id);
    if (!target) return;
    requestAnimationFrame(() => {
      if (scroller) scroller.scrollTop += target.getBoundingClientRect().top - scroller.getBoundingClientRect().top;
      else target.scrollIntoView({block:'start'});
      target.focus({preventScroll:true});
    });
  }
  function openStream(card) {
    const source = {type:'asap-open-post-stream',postId:card.dataset.postId,platform:card.dataset.platform,account:card.dataset.accountId};
    try { if (parent !== window && parent.asapStreamHost) { parent.postMessage(source,location.origin); return; } } catch (_) {}
    const dialog = document.createElement('dialog'); dialog.className = 'news-post-stream';
    const close = document.createElement('button'); close.className = 'news-stream-close'; close.textContent = '×'; close.setAttribute('aria-label','Close post list'); close.onclick = () => dialog.close();
    const scroller = document.createElement('div'); scroller.className = 'news-stream-scroller';
    const list = document.createElement('div'); list.className = 'news-stream-list'; scroller.append(list); dialog.append(close,scroller);
    expandStream(cards.filter(item => sameSource(item,source)).map(item => item.cloneNode(true)),list);
    dialog.addEventListener('close',() => { dialog.remove(); card.focus({preventScroll:true}); });
    document.body.append(dialog); dialog.showModal(); focusPost(list,source.postId,scroller);
  }
  root.addEventListener('click', event => {
    if (streamMode) return;
    const card = event.target.closest('.news-card'); if (!card) return;
    const functional = event.target.closest('button,input,textarea,select,video,a');
    if (functional && !functional.matches('a.news-media')) return;
    if (window.getSelection()?.toString()) return;
    event.preventDefault(); openStream(card);
  });
  root.addEventListener('keydown', event => {
    if (!streamMode && event.target.matches('.news-card') && (event.key === 'Enter' || event.key === ' ')) { event.preventDefault(); openStream(event.target); }
  });
  function measure() {
    root.querySelectorAll('.news-page:not([hidden]) .news-card').forEach(card => {
      const texts = [...card.querySelectorAll('.content')], button = card.querySelector('[data-read-more]');
      if (!texts.length || !button) return;
      button.hidden = button.getAttribute('aria-expanded') !== 'true' && !texts.some(text => text.scrollHeight > text.clientHeight + 1);
    });
    announceHeight();
  }
  root.querySelector('.news-prev').onclick = () => { show(page - 1); measure(); };
  root.querySelector('.news-next').onclick = () => { show(page + 1); measure(); };
  root.addEventListener('keydown', event => { if (streamMode) return; if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') { event.preventDefault(); show(page + (event.key === 'ArrowRight' ? 1 : -1)); measure(); } });
  dots.addEventListener('click',measure);
  addEventListener('resize',() => { if (!streamMode) { paginate(); measure(); } });
  root.addEventListener('load',measure,true);
  if (streamMode) {
    root.classList.add('news-stream-mode');
    const list = document.createElement('div'); list.className = 'news-stream-list';
    const source = {platform:query.get('platform'),account:query.get('account')};
    const selected = source.platform && source.account ? cards.filter(card => sameSource(card,source)) : cards;
    expandStream(selected,list); host.replaceChildren(list);
    root.querySelector('.news-prev').hidden = root.querySelector('.news-next').hidden = true; dots.hidden = true;
    focusPost(list,query.get('focus'));
    addEventListener('keydown', event => { if (event.key === 'Escape' && parent !== window) parent.postMessage({type:'asap-close-post-stream'},location.origin); });
  } else { paginate(); requestAnimationFrame(measure); }
  new ResizeObserver(announceHeight).observe(root);
})();
