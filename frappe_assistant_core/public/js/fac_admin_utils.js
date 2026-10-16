// fac_admin_utils.js
// Utility functions for FAC Admin page (renderMarkdown, etc.)
// Extracted from fac_admin.js lines 8-35

(function() {
    const ns = frappe.fac_admin;

    // Frappe v16 removed Font Awesome and draws icons from its Lucide sprite; v15 has
    // no Lucide sprite but still bundles Font Awesome. Names are Lucide; each maps to
    // the Font Awesome class used on v15.
    const FA_FALLBACK = {
        'arrow-right': 'fa-arrow-right',
        'book': 'fa-book',
        'box': 'fa-cube',
        'chart-line': 'fa-line-chart',
        'check': 'fa-check',
        'circle-alert': 'fa-exclamation-circle',
        'circle-check': 'fa-check-circle',
        'circle-user': 'fa-user-circle-o',
        'circle-x': 'fa-times-circle',
        'clock': 'fa-clock-o',
        'cloud': 'fa-cloud',
        'copy': 'fa-copy',
        'external-link': 'fa-external-link',
        'eye': 'fa-eye',
        'file-image': 'fa-file-image-o',
        'file-text': 'fa-file-text-o',
        'folder': 'fa-folder-o',
        'graduation-cap': 'fa-graduation-cap',
        'history': 'fa-history',
        'key-round': 'fa-key',
        'layout-grid': 'fa-th-large',
        'loader-circle': 'fa-spinner',
        'lock': 'fa-lock',
        'messages-square': 'fa-comments',
        'play': 'fa-play',
        'plus': 'fa-plus',
        'power': 'fa-power-off',
        'refresh-cw': 'fa-refresh',
        'search': 'fa-search',
        'server': 'fa-server',
        'settings': 'fa-cog',
        'settings-2': 'fa-cogs',
        'shield': 'fa-shield',
        'sliders-horizontal': 'fa-sliders',
        'square': 'fa-stop',
        'wrench': 'fa-wrench',
        'x': 'fa-times',
        'zap': 'fa-bolt',
    };

    const hasLucideSprite = parseInt((frappe.boot.versions || {}).frappe, 10) >= 16;

    // Return icon markup. `opts.spin` animates it; `opts.className` and `opts.attrs`
    // (already-escaped attribute string) land on the outer element so click targets
    // such as `.remove-role` keep working.
    ns.icon = function(name, opts = {}) {
        const classes = ['fac-icon', opts.spin ? 'fac-icon-spin' : '', opts.className || '']
            .filter(Boolean).join(' ');
        const attrs = opts.attrs ? ` ${opts.attrs}` : '';
        if (!hasLucideSprite) {
            const fa = FA_FALLBACK[name] || 'fa-circle-o';
            return `<i class="fa ${fa} ${classes}"${attrs} aria-hidden="true"></i>`;
        }
        return frappe.utils.icon(name, opts.size || 'sm', '', '', classes)
            .replace('<svg ', `<svg${attrs} `);
    };

    // Render markdown with proper table support.
    // frappe.markdown() uses showdown but its whitespace preprocessing
    // can break table syntax, and the default converter has tables disabled.
    // We use a dedicated converter instance with tables enabled.
    let _facMarkdownConverter = null;

    ns.renderMarkdown = function(text) {
        if (!text) return '';
        if (!_facMarkdownConverter) {
            // Initialize frappe's converter so we can access the showdown lib
            if (!frappe.md2html) frappe.markdown('');
            if (frappe.md2html) {
                const Showdown = frappe.md2html.constructor;
                _facMarkdownConverter = new Showdown({
                    tables: true,
                    ghCodeBlocks: true,
                    strikethrough: true,
                    tasklists: true,
                    encodeEmails: true,
                    ellipsis: true,
                });
            }
        }
        if (_facMarkdownConverter) {
            return _facMarkdownConverter.makeHtml(text);
        }
        // Fallback
        return `<pre>${frappe.utils.escape_html(text)}</pre>`;
    };

    // Wrap occurrences of `query` in `text` with <mark>. Both inputs are escaped
    // so the result is safe to inject as innerHTML.
    ns.highlight = function(text, query) {
        const safe = frappe.utils.escape_html(text || '');
        if (!query) return safe;
        const needle = String(query).trim();
        if (!needle) return safe;
        const re = new RegExp(needle.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi');
        return safe.replace(re, m => `<mark class="fac-hl">${m}</mark>`);
    };

    // Skeleton loader card HTML helper. `rows` controls how many placeholders.
    ns.skeletonCards = function(rows) {
        const n = rows || 4;
        let out = '<div class="fac-skeleton-wrap">';
        for (let i = 0; i < n; i++) {
            out += `
                <div class="fac-skeleton-card">
                    <div class="fac-skeleton-line fac-skeleton-line--title"></div>
                    <div class="fac-skeleton-line fac-skeleton-line--body"></div>
                    <div class="fac-skeleton-line fac-skeleton-line--body short"></div>
                </div>
            `;
        }
        out += '</div>';
        return out;
    };
})();
