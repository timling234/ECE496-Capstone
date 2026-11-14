/* Same-origin iframe host: show a source's post stream above the embedded feed. */
(() => {
  window.asapStreamHost = true;
  let dialog;
  addEventListener('message', event => {
    if (event.origin !== location.origin) return;
    if (event.data?.type === 'asap-close-post-stream' && dialog?.querySelector('iframe')?.contentWindow === event.source) { dialog.close(); return; }
    if (event.data?.type !== 'asap-open-post-stream') return;
    const frame = [...document.querySelectorAll('iframe')].find(node => node.contentWindow === event.source);
    if (!frame) return;
    const url = new URL(frame.src, location.href);
    if (url.origin !== location.origin || !/\/(feed|demo-feed|embed-demo)$/.test(url.pathname)) return;
    const data = event.data;
    if (![data.postId, data.platform, data.account].every(value => typeof value === 'string' && value.length > 0 && value.length <= 512)) return;
    // Forward through a Mock Website nested inside the workspace preview.
    try { if (parent !== window && parent.asapStreamHost) { parent.postMessage(data, location.origin); return; } } catch (_) {}
    if (url.pathname.endsWith('/embed-demo')) url.pathname = url.searchParams.get('sample') === '1' ? '/demo-feed' : url.pathname.replace(/\/embed-demo$/, '/feed');
    url.searchParams.set('stream','1'); url.searchParams.set('focus',data.postId);
    url.searchParams.set('platform',data.platform); url.searchParams.set('account',data.account);
    if (!dialog) {
      const style = document.createElement('style');
      style.textContent = '.asap-post-stream{position:fixed;inset:0;width:min(660px,100vw);height:calc(100dvh - 24px);max-width:100vw;max-height:100dvh;margin:auto;padding:0;border:0;border-radius:8px;background:white;overflow:hidden}.asap-post-stream::backdrop{background:#000b}.asap-post-stream iframe{display:block;width:100%;height:100%;border:0;border-radius:0}.asap-post-stream-close{position:absolute;right:8px;top:8px;z-index:2;width:30px;height:30px;padding:0;border:0;border-radius:50%;background:#172536dd;color:white;font:24px Arial;cursor:pointer}';
      document.head.append(style); dialog = document.createElement('dialog'); dialog.className = 'asap-post-stream';
      const close = document.createElement('button'); close.className = 'asap-post-stream-close'; close.textContent = '×'; close.setAttribute('aria-label','Close post list'); close.onclick = () => dialog.close(); dialog.append(close);
      dialog.addEventListener('close', () => dialog.querySelector('iframe')?.remove());
      document.body.append(dialog);
    }
    dialog.querySelector('iframe')?.remove(); const content = document.createElement('iframe'); content.title = 'All posts from this source'; content.src = url.href; dialog.append(content);
    if (!dialog.open) dialog.showModal();
  });
})();
