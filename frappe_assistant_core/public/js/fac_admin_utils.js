// fac_admin_utils.js
// Utility functions for FAC Admin page (renderMarkdown, etc.)
// Extracted from fac_admin.js lines 8-35

(function() {
    const ns = frappe.fac_admin;

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
})();
