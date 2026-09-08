/*! Est8Go Embed Widget v1.2 — api.est8go.com */
(function () {
  'use strict';

  var API = 'https://api.est8go.com';
  var REFRESH_MS = 30 * 60 * 1000;

  // ── Find script tag ──────────────────────────────────────────
  var script = document.currentScript || (function () {
    var tags = document.querySelectorAll('script[data-tenant]');
    return tags.length ? tags[tags.length - 1] : null;
  }());

  if (!script) return;
  var tenant = script.getAttribute('data-tenant');
  if (!tenant) return;

  // ── Config ───────────────────────────────────────────────────
  var cfg = {
    tenant:       tenant,
    theme:        (script.getAttribute('data-theme') || 'dark').toLowerCase(),
    limit:        Math.min(24, Math.max(1, parseInt(script.getAttribute('data-limit'), 10) || 6)),
    type:         script.getAttribute('data-type') || '',
    location:     script.getAttribute('data-location') || '',
    columns:      Math.min(3, Math.max(1, parseInt(script.getAttribute('data-columns'), 10) || 3)),
    accent:       script.getAttribute('data-accent') || '#4F46E5',
    radius:       Math.min(32, Math.max(0, parseInt(script.getAttribute('data-radius'), 10) || 16)),
    showPrice:    script.getAttribute('data-show-price') !== 'false',
    showWa:       script.getAttribute('data-show-wa') !== 'false',
    // data-show-facts is the current name; data-show-trust is still
    // honoured so embeds already live on third-party sites keep working.
    showFacts:    script.getAttribute('data-show-facts') !== 'false'
                    && script.getAttribute('data-show-trust') !== 'false',
    showBranding: script.getAttribute('data-show-branding') !== 'false'
  };

  // ── Host element (inserted after <script> tag) ───────────────
  var host = document.createElement('div');
  host.id = 'est8go-widget-' + cfg.tenant.replace(/[^a-z0-9]/gi, '-');
  host.className = 'est8go-embed-host';
  script.parentNode.insertBefore(host, script.nextSibling);

  // ── Shadow DOM ───────────────────────────────────────────────
  var root;
  try {
    root = host.attachShadow({ mode: 'open' });
  } catch (e) {
    root = host; // graceful fallback for very old browsers
  }

  // ── Widget wrapper reference (for live class toggling) ───────
  var wrapper = null;

  // ── Theme helpers ────────────────────────────────────────────
  function isLight() {
    if (cfg.theme === 'light') return true;
    if (cfg.theme === 'dark') return false;
    return !!(window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches);
  }

  function themeClass() {
    return isLight() ? ' light' : '';
  }

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

  // ── CSS — CSS-variable-based so theme switches via class ─────
  function buildCss() {
    var c2 = Math.min(cfg.columns, 2);
    var c3 = cfg.columns;

    return [
      '@import url("https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=Syne:wght@700;800&display=swap");',
      '*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}',
      ':host{display:block;width:100%;font-family:"Inter",-apple-system,Arial,sans-serif;-webkit-font-smoothing:antialiased}',

      // Dark vars (default)
      '.widget{'
        + '--w-bg:#0F172A;--w-surface:#111827;--w-sf2:#1E293B;'
        + '--w-bdr:rgba(255,255,255,0.08);--w-txt:#F8FAFC;--w-mut:#94A3B8;'
        + '--w-em:#10B981;'
        + '--w-acc:' + cfg.accent + ';'
        + '--w-rad:' + cfg.radius + 'px;'
        + 'background:var(--w-bg);padding:16px;'
        + 'font-family:"Inter",-apple-system,Arial,sans-serif;-webkit-font-smoothing:antialiased'
      + '}',

      // Light vars override
      '.widget.light{'
        + '--w-bg:#F8FAFC;--w-surface:#FFFFFF;--w-sf2:#EEF2F7;'
        + '--w-bdr:rgba(15,23,42,0.08);--w-txt:#0F172A;--w-mut:#64748B'
      + '}',

      // Responsive grid
      '.grid{display:grid;grid-template-columns:1fr;gap:16px}',
      '@media(min-width:480px){.grid{grid-template-columns:repeat(' + c2 + ',1fr)}}',
      '@media(min-width:768px){.grid{grid-template-columns:repeat(' + c3 + ',1fr)}}',

      // Cards
      '.card{background:var(--w-surface);border:1px solid var(--w-bdr);border-radius:var(--w-rad);overflow:hidden;display:flex;flex-direction:column;transition:transform .15s}',
      '.card:hover{transform:translateY(-2px)}',

      // Image area
      '.img-wrap{position:relative;height:185px;background:var(--w-sf2);overflow:hidden;flex-shrink:0}',
      '.img-wrap img{width:100%;height:100%;object-fit:cover;display:block}',
      '.img-empty{width:100%;height:100%;display:flex;align-items:center;justify-content:center;font-size:42px;color:var(--w-mut)}',

      // Factual chip — states a record the agency supplied, nothing more
      '.fact{position:absolute;bottom:10px;left:10px;background:rgba(15,23,42,.88);border-radius:7px;padding:4px 9px;font-size:9px;font-weight:600;color:#E2E8F0;letter-spacing:.01em}',

      // Card body
      '.body{padding:12px;display:flex;flex-direction:column;flex:1}',
      '.title{font-size:14px;font-weight:700;color:var(--w-txt);line-height:1.35;margin-bottom:4px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;min-height:2.7em}',
      '.loc{font-size:11px;color:var(--w-mut);margin-bottom:8px}',
      '.price{font-family:"Syne",Arial,sans-serif;font-size:20px;font-weight:800;color:var(--w-em);margin-bottom:10px}',

      // Buttons
      '.actions{margin-top:auto;display:flex;gap:8px}',
      '.btn-v{flex:1;background:var(--w-acc);color:#fff;border:none;border-radius:var(--w-rad);padding:10px;font-size:12px;font-weight:700;text-align:center;text-decoration:none;display:flex;align-items:center;justify-content:center;cursor:pointer;font-family:"Inter",Arial,sans-serif;transition:opacity .15s}',
      '.btn-v:hover{opacity:.87}',
      '.btn-w{width:38px;height:38px;background:#25D366;border:none;border-radius:var(--w-rad);display:flex;align-items:center;justify-content:center;text-decoration:none;flex-shrink:0;cursor:pointer;transition:opacity .15s}',
      '.btn-w:hover{opacity:.87}',

      // Attribution row
      '.attrib-row{display:flex;justify-content:flex-end;align-items:center;padding-top:12px;margin-top:8px;border-top:1px solid var(--w-bdr)}',
      '.attrib{display:inline-flex;align-items:center;gap:4px;font-size:10px;font-weight:700;color:var(--w-em);text-decoration:none;opacity:.8;transition:opacity .15s}',
      '.attrib:hover{opacity:1}',

      // State screens
      '.loader,.err{text-align:center;padding:40px 16px;font-size:13px;color:var(--w-mut)}',
      '.empty{text-align:center;padding:48px 16px;color:var(--w-mut)}',
      '.empty-ico{font-size:40px;margin-bottom:12px}',
      '.empty-msg{font-size:13px;font-weight:600}'
    ].join('\n');
  }

  // ── WhatsApp SVG ─────────────────────────────────────────────
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

  // ── Card HTML ────────────────────────────────────────────────
  function cardHtml(l) {
    // Only ever state a fact the agency recorded. Where there is no
    // fact to show, show nothing — never a score, grade or badge.
    var factHtml = cfg.showFacts && l.gps_verified
      ? '<div class="fact">&#128205; Coordinates recorded</div>'
      : '';

    var priceHtml = cfg.showPrice
      ? '<div class="price">' + formatPrice(l.price) + '</div>'
      : '';

    var waHtml = cfg.showWa && l.wa_number
      ? '<a class="btn-w" href="' + esc(waHref(l.wa_number, l.id, l.title)) + '"'
        + ' target="_blank" rel="noopener noreferrer" aria-label="WhatsApp">' + WA_SVG + '</a>'
      : '';

    return '<div class="card">'
      + '<div class="img-wrap">'
      + (l.image_url
        ? '<img src="' + esc(l.image_url) + '" alt="' + esc(l.title) + '" loading="lazy">'
        : '<div class="img-empty">&#127968;</div>')
      + factHtml
      + '</div>'
      + '<div class="body">'
      + '<div class="title">' + esc(l.title) + '</div>'
      + '<div class="loc">&#128205; ' + esc(l.location || '') + (l.property_type ? ' &middot; ' + esc(l.property_type) : '') + '</div>'
      + priceHtml
      + '<div class="actions">'
      + '<a class="btn-v" href="' + esc(l.property_url) + '" target="_blank" rel="noopener noreferrer">View Details &rarr;</a>'
      + waHtml
      + '</div>'
      + '</div>'
      + '</div>';
  }

  function attribHtml() {
    if (!cfg.showBranding) return '';
    return '<div class="attrib-row">'
      + '<a class="attrib" href="https://api.est8go.com" target="_blank" rel="noopener noreferrer">'
      + 'Powered by Est8Go'
      + '</a></div>';
  }

  function buildInner(listings) {
    if (!listings || !listings.length) {
      return '<div class="empty">'
        + '<div class="empty-ico">&#127968;</div>'
        + '<div class="empty-msg">No properties available</div>'
        + '</div>';
    }
    return '<div class="grid">' + listings.map(cardHtml).join('') + '</div>';
  }

  // ── Paint (always wraps in .widget for CSS var scope) ────────
  function paint(listings) {
    root.innerHTML = '<style>' + buildCss() + '</style>'
      + '<div class="widget' + themeClass() + '">'
      + buildInner(listings) + attribHtml()
      + '</div>';
    wrapper = root.querySelector('.widget');
  }

  function showLoading() {
    root.innerHTML = '<style>' + buildCss() + '</style>'
      + '<div class="widget' + themeClass() + '">'
      + '<div class="loader">Loading properties&hellip;</div>'
      + '</div>';
    wrapper = root.querySelector('.widget');
  }

  function showError() {
    root.innerHTML = '<style>' + buildCss() + '</style>'
      + '<div class="widget' + themeClass() + '">'
      + '<div class="err">Unable to load properties. Please try again later.</div>'
      + '</div>';
    wrapper = root.querySelector('.widget');
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

  // Auto theme: toggle .light class on wrapper directly — no re-fetch needed
  if (cfg.theme === 'auto' && window.matchMedia) {
    window.matchMedia('(prefers-color-scheme: light)').addEventListener('change', function (e) {
      if (wrapper) wrapper.classList.toggle('light', e.matches);
    });
  }
}());
