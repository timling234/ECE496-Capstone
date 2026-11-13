/* Only the embedded same-origin feed may resize this demonstration frame. */
addEventListener('message', event => {
  const frame = document.querySelector('[data-feed-frame]');
  if (!frame || event.source !== frame.contentWindow || event.origin !== location.origin || event.data?.type !== 'asap-feed-height') return;
  const height = Number(event.data.height);
  if (Number.isFinite(height) && height > 0 && height < 50000) frame.style.height = Math.max(Number(frame.dataset.minHeight) || 320, height) + 'px';
});
