(function () {
  var t = document.getElementById('synced'), ago = document.getElementById('ago'), btn = document.getElementById('syncbtn'), msg = document.getElementById('syncmsg');
  function rel() { if (!t) return; var h = (Date.now() - new Date(t.getAttribute('datetime')).getTime()) / 36e5;
    ago.textContent = h < 1 ? '(less than an hour ago)' : '(' + Math.round(h) + ' hours ago)';
    if (h > 9) { ago.textContent += ' · older than usual'; ago.style.color = 'var(--lofg)'; } }
  rel(); setInterval(rel, 60000);
  var polling = null;
  function show(s) {
    if (!s) return;
    if (s.state === 'not_configured') { btn.disabled = true; msg.textContent = 'The Sync button is not switched on yet. Prices still update by themselves every 8 hours.'; return; }
    if (s.state === 'running') { btn.disabled = true; btn.textContent = 'Syncing…'; msg.textContent = 'A sync is running (started ' + new Date(s.started).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + '). It takes about 15–20 minutes; this page reloads by itself when it is done.'; startPoll(); return; }
    btn.disabled = false; btn.textContent = 'Sync now';
    if (s.state === 'failed') msg.textContent = 'The last sync did not finish. The prices shown are from the last good run. Try again, or wait for the next automatic run.';
  }
  function status() { return fetch('/api/status', { cache: 'no-store' }).then(function (r) { return r.json(); }).catch(function () { return null; }); }
  function startPoll() { if (polling) return; polling = setInterval(function () { status().then(function (s) {
    if (s && s.state !== 'running') { clearInterval(polling); polling = null; if (s.state === 'idle') location.reload(); else show(s); } }); }, 30000); }
  if (btn) {
    status().then(show);
    btn.addEventListener('click', function () {
      btn.disabled = true; btn.textContent = 'Starting…'; msg.textContent = '';
      fetch('/api/sync', { method: 'POST' }).then(function (r) { return r.json(); }).then(function (s) {
        if (s.state === 'recent') { btn.disabled = false; btn.textContent = 'Sync now'; msg.textContent = 'A sync finished ' + s.minutes + ' minutes ago. Please wait at least 20 minutes between syncs.'; return; }
        show({ state: s.state === 'started' ? 'running' : s.state, started: s.started || new Date().toISOString() });
      }).catch(function () { btn.disabled = false; btn.textContent = 'Sync now'; msg.textContent = 'Could not start a sync. Please try again.'; });
    });
  }
})();
