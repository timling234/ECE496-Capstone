/* Progressive disclosure: full text remains available when scripting is disabled. */
for (const card of document.querySelectorAll('.news-card')) {
  const text = card.querySelector('.content');
  const button = card.querySelector('[data-read-more]');
  if (!text || !button) continue;
  text.classList.add('collapsed');
  if (text.scrollHeight <= text.clientHeight + 1) { text.classList.remove('collapsed'); continue; }
  button.hidden = false;
  button.addEventListener('click', () => {
    const expanded = button.getAttribute('aria-expanded') !== 'true';
    text.classList.toggle('collapsed', !expanded);
    button.setAttribute('aria-expanded', String(expanded));
    button.textContent = expanded ? 'Hide' : 'Read more';
  });
}
