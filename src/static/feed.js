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
    if (!texts.length || !button) continue;
    texts.forEach(text => text.classList.add('collapsed'));
    button.onclick = () => {
      const expanded = button.getAttribute('aria-expanded') !== 'true';
      texts.forEach(text => text.classList.toggle('collapsed', !expanded)); button.setAttribute('aria-expanded',String(expanded)); button.textContent = expanded ? 'Hide' : 'Read more'; announceHeight();
    };
    card.querySelector('[data-share]')?.addEventListener('click', async event => {
      const button = event.currentTarget, url = button.dataset.share;
      try { if (navigator.share) await navigator.share({url}); else { await navigator.clipboard.writeText(url); button.querySelector('span').textContent='Copied'; setTimeout(() => button.querySelector('span').textContent='Share',2000); } }
      catch (_) { /* A cancelled share leaves the card unchanged. */ }
    });
  }
  const gallery = document.createElement('dialog'); gallery.className = 'news-gallery';
  gallery.innerHTML = '<div data-gallery-content></div><nav><button type="button" data-gallery-prev aria-label="Previous image">←</button><span data-gallery-count></span><button type="button" data-gallery-next aria-label="Next image">→</button><button type="button" data-gallery-close>Close</button></nav>';
  document.body.append(gallery); let media = [], imageIndex = 0;
  function showImage(index) {
    imageIndex = (index + media.length) % media.length;
    const item = media[imageIndex], element = document.createElement(item.type === 'video' ? 'video' : 'img');
    element.src = item.url;
    if (element.tagName === 'VIDEO') element.controls = true;
    else { element.alt = item.alt || 'Post image'; element.referrerPolicy = 'no-referrer'; }
    gallery.querySelector('[data-gallery-content]').replaceChildren(element);
    gallery.querySelector('[data-gallery-count]').textContent = `${imageIndex + 1} / ${media.length}`;
    gallery.querySelector('[data-gallery-prev]').hidden = gallery.querySelector('[data-gallery-next]').hidden = media.length < 2;
  }
  root.querySelectorAll('[data-gallery]').forEach(link => link.addEventListener('click', event => {
    event.preventDefault(); media = JSON.parse(link.dataset.gallery); showImage(0); gallery.showModal();
  }));
  gallery.querySelector('[data-gallery-prev]').onclick = () => showImage(imageIndex - 1);
  gallery.querySelector('[data-gallery-next]').onclick = () => showImage(imageIndex + 1);
  gallery.querySelector('[data-gallery-close]').onclick = () => gallery.close();
  gallery.addEventListener('close', () => gallery.querySelector('[data-gallery-content]').replaceChildren());
  gallery.addEventListener('keydown', event => { if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') { event.preventDefault(); showImage(imageIndex + (event.key === 'ArrowRight' ? 1 : -1)); } });
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
  root.addEventListener('keydown', event => { if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') { event.preventDefault(); show(page + (event.key === 'ArrowRight' ? 1 : -1)); measure(); } });
  dots.addEventListener('click',measure);
  addEventListener('resize',() => { paginate(); measure(); });
  root.addEventListener('load',measure,true);
  paginate(); requestAnimationFrame(measure);
  new ResizeObserver(announceHeight).observe(root);
})();
