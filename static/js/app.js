/* ==========================================================================
   Site Link Finder — front-end logic
   Sections: helpers · state · mode picker · run control · polling ·
             rendering · download
   ========================================================================== */

(function () {
  'use strict';

  /* ------------------------------------------------------------------------
     Helpers
     ------------------------------------------------------------------------ */
  const $ = (id) => document.getElementById(id);

  const escapeHtml = (value) =>
    String(value ?? '').replace(/[&<>"]/g, (c) =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  const linkTo = (url) =>
    `<a href="${escapeHtml(url)}" target="_blank" rel="noopener">${escapeHtml(url)}</a>`;

  const isDead = (status) =>
    typeof status === 'string' || (typeof status === 'number' && status >= 400);

  const POLL_INTERVAL_MS = 700;

  /* ------------------------------------------------------------------------
     State
     ------------------------------------------------------------------------ */
  const state = {
    logIndex: 0,     // how many log lines are already rendered
    pollTimer: null,
    results: null,   // { hits, broken, pages }
    activeTab: null
  };

  /* ------------------------------------------------------------------------
     Mode picker
     ------------------------------------------------------------------------ */
  const currentMode = () =>
    document.querySelector('input[name=mode]:checked').value;

  function applyMode() {
    const mode = currentMode();
    const needsQuery = mode === 'search';
    $('queryField').hidden = !needsQuery;
    $('matchRow').hidden = !needsQuery;
    // the orphan report only makes sense while auditing broken links
    $('orphanCheck').hidden = mode !== 'broken';
  }

  document.querySelectorAll('.mode').forEach((card) => {
    card.addEventListener('click', () => {
      document.querySelectorAll('.mode').forEach((c) => c.classList.remove('is-active'));
      card.classList.add('is-active');
      card.querySelector('input').checked = true;
      applyMode();
    });
  });

  /* ------------------------------------------------------------------------
     Run control
     ------------------------------------------------------------------------ */
  function collectPayload() {
    return {
      domain:  $('domain').value.trim(),
      mode:    currentMode(),
      query:   $('query').value.trim(),
      match:   $('match').value,
      workers: $('workers').value,
      delay:   $('delay').value,
      exclude: $('exclude').value,
      max_depth: $('max_depth').value === '' ? null : $('max_depth').value,
      include_subdomains: $('include_subdomains').checked,
      use_sitemap:        $('use_sitemap').checked,
      use_crawl:          $('use_crawl').checked,
      check_external:     $('check_external').checked,
      check_assets:       $('check_assets').checked,
      search_raw_html:    $('search_raw_html').checked,
      find_orphans:       $('find_orphans').checked
    };
  }

  async function start() {
    const payload = collectPayload();

    if (!payload.domain) {
      alert('Enter a site domain');
      return;
    }
    if (payload.mode === 'search' && !payload.query) {
      alert('Enter the link you are looking for');
      return;
    }

    const response = await fetch('/api/start', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
    const result = await response.json();

    if (!result.ok) {
      alert(result.error || 'Could not start');
      return;
    }

    state.logIndex = 0;
    state.results = null;
    state.activeTab = null;

    $('log').textContent = '';
    $('progressCard').hidden = false;
    $('resultsCard').hidden = true;
    $('bar').classList.add('is-indeterminate');
    $('startBtn').disabled = true;
    $('stopBtn').disabled = false;

    clearInterval(state.pollTimer);
    state.pollTimer = setInterval(poll, POLL_INTERVAL_MS);
    poll();
  }

  function stop() {
    fetch('/api/stop', { method: 'POST' });
    $('stopBtn').disabled = true;
  }

  /* ------------------------------------------------------------------------
     Polling
     ------------------------------------------------------------------------ */
  async function poll() {
    let status;
    try {
      status = await (await fetch('/api/status?since=' + state.logIndex)).json();
    } catch (e) {
      return; // server restarting — try again on the next tick
    }

    showVersion(status.version);
    appendLog(status);
    updateBar(status);

    if (!status.running) {
      clearInterval(state.pollTimer);
      state.pollTimer = null;
      $('startBtn').disabled = false;
      $('stopBtn').disabled = true;
      $('bar').classList.remove('is-indeterminate');
      $('bar').querySelector('i').style.width = '100%';

      if (status.summary || status.error) renderResults(status);
    }
  }

  function appendLog(status) {
    if (!status.log || !status.log.length) return;

    const box = $('log');
    const atBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 60;

    box.textContent += status.log.join('\n') + '\n';
    state.logIndex = status.log_len;

    if (atBottom) box.scrollTop = box.scrollHeight;
  }

  function updateBar(status) {
    if (!status.total) return;
    $('bar').classList.remove('is-indeterminate');
    $('bar').querySelector('i').style.width =
      Math.min(100, (status.done / status.total) * 100) + '%';
  }

  function showVersion(version) {
    if (version) $('version').textContent = 'version ' + version;
  }

  /* ------------------------------------------------------------------------
     Rendering: stats and tabs
     ------------------------------------------------------------------------ */
  function renderResults(status) {
    const summary = status.summary || {};
    state.results = status.results || { hits: [], broken: [], pages: [], orphans: [] };
    state.results.orphans = state.results.orphans || [];

    $('resultsCard').hidden = false;
    $('errorBox').innerHTML = status.error
      ? `<div class="error-box">Error: ${escapeHtml(status.error)}</div>`
      : '';

    renderStats(summary);
    renderTabs(summary);

    $('filter').value = '';
    renderTable();
    $('resultsCard').scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function statTile(value, label, modifier) {
    return `<div class="stat ${modifier || ''}">
      <div class="stat__value">${value}</div>
      <div class="stat__label">${label}</div>
    </div>`;
  }

  function renderStats(summary) {
    const tiles = [
      statTile(summary.pages ?? 0, 'pages crawled'),
      statTile((summary.links ?? 0).toLocaleString('en-US'), 'links collected')
    ];

    if (summary.mode === 'search' || summary.mode === 'full') {
      tiles.push(statTile(
        summary.hits ?? 0,
        `matches on ${summary.hit_pages ?? 0} pages`,
        summary.hits ? 'stat--good' : 'stat--warn'
      ));
    }

    if (summary.mode === 'broken' || summary.mode === 'full') {
      tiles.push(statTile(
        summary.broken ?? 0,
        `broken links (${summary.broken_unique ?? 0} unique)`,
        summary.broken ? 'stat--bad' : 'stat--good'
      ));
    }

    if (summary.orphans_checked) {
      tiles.push(statTile(
        summary.orphans ?? 0,
        'pages nothing links to',
        summary.orphans ? 'stat--warn' : 'stat--good'
      ));
    }

    tiles.push(statTile(Math.round(summary.elapsed ?? 0) + 's', 'run time'));
    $('stats').innerHTML = tiles.join('');
  }

  function renderTabs(summary) {
    const tabs = [];

    if (summary.mode === 'search' || summary.mode === 'full') {
      tabs.push(['hits', '🎯 Where the link was found', state.results.hits.length]);
    }
    if (summary.mode === 'broken' || summary.mode === 'full') {
      tabs.push(['broken', '💔 Broken links', state.results.broken.length]);
    }
    if (summary.orphans_checked) {
      tabs.push(['orphans', '🔗 No internal links', state.results.orphans.length]);
    }
    tabs.push(['pages', '🗺️ All pages', state.results.pages.length]);

    $('tabs').innerHTML = tabs.map(([key, title, count], i) =>
      `<div class="tab ${i === 0 ? 'is-active' : ''}" data-tab="${key}">
         ${title}<span class="tab__badge">${count}</span>
       </div>`).join('');

    document.querySelectorAll('.tab').forEach((tab) => {
      tab.addEventListener('click', () => {
        document.querySelectorAll('.tab').forEach((t) => t.classList.remove('is-active'));
        tab.classList.add('is-active');
        state.activeTab = tab.dataset.tab;
        renderTable();
      });
    });

    state.activeTab = tabs[0][0];
  }

  /* ------------------------------------------------------------------------
     Rendering: table rows
     ------------------------------------------------------------------------ */
  function hitRow(hit) {
    const dead = isDead(hit.status);

    const statusPill = hit.status == null ? '' :
      `<div class="cell-note">
         <span class="pill ${dead ? 'pill--bad' : 'pill--good'}">
           ${dead ? '✕ ' + escapeHtml(hit.status) : '✓ works'}
         </span>
         ${dead ? `<span class="cell-note--bad"> ${escapeHtml(hit.status_text)}</span>` : ''}
       </div>`;

    // every match sits in a technical tag => nothing on the site actually links here
    const noInternal = hit.no_internal
      ? `<div class="cell-note">
           <span class="pill pill--warn">no internal links</span>
           <span class="cell-note"> nothing on the site links here — only technical tags</span>
         </div>`
      : '';

    const rawHref = hit.href !== hit.absolute
      ? `<div class="cell-note">href: <code>${escapeHtml(hit.href)}</code></div>`
      : '';

    const context = hit.context
      ? `<div class="cell-note"><code>${escapeHtml(hit.context.slice(0, 160))}</code></div>`
      : '';

    return `<tr>
      <td>${linkTo(hit.page)}</td>
      <td>${linkTo(hit.absolute)}${statusPill}${noInternal}${rawHref}</td>
      <td>
        <span class="pill ${hit.visible ? 'pill--good' : 'pill--warn'}">
          ${hit.visible ? '👁 On the page' : '🔧 Technical'}
        </span>
        <div class="cell-note">${escapeHtml(hit.where)}</div>
        ${context}
      </td>
      <td>${escapeHtml(hit.text) || '<span class="cell-note">—</span>'}</td>
    </tr>`;
  }

  function brokenRow(item) {
    const repeats = item.count > 1
      ? `<div class="cell-note">appears ${item.count} times on the page</div>`
      : '';

    return `<tr>
      <td>${linkTo(item.page)}</td>
      <td>
        ${linkTo(item.link)}
        <div class="cell-note">
          <span class="pill ${item.scope === 'internal' ? 'pill--warn' : 'pill--info'}">
            ${escapeHtml(item.scope)}
          </span>
        </div>
      </td>
      <td>
        <span class="pill pill--bad">${escapeHtml(item.status)}</span>
        <div class="cell-note">${escapeHtml(item.reason)}</div>
      </td>
      <td>
        <span class="pill ${item.visible ? 'pill--good' : 'pill--warn'}">
          ${item.visible ? '👁 On the page' : '🔧 Technical'}
        </span>
        <div class="cell-note">${escapeHtml(item.where)}</div>
      </td>
      <td>${escapeHtml(item.text) || '<span class="cell-note">—</span>'}${repeats}</td>
    </tr>`;
  }

  function pageRow(page) {
    let pillClass = 'pill--bad';
    if (page.status === 200) pillClass = 'pill--info';
    else if (typeof page.status === 'number' && page.status < 400) pillClass = 'pill--warn';

    const error = page.error
      ? `<div class="cell-note cell-note--bad">${escapeHtml(page.error)}</div>`
      : '';

    return `<tr>
      <td>${linkTo(page.url)}</td>
      <td><span class="pill ${pillClass}">${escapeHtml(page.status)}</span>${error}</td>
      <td>${escapeHtml(page.title)}</td>
      <td>${page.links}</td>
    </tr>`;
  }

  function orphanRow(page) {
    return `<tr>
      <td>${linkTo(page.url)}</td>
      <td>${escapeHtml(page.title) || '<span class="cell-note">—</span>'}</td>
      <td>${page.links_out}</td>
      <td>${page.in_sitemap
        ? '<span class="pill pill--info">in sitemap</span>'
        : '<span class="pill pill--warn">not in sitemap</span>'}</td>
    </tr>`;
  }

  const TABLE_SPECS = {
    hits: {
      head: ['Page holding the link', 'Found link', 'Where exactly', 'Link or button text'],
      source: () => state.results.hits,
      row: hitRow
    },
    broken: {
      head: ['Page holding the link', 'Broken link', 'Reason', 'Where exactly', 'Link text'],
      source: () => state.results.broken,
      row: brokenRow
    },
    orphans: {
      head: ['Page nothing links to', 'Title', 'Links out', 'Source'],
      source: () => state.results.orphans,
      row: orphanRow
    },
    pages: {
      head: ['Page URL', 'Status', 'Title', 'Links'],
      source: () => state.results.pages,
      row: pageRow
    }
  };

  function renderTable() {
    if (!state.results || !state.activeTab) return;

    const spec = TABLE_SPECS[state.activeTab];
    const query = $('filter').value.trim().toLowerCase();

    const matches = (row) => !query ||
      Object.values(row).some((v) => String(v ?? '').toLowerCase().includes(query));

    const rows = spec.source().filter(matches).map(spec.row);

    $('tableBox').innerHTML = rows.length
      ? `<div class="table-wrap">
           <table>
             <thead><tr>${spec.head.map((h) => `<th>${h}</th>`).join('')}</tr></thead>
             <tbody>${rows.join('')}</tbody>
           </table>
         </div>`
      : `<div class="empty">${query ? 'Nothing matches this filter' : 'Nothing found 🎉'}</div>`;
  }

  /* ------------------------------------------------------------------------
     Download
     ------------------------------------------------------------------------ */
  async function download() {
    const button = $('downloadBtn');
    const label = button.textContent;

    button.disabled = true;
    button.textContent = 'Building the file ...';

    try {
      const response = await fetch('/api/download');
      if (!response.ok) {
        alert(await response.text());
        return;
      }

      const blob = await response.blob();
      const disposition = response.headers.get('Content-Disposition') || '';
      const name = (disposition.match(/filename="(.+?)"/) || [null, 'result.xlsx'])[1];

      const anchor = document.createElement('a');
      anchor.href = URL.createObjectURL(blob);
      anchor.download = name;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      setTimeout(() => URL.revokeObjectURL(anchor.href), 5000);
    } catch (e) {
      alert('Download failed: ' + e);
    } finally {
      button.disabled = false;
      button.textContent = label;
    }
  }

  /* ------------------------------------------------------------------------
     Wiring
     ------------------------------------------------------------------------ */
  $('startBtn').addEventListener('click', start);
  $('stopBtn').addEventListener('click', stop);
  $('downloadBtn').addEventListener('click', download);
  $('folderBtn').addEventListener('click', () => fetch('/api/open-folder'));
  $('filter').addEventListener('input', renderTable);

  applyMode();

  // show the server version right away: if it stays the same after a code
  // update, app.py was not restarted and is still running the old code
  fetch('/api/status?since=0')
    .then((r) => r.json())
    .then((data) => showVersion(data.version))
    .catch(() => {});
})();
