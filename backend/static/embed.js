/*! Est8Go Embed Widget v1.0 — est8go-api.onrender.com */
(function () {
  'use strict';

  var API = 'https://est8go-api.onrender.com';
  var REFRESH_MS = 30 * 60 * 1000;

  // ── Find script tag ──────────────────────────────────────────
  var script = document.currentScript || (function () {
    var tags = document.querySelectorAll('script[data-tenant]');
    return tags.length ? tags[tags.length - 1] : null;
  }());

  if (!script) return;
  var tenant = script.getAttribute('data-tenant');
  if (!tenant) return;

  var cfg = {
    tenant: tenant,
    theme: (script.getAttribute('data-theme') || 'auto').toLowerCase(),
    limit: Math.min(24, Math.max(1, parseInt(script.getAttribute('data-limit'), 10) || 6)),
    type: script.getAttribute('data-type') || '',
    location: script.getAttribute('data-location') || ''
  };

  // ── Host element (inserted after <script> tag) ───────────────
  var host = document.createElement('div');
  host.id = 'est8go-widget-' + cfg.tenant.replace(/[^a-z0-9]/gi, '-');
  script.parentNode.insertBefore(host, script.nextSibling);

  // ── Shadow DOM ───────────────────────────────────────────────
  var root;
  try {
    root = host.attachShadow({ mode: 'open' });
  } catch (e) {
    root = host; // graceful fallback for very old browsers
  }

  // ── Theme resolution ─────────────────────────────────────────
  function isDark() {
    if (cfg.theme === 'dark') return true;
    if (cfg.theme === 'light') return false;
    return !!(window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches);
  }

  // ── Trust grade colours ──────────────────────────────────────
  var GRADE_COLORS = {
    emerald: '#10B981',
    gold: '#F59E0B',
    silver: '#94A3B8',
    bronze: '#CD7F32',
    ungraded: '#64748B'
  };

  // ── Helpers ──────────────────────────────────────────────────
  function formatPrice(p) {
    p = parseInt(p, 10);
    if (!p) return 'Price on Request';
    if (p >= 1000000000) return '₦' + (p / 1000000000).toFixed(1).replace(/\.0$/, '') + 'B';
    if (p >= 1000000) return '₦' + Math.floor(p / 1000000) + 'M';
    return '₦' + p.toLocaleString();
  }

  function esc(s) {
    return String(s || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function waHref(num, id, title) {
    var text = 'Hi, I am interested in Est8Go property #' + id + ' — ' + (title || '');
    return 'https://wa.me/' + num + '?text=' + encodeURIComponent(text);
  }

  // ── Shadow DOM CSS ───────────────────────────────────────────
  function buildCss(dark) {
    var bg   = dark ? '#0F172A' : '#F8FAFC';
    var surf = dark ? '#111827' : '#FFFFFF';
    var sf2  = dark ? '#1E293B' : '#EEF2F7';
    var bdr  = dark ? 'rgba(255,255,255,0.08)' : 'rgba(15,23,42,0.10)';
    var txt  = dark ? '#F8FAFC' : '#0F172A';
    var mut  = dark ? '#94A3B8' : '#64748B';

    return [
      '@import url("https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=Syne:wght@700;800&display=swap");',
      '*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}',
      ':host{display:block;width:100%;font-family:"Inter",-apple-system,Arial,sans-serif;-webkit-font-smoothing:antialiased}',
      '.widget{background:' + bg + ';padding:16px;border-radius:16px}',
      '.grid{display:grid;grid-template-columns:1fr;gap:16px}',
      '@media(min-width:500px){.grid{grid-template-columns:1fr 1fr}}',
      '@media(min-width:900px){.grid{grid-template-columns:1fr 1fr 1fr}}',
      '.card{background:' + surf + ';border:1px solid ' + bdr + ';border-radius:16px;overflow:hidden;display:flex;flex-direction:column;transition:transform .15s}',
      '.card:hover{transform:translateY(-2px)}',
      '.img-wrap{position:relative;height:185px;background:' + sf2 + ';overflow:hidden;flex-shrink:0}',
      '.img-wrap img{width:100%;height:100%;object-fit:cover;display:block}',
      '.img-empty{width:100%;height:100%;display:flex;align-items:center;justify-content:center;font-size:42px;color:' + mut + '}',
      '.trust{position:absolute;top:10px;right:10px;background:rgba(15,23,42,.88);border-radius:9px;padding:5px 9px;display:flex;align-items:center;gap:5px}',
      '.trust-n{font-family:"Syne",Arial,sans-serif;font-size:16px;font-weight:800;line-height:1}',
      '.trust-g{font-size:9px;font-weight:700;text-transform:capitalize;opacity:.85}',
      '.gps{position:absolute;bottom:10px;left:10px;background:rgba(16,185,129,.92);border-radius:7px;padding:3px 9px;font-size:9px;font-weight:700;color:#fff}',
      '.body{padding:12px;display:flex;flex-direction:column;flex:1}',
      '.title{font-size:14px;font-weight:700;color:' + txt + ';line-height:1.35;margin-bottom:4px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;min-height:2.7em}',
      '.loc{font-size:11px;color:' + mut + ';margin-bottom:8px}',
      '.price{font-family:"Syne",Arial,sans-serif;font-size:20px;font-weight:800;color:#10B981;margin-bottom:10px}',
      '.actions{margin-top:auto;display:flex;gap:8px}',
      '.btn-v{flex:1;background:#4F46E5;color:#fff;border:none;border-radius:9px;padding:10px;font-size:12px;font-weight:700;text-align:center;text-decoration:none;display:flex;align-items:center;justify-content:center;cursor:pointer;font-family:"Inter",Arial,sans-serif;transition:opacity .15s}',
      '.btn-v:hover{opacity:.87}',
      '.btn-w{width:38px;height:38px;background:#25D366;border:none;border-radius:9px;display:flex;align-items:center;justify-content:center;text-decoration:none;flex-shrink:0;cursor:pointer;transition:opacity .15s}',
      '.btn-w:hover{opacity:.87}',
      '.seal-row{display:flex;justify-content:flex-end;padding-top:12px;margin-top:8px;border-top:1px solid ' + bdr + '}',
      '.seal{display:inline-flex;align-items:center;gap:4px;font-size:10px;font-weight:700;color:#10B981;text-decoration:none;opacity:.8;transition:opacity .15s}',
      '.seal:hover{opacity:1}',
      '.loader,.err{text-align:center;padding:40px 16px;font-size:13px;color:' + mut + ';background:' + bg + ';border-radius:16px}',
      '.empty{text-align:center;padding:48px 16px;color:' + mut + '}',
      '.empty-ico{font-size:40px;margin-bottom:12px}',
      '.empty-msg{font-size:13px;font-weight:600}'
    ].join('\n');
  }

  // ── Card HTML ────────────────────────────────────────────────
  var WA_SVG = '<svg width="17" height="17" viewBox="0 0 24 24" fill="white">'
    + '<path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15'
    + '-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475'
    + '-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52'
    + '.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207'
    + '-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372'
    + '-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487'
    + '.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413'
    + '.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347'
    + 'm-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374'
    + 'a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898'
    + 'a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884'
    + 'm8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892'
    + 'c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005'
    + 'c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/></svg>';

  function cardHtml(l) {
    var gc = GRADE_COLORS[l.trust_grade] || '#64748B';
    return '<div class="card">'
      + '<div class="img-wrap">'
      + (l.image_url
        ? '<img src="' + esc(l.image_url) + '" alt="' + esc(l.title) + '" loading="lazy">'
        : '<div class="img-empty">&#127968;</div>')
      + '<div class="trust">'
      + '<span class="trust-n" style="color:' + gc + '">' + (l.trust_score || 0) + '</span>'
      + '<span class="trust-g" style="color:' + gc + '">' + esc(l.trust_grade || 'ungraded') + '</span>'
      + '</div>'
      + (l.gps_verified ? '<div class="gps">&#128205; GPS Verified</div>' : '')
      + '</div>'
      + '<div class="body">'
      + '<div class="title">' + esc(l.title) + '</div>'
      + '<div class="loc">&#128205; ' + esc(l.location || '') + (l.property_type ? ' &middot; ' + esc(l.property_type) : '') + '</div>'
      + '<div class="price">' + formatPrice(l.price) + '</div>'
      + '<div class="actions">'
      + '<a class="btn-v" href="' + esc(l.property_url) + '" target="_blank" rel="noopener noreferrer">View Details &rarr;</a>'
      + (l.wa_number
        ? '<a class="btn-w" href="' + esc(waHref(l.wa_number, l.id, l.title)) + '" target="_blank" rel="noopener noreferrer" aria-label="WhatsApp">' + WA_SVG + '</a>'
        : '')
      + '</div>'
      + '</div>'
      + '</div>';
  }

  // ── Paint ────────────────────────────────────────────────────
  var SEAL_HTML = '<div class="seal-row">'
    + '<a class="seal" href="https://est8go-api.onrender.com" target="_blank" rel="noopener noreferrer">'
    + '&#128737;&#65039; Verified by Est8Go'
    + '</a></div>';

  function paint(listings) {
    var dark = isDark();
    var inner;
    if (!listings || !listings.length) {
      inner = '<div class="empty"><div class="empty-ico">&#127968;</div>'
        + '<div class="empty-msg">No verified properties available</div></div>';
    } else {
      inner = '<div class="grid">' + listings.map(cardHtml).join('') + '</div>';
    }
    root.innerHTML = '<style>' + buildCss(dark) + '</style>'
      + '<div class="widget">' + inner + SEAL_HTML + '</div>';
  }

  function showLoading() {
    var dark = isDark();
    root.innerHTML = '<style>' + buildCss(dark) + '</style>'
      + '<div class="loader">Loading verified properties&hellip;</div>';
  }

  function showError() {
    var dark = isDark();
    root.innerHTML = '<style>' + buildCss(dark) + '</style>'
      + '<div class="err">Unable to load properties. Please try again later.</div>';
  }

  // ── API fetch ────────────────────────────────────────────────
  function buildUrl() {
    var u = API + '/public/api/' + encodeURIComponent(cfg.tenant) + '/listings?limit=' + cfg.limit;
    if (cfg.type) u += '&type=' + encodeURIComponent(cfg.type);
    if (cfg.location) u += '&location=' + encodeURIComponent(cfg.location);
    return u;
  }

  function refresh() {
    fetch(buildUrl())
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(paint)
      .catch(showError);
  }

  // ── Boot ─────────────────────────────────────────────────────
  showLoading();
  refresh();
  setInterval(refresh, REFRESH_MS);

  if (cfg.theme === 'auto' && window.matchMedia) {
    window.matchMedia('(prefers-color-scheme: dark)')
      .addEventListener('change', refresh);
  }
}());
