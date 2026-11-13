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
    const text = card.querySelector('.content'), button = card.querySelector('[data-read-more]');
    if (!text || !button) continue;
    text.classList.add('collapsed');
    button.onclick = () => {
      const expanded = button.getAttribute('aria-expanded') !== 'true';
      text.classList.toggle('collapsed', !expanded); button.setAttribute('aria-expanded',String(expanded)); button.textContent = expanded ? 'Hide' : 'Read more'; announceHeight();
    };
    card.querySelector('[data-share]')?.addEventListener('click', async event => {
      const button = event.currentTarget, url = button.dataset.share;
      try { if (navigator.share) await navigator.share({url}); else { await navigator.clipboard.writeText(url); button.querySelector('span').textContent='Copied'; setTimeout(() => button.querySelector('span').textContent='Share',2000); } }
      catch (_) { /* A cancelled share leaves the card unchanged. */ }
    });
  }
  function measure() {
    root.querySelectorAll('.news-page:not([hidden]) .news-card').forEach(card => {
      const text = card.querySelector('.content'), button = card.querySelector('[data-read-more]');
      if (!text || !button) return;
      button.hidden = button.getAttribute('aria-expanded') !== 'true' && text.scrollHeight <= text.clientHeight + 1;
    });
    announceHeight();
  }
  root.querySelector('.news-prev').onclick = () => { show(page - 1); measure(); };
  root.querySelector('.news-next').onclick = () => { show(page + 1); measure(); };
  root.addEventListener('keydown', event => { if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') { event.preventDefault(); show(page + (event.key === 'ArrowRight' ? 1 : -1)); measure(); } });
  dots.addEventListener('click',measure);
  addEventListener('resize',() => { paginate(); measure(); });
  root.addEventListener('load',measure,true);
  paginate(); requestAnimationFrame(measure);
  new ResizeObserver(announceHeight).observe(root);
})();
