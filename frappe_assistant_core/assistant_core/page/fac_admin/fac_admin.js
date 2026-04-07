frappe.pages['fac-admin'].on_page_load = function(wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'FAC Admin',
        single_column: true
    });

    // Render markdown with proper table support.
    // frappe.markdown() uses showdown but its whitespace preprocessing
    // can break table syntax, and the default converter has tables disabled.
    // We use a dedicated converter instance with tables enabled.
    let _facMarkdownConverter = null;
    function renderMarkdown(text) {
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
    }

    // State management to prevent race conditions
    const state = {
        toggleInProgress: {},  // Track which items are being toggled
        refreshInProgress: false,  // Track if auto-refresh is happening
        autoRefreshEnabled: true,  // Can be disabled during operations
        viewMode: 'plugins',  // 'plugins' or 'tools'
        activeTab: 'tools',  // 'tools' | 'prompts' | 'skills'
        availableRoles: [],  // Cached list of available roles
        openConfigPanels: {},  // Track which tool config panels are open
        promptsData: [],  // Cached prompt templates list
        skillsData: [],  // Cached skills list
    };

    // Add custom styles matching Frappe theme
    const styles = `
        <style>
            .fac-admin-container {
                max-width: 1400px;
                margin: 0 auto;
            }
            .fac-card {
                background: var(--card-bg);
                border-radius: var(--border-radius-md);
                padding: 20px;
                margin-bottom: 20px;
                box-shadow: var(--shadow-sm);
                border: 1px solid var(--border-color);
            }
            .fac-card-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 20px;
                padding-bottom: 12px;
                border-bottom: 1px solid var(--border-color);
            }
            .fac-card-title {
                font-size: 16px;
                font-weight: 600;
                color: var(--heading-color);
                display: flex;
                align-items: center;
                gap: 8px;
            }
            .fac-status-indicator {
                width: 10px;
                height: 10px;
                border-radius: 50%;
                display: inline-block;
            }
            .fac-status-indicator.active {
                background: var(--green-500);
                box-shadow: 0 0 0 3px var(--green-100);
            }
            .fac-status-indicator.inactive {
                background: var(--red-500);
                box-shadow: 0 0 0 3px var(--red-100);
            }
            .fac-stats-grid {
                display: grid;
                grid-template-columns: repeat(5, 1fr);
                gap: 16px;
                margin-bottom: 20px;
            }
            @media (max-width: 1200px) {
                .fac-stats-grid {
                    grid-template-columns: repeat(3, 1fr);
                }
            }
            @media (max-width: 768px) {
                .fac-stats-grid {
                    grid-template-columns: repeat(2, 1fr);
                }
            }
            .fac-stat-card {
                background: var(--card-bg);
                border-radius: var(--border-radius-md);
                padding: 20px;
                border-left: 4px solid var(--primary);
                box-shadow: var(--shadow-sm);
            }
            .fac-stat-card h3 {
                margin: 0 0 12px 0;
                font-size: 13px;
                font-weight: 500;
                color: var(--text-muted);
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            .fac-stat-value {
                font-size: 32px;
                font-weight: 600;
                color: var(--heading-color);
                margin-bottom: 8px;
            }
            .fac-stat-label {
                font-size: 13px;
                color: var(--text-muted);
            }
            .fac-tool-item {
                padding: 12px 16px;
                border-bottom: 1px solid var(--border-color);
                transition: background 0.15s;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            .fac-tool-item:hover {
                background: var(--bg-color);
            }
            .fac-tool-item:last-child {
                border-bottom: none;
            }
            .fac-tool-info {
                flex: 1;
            }
            .fac-tool-name {
                font-weight: 600;
                color: var(--heading-color);
                margin-bottom: 4px;
                font-size: 14px;
            }
            .fac-tool-meta {
                display: flex;
                gap: 12px;
                align-items: center;
                font-size: 12px;
            }
            .fac-tool-badge {
                display: inline-block;
                padding: 3px 10px;
                background: var(--bg-color);
                border-radius: 12px;
                font-size: 11px;
                color: var(--text-muted);
                font-weight: 500;
                border: 1px solid var(--border-color);
            }
            .fac-tool-toggle {
                margin: 0;
            }
            .fac-plugin-item {
                padding: 16px;
                border-bottom: 1px solid var(--border-color);
                transition: background 0.15s;
            }
            .fac-plugin-item:hover {
                background: var(--bg-color);
            }
            .fac-plugin-item:last-child {
                border-bottom: none;
            }
            .fac-plugin-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            .fac-plugin-name {
                font-weight: 600;
                color: var(--heading-color);
                font-size: 14px;
                display: flex;
                align-items: center;
                gap: 8px;
            }
            .fac-plugin-name i {
                color: var(--primary);
            }
            /* Toggle Switch */
            .switch {
                position: relative;
                display: inline-block;
                width: 44px;
                height: 24px;
            }
            .switch input {
                opacity: 0;
                width: 0;
                height: 0;
            }
            .slider {
                position: absolute;
                cursor: pointer;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background-color: var(--gray-400);
                transition: .3s;
                border: 1px solid var(--border-color);
            }
            .slider:before {
                position: absolute;
                content: "";
                height: 18px;
                width: 18px;
                left: 3px;
                bottom: 3px;
                background-color: white;
                transition: .3s;
                box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
            }
            input:checked + .slider {
                background-color: var(--green-500);
                border-color: var(--green-600);
            }
            input:checked + .slider:before {
                transform: translateX(20px);
                background-color: white;
                box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
            }
            .slider.round {
                border-radius: 24px;
            }
            .slider.round:before {
                border-radius: 50%;
            }
            .fac-settings-group {
                margin-bottom: 24px;
            }
            .fac-settings-label {
                font-size: 13px;
                font-weight: 600;
                color: var(--heading-color);
                margin-bottom: 8px;
                display: block;
            }
            .fac-settings-value {
                font-size: 13px;
                color: var(--text-color);
                padding: 10px 12px;
                background: var(--control-bg);
                border-radius: var(--border-radius);
                border: 1px solid var(--border-color);
            }
            .fac-endpoint-url {
                font-family: var(--font-stack-monospace);
                font-size: 12px;
                word-break: break-all;
            }
            .fac-table {
                width: 100%;
                border-collapse: collapse;
            }
            .fac-table thead {
                background: var(--bg-color);
            }
            .fac-table th {
                padding: 10px 12px;
                text-align: left;
                font-size: 12px;
                font-weight: 600;
                color: var(--text-muted);
                border-bottom: 1px solid var(--border-color);
            }
            .fac-table td {
                padding: 10px 12px;
                font-size: 13px;
                color: var(--text-color);
                border-bottom: 1px solid var(--border-color);
            }
            .fac-table tbody tr:hover {
                background: var(--bg-color);
            }
            /* Toggle in progress state */
            .toggle-in-progress {
                opacity: 0.6;
                pointer-events: none;
            }
            .toggle-in-progress .slider {
                cursor: not-allowed;
            }
            /* View mode tabs */
            .fac-view-tabs {
                display: flex;
                gap: 8px;
                margin-bottom: 16px;
            }
            .fac-view-tab {
                padding: 8px 16px;
                border: 1px solid var(--border-color);
                border-radius: var(--border-radius);
                background: var(--card-bg);
                cursor: pointer;
                font-size: 13px;
                font-weight: 500;
                transition: all 0.15s;
            }
            .fac-view-tab:hover {
                background: var(--bg-color);
            }
            .fac-view-tab.active {
                background: var(--primary);
                color: white;
                border-color: var(--primary);
            }
            /* Category badges */
            .fac-category-badge {
                display: inline-block;
                padding: 2px 8px;
                border-radius: 10px;
                font-size: 10px;
                font-weight: 600;
                text-transform: uppercase;
            }
            .fac-category-badge.read_only, .fac-category-badge.green {
                background: var(--green-100);
                color: var(--green-600);
            }
            .fac-category-badge.write, .fac-category-badge.yellow {
                background: var(--yellow-100);
                color: var(--yellow-700);
            }
            .fac-category-badge.read_write, .fac-category-badge.blue {
                background: var(--blue-100);
                color: var(--blue-600);
            }
            .fac-category-badge.privileged, .fac-category-badge.orange {
                background: var(--orange-100);
                color: var(--orange-600);
            }
            /* Backward compatibility for existing 'dangerous' category */
            .fac-category-badge.dangerous {
                background: var(--orange-100);
                color: var(--orange-600);
            }
            /* Tool item with expanded layout */
            .fac-tool-item-detailed {
                padding: 12px 16px;
                border-bottom: 1px solid var(--border-color);
                transition: background 0.15s;
            }
            .fac-tool-item-detailed:hover {
                background: var(--bg-color);
            }
            .fac-tool-item-detailed:last-child {
                border-bottom: none;
            }
            .fac-tool-header {
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                margin-bottom: 6px;
            }
            .fac-tool-title {
                font-weight: 600;
                color: var(--heading-color);
                font-size: 13px;
                display: flex;
                align-items: center;
                gap: 8px;
            }
            .fac-tool-description {
                font-size: 12px;
                color: var(--text-muted);
                margin-bottom: 6px;
            }
            .fac-tool-footer {
                display: flex;
                gap: 8px;
                align-items: center;
            }
            .fac-disabled-overlay {
                opacity: 0.5;
            }
            .fac-plugin-disabled-notice {
                font-size: 11px;
                color: var(--orange-500);
                display: flex;
                align-items: center;
                gap: 4px;
            }
            /* Filter controls */
            .fac-filter-bar {
                display: flex;
                gap: 12px;
                align-items: center;
                margin-bottom: 16px;
                flex-wrap: wrap;
            }
            .fac-filter-input {
                flex: 1;
                min-width: 200px;
                padding: 8px 12px;
                border: 1px solid var(--border-color);
                border-radius: var(--border-radius);
                font-size: 13px;
            }
            .fac-filter-select {
                padding: 8px 12px;
                border: 1px solid var(--border-color);
                border-radius: var(--border-radius);
                font-size: 13px;
                background: var(--card-bg);
            }
            /* Tool settings button */
            .fac-tool-settings-btn {
                background: transparent;
                border: 1px solid var(--border-color);
                border-radius: var(--border-radius);
                padding: 4px 8px;
                cursor: pointer;
                color: var(--text-muted);
                font-size: 12px;
                transition: all 0.15s;
                margin-left: 8px;
            }
            .fac-tool-settings-btn:hover {
                background: var(--blue-100);
                color: var(--blue-600);
                border-color: var(--blue-400);
            }
            .fac-tool-settings-btn.active {
                background: var(--blue-500);
                color: white;
                border-color: var(--blue-600);
            }
            /* Tool config panel */
            .fac-tool-config-panel {
                display: none;
                margin-top: 12px;
                padding: 12px;
                background: var(--control-bg);
                border-radius: var(--border-radius);
                border: 1px solid var(--border-color);
            }
            .fac-tool-config-panel.open {
                display: block;
            }
            .fac-config-row {
                display: flex;
                gap: 16px;
                align-items: flex-start;
                margin-bottom: 12px;
            }
            .fac-config-row:last-child {
                margin-bottom: 0;
            }
            .fac-config-group {
                flex: 1;
            }
            .fac-config-label {
                font-size: 11px;
                font-weight: 600;
                color: var(--text-muted);
                text-transform: uppercase;
                margin-bottom: 6px;
                display: block;
            }
            .fac-config-select {
                width: 100%;
                padding: 6px 10px;
                border: 1px solid var(--border-color);
                border-radius: var(--border-radius);
                font-size: 12px;
                background: var(--card-bg);
            }
            /* Role tags */
            .fac-role-tags {
                display: flex;
                flex-wrap: wrap;
                gap: 6px;
                margin-top: 8px;
            }
            .fac-role-tag {
                display: inline-flex;
                align-items: center;
                gap: 4px;
                padding: 4px 8px;
                background: var(--blue-100);
                color: var(--blue-700);
                border-radius: 12px;
                font-size: 11px;
                font-weight: 500;
            }
            .fac-role-tag .remove-role {
                cursor: pointer;
                opacity: 0.7;
            }
            .fac-role-tag .remove-role:hover {
                opacity: 1;
            }
            .fac-add-role-btn {
                display: inline-flex;
                align-items: center;
                gap: 4px;
                padding: 4px 8px;
                background: var(--card-bg);
                color: var(--text-muted);
                border: 1px dashed var(--border-color);
                border-radius: 12px;
                font-size: 11px;
                cursor: pointer;
                transition: all 0.15s;
            }
            .fac-add-role-btn:hover {
                border-color: var(--primary);
                color: var(--primary);
            }
            .fac-config-actions {
                display: flex;
                gap: 8px;
                justify-content: flex-end;
                margin-top: 12px;
                padding-top: 12px;
                border-top: 1px solid var(--border-color);
            }
            .fac-tool-actions {
                display: flex;
                align-items: center;
                gap: 8px;
            }
            /* Bulk actions bar */
            .fac-bulk-actions-bar {
                display: flex;
                gap: 10px;
                align-items: center;
                margin-bottom: 12px;
                padding: 10px 12px;
                background: var(--bg-color);
                border-radius: var(--border-radius);
                border: 1px solid var(--border-color);
            }
            .fac-bulk-label {
                font-size: 12px;
                font-weight: 600;
                color: var(--text-muted);
                margin-right: 4px;
            }
            .fac-bulk-actions-bar .btn {
                min-width: 80px;
            }
            .fac-bulk-actions-bar .btn-success {
                background: var(--green-500);
                border-color: var(--green-600);
                color: white;
            }
            .fac-bulk-actions-bar .btn-success:hover {
                background: var(--green-600);
            }
            .fac-bulk-actions-bar .btn-warning {
                background: var(--orange-500);
                border-color: var(--orange-600);
                color: white;
            }
            .fac-bulk-actions-bar .btn-warning:hover {
                background: var(--orange-600);
            }

            /* Top-level tab nav */
            .fac-top-tabs {
                display: flex;
                gap: 0;
                border-bottom: 2px solid var(--border-color);
                margin-bottom: 0;
            }
            .fac-top-tab {
                padding: 12px 20px;
                border: none;
                background: transparent;
                cursor: pointer;
                font-size: 14px;
                font-weight: 500;
                color: var(--text-muted);
                border-bottom: 2px solid transparent;
                margin-bottom: -2px;
                transition: all 0.15s;
                display: flex;
                align-items: center;
                gap: 6px;
            }
            .fac-top-tab:hover {
                color: var(--heading-color);
                background: var(--bg-color);
            }
            .fac-top-tab.active {
                color: var(--primary);
                border-bottom-color: var(--primary);
                font-weight: 600;
            }

            /* Tab content panels */
            .fac-tab-panel {
                display: none;
                padding-top: 16px;
            }
            .fac-tab-panel.active {
                display: block;
            }

            /* Clean card layout for prompts and skills lists */
            .fac-item-card {
                padding: 16px 20px;
                border: 1px solid var(--border-color);
                border-radius: var(--border-radius-md);
                margin-bottom: 10px;
                background: var(--card-bg);
                transition: box-shadow 0.15s, border-color 0.15s;
            }
            .fac-item-card:hover {
                border-color: var(--gray-300);
                box-shadow: var(--shadow-sm);
            }
            .fac-item-card.toggle-in-progress { opacity: 0.6; }

            /* Top row: title + status + actions */
            .fac-item-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 4px;
            }
            .fac-item-title {
                font-weight: 600;
                font-size: 14px;
                color: var(--heading-color);
                display: flex;
                align-items: center;
                gap: 8px;
                flex: 1;
                min-width: 0;
            }
            .fac-item-actions {
                display: flex;
                align-items: center;
                gap: 8px;
                flex-shrink: 0;
                margin-left: 16px;
            }

            /* Subtitle row: prompt_id / skill_id */
            .fac-item-subtitle {
                font-size: 12px;
                color: var(--text-light);
                font-family: var(--font-stack-monospace, monospace);
                margin-bottom: 10px;
            }

            /* Bottom row: metadata chips */
            .fac-item-meta {
                display: flex;
                gap: 6px;
                flex-wrap: wrap;
                align-items: center;
            }
            .fac-meta-chip {
                display: inline-flex;
                align-items: center;
                gap: 4px;
                padding: 2px 10px;
                border-radius: 12px;
                font-size: 11px;
                color: var(--text-muted);
                background: var(--bg-color);
                border: 1px solid var(--border-color);
            }
            .fac-meta-chip i { font-size: 10px; }
            .fac-meta-chip.system-chip {
                background: var(--blue-50, #eff6ff);
                color: var(--blue-600, #2563eb);
                border-color: var(--blue-100, #dbeafe);
            }

            /* Inline expand panel (for skill content / template preview) */
            .fac-expand-panel {
                display: none;
                margin-top: 12px;
                padding: 12px;
                background: var(--control-bg);
                border-radius: var(--border-radius);
                border: 1px solid var(--border-color);
                font-size: 13px;
                line-height: 1.6;
            }
            .fac-expand-panel.open { display: block; }
            .fac-expand-panel pre {
                margin: 0;
                white-space: pre-wrap;
                font-family: var(--font-stack-monospace, monospace);
                font-size: 12px;
                color: var(--text-color);
            }
            .fac-preview-content h1, .fac-preview-content h2,
            .fac-preview-content h3, .fac-preview-content h4 {
                margin-top: 12px;
                margin-bottom: 6px;
            }
            .fac-preview-content p { margin-bottom: 8px; }
            .fac-preview-content ul, .fac-preview-content ol {
                margin-bottom: 8px;
                padding-left: 20px;
            }
            .fac-preview-content code {
                background: var(--gray-100);
                padding: 1px 4px;
                border-radius: 3px;
                font-size: 12px;
            }
            .fac-preview-content pre code {
                background: var(--control-bg);
                display: block;
                padding: 8px;
                border-radius: var(--border-radius);
                overflow-x: auto;
            }
            .fac-expand-panel table, .fac-preview-content table {
                width: 100%;
                border-collapse: collapse;
                margin: 12px 0;
                font-size: 13px;
            }
            .fac-expand-panel th, .fac-preview-content th {
                background: var(--bg-color);
                font-weight: 600;
                text-align: left;
                padding: 8px 12px;
                border: 1px solid var(--border-color);
                font-size: 12px;
                color: var(--heading-color);
            }
            .fac-expand-panel td, .fac-preview-content td {
                padding: 8px 12px;
                border: 1px solid var(--border-color);
                vertical-align: top;
            }
            .fac-expand-panel tr:hover td, .fac-preview-content tr:hover td {
                background: var(--bg-color);
            }

            /* Status badge variants */
            .fac-status-badge {
                display: inline-block;
                padding: 2px 8px;
                border-radius: 10px;
                font-size: 11px;
                font-weight: 600;
                text-transform: uppercase;
            }
            .fac-status-badge.published {
                background: var(--green-100);
                color: var(--green-700);
            }
            .fac-status-badge.draft {
                background: var(--gray-100);
                color: var(--gray-600);
            }
            .fac-status-badge.deprecated, .fac-status-badge.archived {
                background: var(--orange-100);
                color: var(--orange-600);
            }

            /* Active state for eye/book expand buttons */
            .fac-tool-settings-btn.active {
                background: var(--primary-light);
                color: var(--primary);
                border-color: var(--primary);
            }

            /* ===== Dark mode overrides ===== */
            [data-theme="dark"] .fac-status-badge.published {
                background: rgba(34, 197, 94, 0.15);
                color: #4ade80;
            }
            [data-theme="dark"] .fac-status-badge.draft {
                background: rgba(156, 163, 175, 0.2);
                color: #9ca3af;
            }
            [data-theme="dark"] .fac-status-badge.deprecated,
            [data-theme="dark"] .fac-status-badge.archived {
                background: rgba(251, 146, 60, 0.15);
                color: #fb923c;
            }
            [data-theme="dark"] .fac-meta-chip {
                background: rgba(255, 255, 255, 0.06);
                border-color: rgba(255, 255, 255, 0.1);
                color: var(--text-muted);
            }
            [data-theme="dark"] .fac-meta-chip.system-chip {
                background: rgba(96, 165, 250, 0.12);
                color: #93bbfd;
                border-color: rgba(96, 165, 250, 0.2);
            }
            [data-theme="dark"] .fac-item-card {
                border-color: rgba(255, 255, 255, 0.08);
            }
            [data-theme="dark"] .fac-item-card:hover {
                border-color: rgba(255, 255, 255, 0.15);
            }
            [data-theme="dark"] .fac-item-subtitle {
                color: var(--text-muted);
            }
            [data-theme="dark"] .fac-expand-panel {
                background: rgba(255, 255, 255, 0.03);
                border-color: rgba(255, 255, 255, 0.08);
            }
            [data-theme="dark"] .fac-expand-panel th,
            [data-theme="dark"] .fac-preview-content th {
                background: rgba(255, 255, 255, 0.06);
                border-color: rgba(255, 255, 255, 0.1);
            }
            [data-theme="dark"] .fac-expand-panel td,
            [data-theme="dark"] .fac-preview-content td {
                border-color: rgba(255, 255, 255, 0.08);
            }
            [data-theme="dark"] .fac-expand-panel tr:hover td,
            [data-theme="dark"] .fac-preview-content tr:hover td {
                background: rgba(255, 255, 255, 0.04);
            }
            [data-theme="dark"] .fac-preview-content code {
                background: rgba(255, 255, 255, 0.08);
                color: #e5a0f0;
            }
            [data-theme="dark"] .fac-preview-content pre code {
                background: rgba(0, 0, 0, 0.3);
                color: var(--text-color);
            }
            [data-theme="dark"] .fac-top-tab:hover {
                background: rgba(255, 255, 255, 0.04);
                color: var(--text-color);
            }
            [data-theme="dark"] .fac-top-tab.active {
                color: #60a5fa;
                border-bottom-color: #60a5fa;
            }
            [data-theme="dark"] .fac-tool-settings-btn.active {
                background: rgba(96, 165, 250, 0.15);
                color: #60a5fa;
                border-color: rgba(96, 165, 250, 0.3);
            }
        </style>
    `;

    page.main.html(styles + `
        <div class="fac-admin-container">
            <!-- Server Status Card -->
            <div class="fac-card">
                <div class="fac-card-header">
                    <div class="fac-card-title">
                        <span id="server-status-icon" class="fac-status-indicator"></span>
                        <span id="server-status-text">Frappe Assistant Core</span>
                    </div>
                    <div>
                        <button class="btn btn-sm btn-primary" id="toggle-server">
                            <span id="toggle-server-text">Loading...</span>
                        </button>
                        <button class="btn btn-sm btn-default" id="open-settings">
                            <i class="fa fa-cog"></i> Settings
                        </button>
                    </div>
                </div>

                <!-- Quick Settings -->
                <div class="row">
                    <div class="col-md-12">
                        <div class="fac-settings-group">
                            <label class="fac-settings-label">MCP Endpoint</label>
                            <div class="fac-settings-value fac-endpoint-url" id="fac-mcp-endpoint">
                                Loading...
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Stats Grid -->
            <div class="fac-stats-grid">
                <div class="fac-stat-card" style="border-left-color: var(--primary);">
                    <h3>Plugins</h3>
                    <div id="plugin-stats">
                        <div class="fac-stat-value">-</div>
                        <div class="fac-stat-label">Loading...</div>
                    </div>
                </div>
                <div class="fac-stat-card" style="border-left-color: var(--green-500);">
                    <h3>Tools Available</h3>
                    <div id="tool-stats">
                        <div class="fac-stat-value">-</div>
                        <div class="fac-stat-label">Loading...</div>
                    </div>
                </div>
                <div class="fac-stat-card" style="border-left-color: var(--blue-500);">
                    <h3>Today's Activity</h3>
                    <div id="activity-stats">
                        <div class="fac-stat-value">-</div>
                        <div class="fac-stat-label">Tool executions today</div>
                    </div>
                </div>
                <div class="fac-stat-card" style="border-left-color: #7c3aed;">
                    <h3>Prompt Templates</h3>
                    <div id="template-stats">
                        <div class="fac-stat-value">-</div>
                        <div class="fac-stat-label">Loading...</div>
                    </div>
                </div>
                <div class="fac-stat-card" style="border-left-color: #0891b2;">
                    <h3>Skills</h3>
                    <div id="skill-stats">
                        <div class="fac-stat-value">-</div>
                        <div class="fac-stat-label">Loading...</div>
                    </div>
                </div>
            </div>

            <!-- Main Registry Card with Top-Level Tabs -->
            <div class="fac-card" style="padding-bottom: 0;">

                <!-- Top-Level Tab Navigation -->
                <div class="fac-top-tabs">
                    <button class="fac-top-tab active" data-tab="tools">
                        <i class="fa fa-wrench"></i> Tools
                    </button>
                    <button class="fac-top-tab" data-tab="prompts">
                        <i class="fa fa-file-text-o"></i> Prompt Templates
                    </button>
                    <button class="fac-top-tab" data-tab="skills">
                        <i class="fa fa-graduation-cap"></i> Skills
                    </button>
                </div>

                <!-- TOOLS TAB PANEL -->
                <div class="fac-tab-panel active" id="tab-panel-tools">
                    <div class="fac-card-header" style="margin-top: 0;">
                        <div class="fac-card-title">
                            <i class="fa fa-tools"></i>
                            Tool Registry
                        </div>
                        <button class="btn btn-sm btn-default" id="refresh-tools">
                            <i class="fa fa-refresh"></i> Refresh
                        </button>
                    </div>

                    <!-- View Mode Tabs -->
                    <div class="fac-view-tabs">
                        <div class="fac-view-tab active" data-view="plugins">
                            <i class="fa fa-cube"></i> Plugins
                        </div>
                        <div class="fac-view-tab" data-view="tools">
                            <i class="fa fa-wrench"></i> Individual Tools
                        </div>
                    </div>

                    <!-- Bulk Actions Bar (shown in tools view) -->
                    <div class="fac-bulk-actions-bar" id="tools-bulk-actions" style="display: none;">
                        <span class="fac-bulk-label">Bulk Actions:</span>
                        <select class="fac-filter-select" id="bulk-category-select">
                            <option value="">Select Category</option>
                            <option value="read_only">Read Only</option>
                            <option value="write">Write</option>
                            <option value="read_write">Read & Write</option>
                            <option value="privileged">Privileged</option>
                        </select>
                        <select class="fac-filter-select" id="bulk-plugin-select">
                            <option value="">All Plugins</option>
                        </select>
                        <button class="btn btn-xs btn-success" id="bulk-enable-btn">
                            <i class="fa fa-check"></i> Enable
                        </button>
                        <button class="btn btn-xs btn-warning" id="bulk-disable-btn">
                            <i class="fa fa-times"></i> Disable
                        </button>
                    </div>

                    <!-- Filter Bar (shown in tools view) -->
                    <div class="fac-filter-bar" id="tools-filter-bar" style="display: none;">
                        <input type="text" class="fac-filter-input" id="tool-search"
                               placeholder="Search tools...">
                        <select class="fac-filter-select" id="category-filter">
                            <option value="">All Categories</option>
                            <option value="read_only">Read Only</option>
                            <option value="write">Write</option>
                            <option value="read_write">Read & Write</option>
                            <option value="privileged">Privileged</option>
                        </select>
                        <select class="fac-filter-select" id="plugin-filter">
                            <option value="">All Plugins</option>
                        </select>
                    </div>

                    <div id="tool-registry" style="max-height: 500px; overflow-y: auto;">
                        <div style="padding: 20px; text-align: center; color: var(--text-muted);">
                            <i class="fa fa-spinner fa-spin"></i> Loading tools...
                        </div>
                    </div>
                </div>

                <!-- PROMPT TEMPLATES TAB PANEL -->
                <div class="fac-tab-panel" id="tab-panel-prompts">
                    <div class="fac-card-header" style="margin-top: 0;">
                        <div style="display: flex; gap: 8px; flex: 1; align-items: center;">
                            <input type="text" class="fac-filter-input" id="prompt-search"
                                   placeholder="Search templates..." style="flex: 1; max-width: 300px;">
                            <select class="fac-filter-select" id="prompt-status-filter">
                                <option value="">All Statuses</option>
                                <option value="Published">Published</option>
                                <option value="Draft">Draft</option>
                                <option value="Deprecated">Deprecated</option>
                                <option value="Archived">Archived</option>
                            </select>
                        </div>
                        <button class="btn btn-sm btn-default" id="refresh-prompts">
                            <i class="fa fa-refresh"></i> Refresh
                        </button>
                    </div>
                    <div id="prompt-templates-list" style="max-height: 600px; overflow-y: auto;">
                        <div style="padding: 20px; text-align: center; color: var(--text-muted);">
                            <i class="fa fa-spinner fa-spin"></i> Loading templates...
                        </div>
                    </div>
                </div>

                <!-- SKILLS TAB PANEL -->
                <div class="fac-tab-panel" id="tab-panel-skills">
                    <div class="fac-card-header" style="margin-top: 0;">
                        <div style="display: flex; gap: 8px; flex: 1; align-items: center;">
                            <input type="text" class="fac-filter-input" id="skill-search"
                                   placeholder="Search skills..." style="flex: 1; max-width: 300px;">
                            <select class="fac-filter-select" id="skill-type-filter">
                                <option value="">All Types</option>
                                <option value="Tool Usage">Tool Usage</option>
                                <option value="Workflow">Workflow</option>
                            </select>
                            <select class="fac-filter-select" id="skill-status-filter">
                                <option value="">All Statuses</option>
                                <option value="Published">Published</option>
                                <option value="Draft">Draft</option>
                                <option value="Deprecated">Deprecated</option>
                            </select>
                        </div>
                        <button class="btn btn-sm btn-default" id="refresh-skills">
                            <i class="fa fa-refresh"></i> Refresh
                        </button>
                    </div>
                    <div id="skills-list" style="max-height: 600px; overflow-y: auto;">
                        <div style="padding: 20px; text-align: center; color: var(--text-muted);">
                            <i class="fa fa-spinner fa-spin"></i> Loading skills...
                        </div>
                    </div>
                </div>

            </div>

            <!-- Recent Activity -->
            <div class="fac-card">
                <div class="fac-card-header">
                    <div class="fac-card-title">
                        <i class="fa fa-history"></i>
                        Recent Activity
                    </div>
                </div>
                <div id="recent-activity">
                    <div style="padding: 20px; text-align: center; color: var(--text-muted);">
                        <i class="fa fa-spinner fa-spin"></i> Loading activity...
                    </div>
                </div>
            </div>
        </div>
    `);

    // Load server status
    function loadServerStatus() {
        frappe.call({
            method: "frappe.client.get",
            args: {
                doctype: "Assistant Core Settings",
                name: "Assistant Core Settings"  // Required for Single DocTypes
            },
            callback: function(response) {
                if (response.message) {
                    const settings = response.message;
                    const isEnabled = settings.server_enabled;

                    // Update status
                    const statusIcon = $('#server-status-icon');
                    const statusText = $('#server-status-text');
                    const toggleBtn = $('#toggle-server');
                    const toggleText = $('#toggle-server-text');

                    if (isEnabled) {
                        statusIcon.removeClass('inactive').addClass('active');
                        statusText.text('Frappe Assistant Core - Running');
                        toggleBtn.removeClass('btn-primary').addClass('btn-warning');
                        toggleText.html('<i class="fa fa-stop"></i> Disable');
                    } else {
                        statusIcon.removeClass('active').addClass('inactive');
                        statusText.text('Frappe Assistant Core - Stopped');
                        toggleBtn.removeClass('btn-warning').addClass('btn-primary');
                        toggleText.html('<i class="fa fa-play"></i> Enable');
                    }

                    // Update MCP Endpoint URL from settings (with fallback)
                    let endpointUrl = settings.mcp_endpoint_url;
                    if (!endpointUrl || endpointUrl === '') {
                        // Generate URL client-side if not set
                        endpointUrl = window.location.origin + '/api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp';
                    }
                    $('#fac-mcp-endpoint').text(endpointUrl);
                }
            },
            error: function(r) {
                console.error('Failed to load server status:', r);
                $('#fac-mcp-endpoint').text('Error loading endpoint');
            }
        });
    }

    // Toggle server
    function toggleServer() {
        frappe.call({
            method: "frappe_assistant_core.api.admin_api.get_server_settings",
            callback: function(response) {
                if (response.message) {
                    const currentState = response.message.server_enabled;
                    const newState = currentState ? 0 : 1;

                    frappe.call({
                        method: "frappe_assistant_core.api.admin_api.update_server_settings",
                        args: {
                            server_enabled: newState
                        },
                        callback: function(result) {
                            if (result.message) {
                                frappe.show_alert({
                                    message: newState ? 'FAC Server Enabled' : 'FAC Server Disabled',
                                    indicator: newState ? 'green' : 'orange'
                                });

                                // Reload status (cache is cleared by API)
                                setTimeout(function() {
                                    loadServerStatus();
                                }, 300);
                            }
                        }
                    });
                }
            }
        });
    }

    // Load plugin and tool stats
    function loadStats() {
        frappe.call({
            method: "frappe_assistant_core.api.admin_api.get_plugin_stats",
            callback: function(response) {
                if (response.message) {
                    const stats = response.message;
                    $('#plugin-stats').html(`
                        <div class="fac-stat-value">${stats.enabled_count || 0}</div>
                        <div class="fac-stat-label">${stats.enabled_count} enabled / ${stats.total_count} total</div>
                    `);
                }
            }
        });

        frappe.call({
            method: "frappe_assistant_core.api.admin_api.get_tool_stats",
            callback: function(response) {
                if (response.message) {
                    const stats = response.message;
                    $('#tool-stats').html(`
                        <div class="fac-stat-value">${stats.total_tools || 0}</div>
                        <div class="fac-stat-label">Registered tools</div>
                    `);
                }
            }
        });

        frappe.call({
            method: "frappe_assistant_core.api.admin_api.get_usage_statistics",
            callback: function(response) {
                if (response.message && response.message.success) {
                    const stats = response.message.data;
                    $('#activity-stats').html(`
                        <div class="fac-stat-value">${stats.audit_logs?.today || 0}</div>
                        <div class="fac-stat-label">Tool executions today</div>
                    `);
                }
            }
        });

        frappe.call({
            method: "frappe_assistant_core.api.admin_api.get_prompt_templates_list",
            callback: function(response) {
                if (response.message && response.message.success) {
                    const d = response.message;
                    $('#template-stats').html(`
                        <div class="fac-stat-value">${d.published || 0}</div>
                        <div class="fac-stat-label">${d.published} published / ${d.total} total</div>
                    `);
                }
            }
        });

        frappe.call({
            method: "frappe_assistant_core.api.admin_api.get_skills_list",
            callback: function(response) {
                if (response.message && response.message.success) {
                    const d = response.message;
                    $('#skill-stats').html(`
                        <div class="fac-stat-value">${d.published || 0}</div>
                        <div class="fac-stat-label">${d.published} published / ${d.total} total</div>
                    `);
                }
            }
        });
    }

    // Store tools data for filtering
    let toolsData = [];

    // Load tool registry based on current view mode
    function loadToolRegistry() {
        if (state.viewMode === 'plugins') {
            loadPluginView();
        } else {
            loadToolsView();
        }
    }

    // Load plugin view (grouped by plugin)
    function loadPluginView() {
        // Skip if any toggle is in progress
        if (Object.keys(state.toggleInProgress).length > 0) {
            return;
        }

        frappe.call({
            method: "frappe_assistant_core.api.admin_api.get_plugin_stats",
            callback: function(response) {
                if (response.message && response.message.plugins) {
                    const plugins = response.message.plugins;
                    if (plugins.length > 0) {
                        const pluginsHtml = plugins.map(plugin => {
                            const isToggling = state.toggleInProgress[`plugin_${plugin.plugin_id}`];
                            return `
                            <div class="fac-plugin-item ${isToggling ? 'toggle-in-progress' : ''}">
                                <div class="fac-plugin-header">
                                    <div class="fac-plugin-info">
                                        <div class="fac-plugin-name">
                                            <i class="fa fa-cube"></i>
                                            ${plugin.name}
                                        </div>
                                    </div>
                                    <div>
                                        <label class="switch" style="margin: 0;">
                                            <input type="checkbox" class="fac-plugin-toggle"
                                                   data-plugin="${plugin.plugin_id}"
                                                   ${plugin.enabled ? 'checked' : ''}
                                                   ${isToggling ? 'disabled' : ''}>
                                            <span class="slider round"></span>
                                        </label>
                                    </div>
                                </div>
                            </div>
                        `}).join('');
                        $('#tool-registry').html(pluginsHtml);

                        // Add toggle handlers
                        $('.fac-plugin-toggle').off('change').on('change', function() {
                            const pluginName = $(this).data('plugin');
                            const isEnabled = $(this).is(':checked');
                            togglePlugin(pluginName, isEnabled);
                        });
                    } else {
                        $('#tool-registry').html('<div style="padding: 20px; text-align: center; color: var(--text-muted);">No plugins available</div>');
                    }
                }
            },
            error: function() {
                $('#tool-registry').html('<div style="padding: 20px; text-align: center; color: var(--red-500);">Failed to load plugins</div>');
            }
        });
    }

    // Load individual tools view
    function loadToolsView() {
        // Skip if any toggle is in progress
        if (Object.keys(state.toggleInProgress).length > 0) {
            return;
        }

        frappe.call({
            method: "frappe_assistant_core.api.admin_api.get_tool_configurations",
            callback: function(response) {
                if (response.message && response.message.success) {
                    toolsData = response.message.tools;

                    // Populate plugin filter and bulk plugin select
                    const plugins = [...new Set(toolsData.map(t => t.plugin_name))];
                    const pluginFilter = $('#plugin-filter');
                    const bulkPluginSelect = $('#bulk-plugin-select');
                    pluginFilter.find('option:gt(0)').remove();
                    bulkPluginSelect.find('option:gt(0)').remove();
                    plugins.forEach(p => {
                        const label = p.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase());
                        pluginFilter.append(`<option value="${p}">${label}</option>`);
                        bulkPluginSelect.append(`<option value="${p}">${label}</option>`);
                    });

                    renderToolsList();
                } else {
                    $('#tool-registry').html('<div style="padding: 20px; text-align: center; color: var(--red-500);">Failed to load tools</div>');
                }
            },
            error: function() {
                $('#tool-registry').html('<div style="padding: 20px; text-align: center; color: var(--red-500);">Failed to load tools</div>');
            }
        });
    }

    // Render filtered tools list
    function renderToolsList() {
        const searchTerm = $('#tool-search').val().toLowerCase();
        const categoryFilter = $('#category-filter').val();
        const pluginFilter = $('#plugin-filter').val();

        let filteredTools = toolsData.filter(tool => {
            // Search filter
            if (searchTerm && !tool.name.toLowerCase().includes(searchTerm) &&
                !tool.description.toLowerCase().includes(searchTerm)) {
                return false;
            }
            // Category filter - treat 'privileged' and 'dangerous' as equivalent
            if (categoryFilter) {
                const toolCategory = tool.category === 'dangerous' ? 'privileged' : tool.category;
                const filterCategory = categoryFilter === 'dangerous' ? 'privileged' : categoryFilter;
                if (toolCategory !== filterCategory) {
                    return false;
                }
            }
            // Plugin filter
            if (pluginFilter && tool.plugin_name !== pluginFilter) {
                return false;
            }
            return true;
        });

        if (filteredTools.length === 0) {
            $('#tool-registry').html('<div style="padding: 20px; text-align: center; color: var(--text-muted);">No tools match the filters</div>');
            return;
        }

        const toolsHtml = filteredTools.map(tool => {
            const isToggling = state.toggleInProgress[`tool_${tool.name}`];
            const pluginDisabled = !tool.plugin_enabled;
            const isPanelOpen = state.openConfigPanels[tool.name];
            const roleTagsHtml = (tool.role_access || []).map(r =>
                `<span class="fac-role-tag" data-role="${r.role}">
                    ${r.role}
                    <i class="fa fa-times remove-role" data-tool="${tool.name}" data-role="${r.role}"></i>
                </span>`
            ).join('');

            return `
                <div class="fac-tool-item-detailed ${isToggling ? 'toggle-in-progress' : ''} ${pluginDisabled ? 'fac-disabled-overlay' : ''}" data-tool-name="${tool.name}">
                    <div class="fac-tool-header">
                        <div class="fac-tool-title">
                            ${tool.display_name}
                            <span class="fac-category-badge ${tool.category}">${tool.category_label}</span>
                        </div>
                        <div class="fac-tool-actions">
                            <button class="fac-tool-settings-btn ${isPanelOpen ? 'active' : ''}"
                                    data-tool="${tool.name}"
                                    title="Configure role access">
                                <i class="fa fa-cog"></i>
                            </button>
                            <label class="switch" style="margin: 0;">
                                <input type="checkbox" class="fac-tool-toggle"
                                       data-tool="${tool.name}"
                                       ${tool.tool_enabled ? 'checked' : ''}
                                       ${isToggling || pluginDisabled ? 'disabled' : ''}>
                                <span class="slider round"></span>
                            </label>
                        </div>
                    </div>
                    <div class="fac-tool-description">${tool.description || 'No description available'}</div>
                    <div class="fac-tool-footer">
                        <span class="fac-tool-badge">${tool.plugin_display_name}</span>
                        ${pluginDisabled ? '<span class="fac-plugin-disabled-notice"><i class="fa fa-exclamation-circle"></i> Plugin disabled</span>' : ''}
                        ${tool.role_access_mode !== 'Allow All' ? '<span class="fac-tool-badge" style="background: var(--blue-100); color: var(--blue-600);"><i class="fa fa-lock"></i> Role restricted</span>' : ''}
                    </div>

                    <!-- Configuration Panel -->
                    <div class="fac-tool-config-panel ${isPanelOpen ? 'open' : ''}" id="config-panel-${tool.name}">
                        <div class="fac-config-row">
                            <div class="fac-config-group">
                                <label class="fac-config-label">Role Access Mode</label>
                                <select class="fac-config-select fac-role-mode-select" data-tool="${tool.name}">
                                    <option value="Allow All" ${tool.role_access_mode === 'Allow All' ? 'selected' : ''}>Allow All Users</option>
                                    <option value="Restrict to Listed Roles" ${tool.role_access_mode === 'Restrict to Listed Roles' ? 'selected' : ''}>Restrict to Listed Roles</option>
                                </select>
                            </div>
                            <div class="fac-config-group">
                                <label class="fac-config-label">Category</label>
                                <select class="fac-config-select fac-category-select" data-tool="${tool.name}">
                                    <option value="read_only" ${tool.category === 'read_only' ? 'selected' : ''}>Read Only</option>
                                    <option value="write" ${tool.category === 'write' ? 'selected' : ''}>Write</option>
                                    <option value="read_write" ${tool.category === 'read_write' ? 'selected' : ''}>Read & Write</option>
                                    <option value="privileged" ${tool.category === 'privileged' || tool.category === 'dangerous' ? 'selected' : ''}>Privileged</option>
                                </select>
                            </div>
                        </div>
                        <div class="fac-config-row fac-roles-section" data-tool="${tool.name}" style="${tool.role_access_mode !== 'Restrict to Listed Roles' ? 'display: none;' : ''}">
                            <div class="fac-config-group">
                                <label class="fac-config-label">Allowed Roles</label>
                                <div class="fac-role-tags" id="role-tags-${tool.name}">
                                    ${roleTagsHtml}
                                    <span class="fac-add-role-btn" data-tool="${tool.name}">
                                        <i class="fa fa-plus"></i> Add Role
                                    </span>
                                </div>
                            </div>
                        </div>
                        <div class="fac-config-actions">
                            <button class="btn btn-xs btn-default fac-config-cancel" data-tool="${tool.name}">Cancel</button>
                            <button class="btn btn-xs btn-primary fac-config-save" data-tool="${tool.name}">Save Changes</button>
                        </div>
                    </div>
                </div>
            `;
        }).join('');

        $('#tool-registry').html(toolsHtml);

        // Add toggle handlers
        $('.fac-tool-toggle').off('change').on('change', function() {
            const toolName = $(this).data('tool');
            const isEnabled = $(this).is(':checked');
            toggleTool(toolName, isEnabled);
        });

        // Add settings button handlers
        $('.fac-tool-settings-btn').off('click').on('click', function() {
            const toolName = $(this).data('tool');
            toggleConfigPanel(toolName);
        });

        // Add role mode change handlers
        $('.fac-role-mode-select').off('change').on('change', function() {
            const toolName = $(this).data('tool');
            const mode = $(this).val();
            const rolesSection = $(`.fac-roles-section[data-tool="${toolName}"]`);
            if (mode === 'Restrict to Listed Roles') {
                rolesSection.show();
            } else {
                rolesSection.hide();
            }
        });

        // Add role button handlers
        $('.fac-add-role-btn').off('click').on('click', function() {
            const toolName = $(this).data('tool');
            showAddRoleDialog(toolName);
        });

        // Remove role handlers
        $('.remove-role').off('click').on('click', function() {
            const toolName = $(this).data('tool');
            const role = $(this).data('role');
            removeRole(toolName, role);
        });

        // Cancel button handlers
        $('.fac-config-cancel').off('click').on('click', function() {
            const toolName = $(this).data('tool');
            toggleConfigPanel(toolName, false);
            // Re-render to reset any unsaved changes
            renderToolsList();
        });

        // Save button handlers
        $('.fac-config-save').off('click').on('click', function() {
            const toolName = $(this).data('tool');
            saveToolConfig(toolName);
        });
    }

    // Toggle config panel visibility
    function toggleConfigPanel(toolName, forceState) {
        const panel = $(`#config-panel-${toolName}`);
        const btn = $(`.fac-tool-settings-btn[data-tool="${toolName}"]`);

        if (forceState === false || (forceState === undefined && panel.hasClass('open'))) {
            panel.removeClass('open');
            btn.removeClass('active');
            delete state.openConfigPanels[toolName];
        } else {
            panel.addClass('open');
            btn.addClass('active');
            state.openConfigPanels[toolName] = true;
            // Load roles if not already loaded
            if (state.availableRoles.length === 0) {
                loadAvailableRoles();
            }
        }
    }

    // Load available roles
    function loadAvailableRoles() {
        frappe.call({
            method: "frappe_assistant_core.api.admin_api.get_available_roles",
            callback: function(response) {
                if (response.message && response.message.success) {
                    state.availableRoles = response.message.roles;
                }
            }
        });
    }

    // Show add role dialog
    function showAddRoleDialog(toolName) {
        const tool = toolsData.find(t => t.name === toolName);
        const existingRoles = (tool?.role_access || []).map(r => r.role);
        const availableRoles = state.availableRoles.filter(r => !existingRoles.includes(r.name));

        if (availableRoles.length === 0) {
            frappe.show_alert({
                message: 'All available roles have been added',
                indicator: 'orange'
            });
            return;
        }

        const dialog = new frappe.ui.Dialog({
            title: 'Add Role',
            fields: [
                {
                    fieldname: 'role',
                    fieldtype: 'Select',
                    label: 'Role',
                    options: availableRoles.map(r => r.name).join('\n'),
                    reqd: 1
                }
            ],
            primary_action_label: 'Add',
            primary_action: function(values) {
                addRole(toolName, values.role);
                dialog.hide();
            }
        });
        dialog.show();
    }

    // Add role to tool
    function addRole(toolName, role) {
        const tool = toolsData.find(t => t.name === toolName);
        if (!tool.role_access) {
            tool.role_access = [];
        }
        tool.role_access.push({ role: role, allow_access: 1 });

        // Re-render the role tags
        const container = $(`#role-tags-${toolName}`);
        const addBtn = container.find('.fac-add-role-btn');
        addBtn.before(`
            <span class="fac-role-tag" data-role="${role}">
                ${role}
                <i class="fa fa-times remove-role" data-tool="${toolName}" data-role="${role}"></i>
            </span>
        `);

        // Re-attach remove handler
        container.find(`.remove-role[data-role="${role}"]`).off('click').on('click', function() {
            removeRole(toolName, role);
        });
    }

    // Remove role from tool
    function removeRole(toolName, role) {
        const tool = toolsData.find(t => t.name === toolName);
        if (tool && tool.role_access) {
            tool.role_access = tool.role_access.filter(r => r.role !== role);
        }
        $(`#role-tags-${toolName} .fac-role-tag[data-role="${role}"]`).remove();
    }

    // Save tool configuration
    function saveToolConfig(toolName) {
        const tool = toolsData.find(t => t.name === toolName);
        const panel = $(`#config-panel-${toolName}`);

        const roleAccessMode = panel.find('.fac-role-mode-select').val();
        const category = panel.find('.fac-category-select').val();
        const roles = tool.role_access || [];

        // Show saving state
        const saveBtn = panel.find('.fac-config-save');
        saveBtn.prop('disabled', true).html('<i class="fa fa-spinner fa-spin"></i> Saving...');

        // Update role access first
        frappe.call({
            method: "frappe_assistant_core.api.admin_api.update_tool_role_access",
            args: {
                tool_name: toolName,
                role_access_mode: roleAccessMode,
                roles: roles
            },
            callback: function(response) {
                if (response.message && response.message.success) {
                    // Now update category
                    frappe.call({
                        method: "frappe_assistant_core.api.admin_api.update_tool_category",
                        args: {
                            tool_name: toolName,
                            category: category,
                            override: true
                        },
                        callback: function(catResponse) {
                            if (catResponse.message && catResponse.message.success) {
                                frappe.show_alert({
                                    message: 'Tool configuration saved',
                                    indicator: 'green'
                                });

                                // Update local data
                                tool.role_access_mode = roleAccessMode;
                                tool.category = category;

                                // Close panel and refresh
                                toggleConfigPanel(toolName, false);
                                loadToolsView();
                            } else {
                                frappe.show_alert({
                                    message: catResponse.message?.message || 'Failed to update category',
                                    indicator: 'red'
                                });
                            }
                        },
                        always: function() {
                            saveBtn.prop('disabled', false).html('Save Changes');
                        }
                    });
                } else {
                    frappe.show_alert({
                        message: response.message?.message || 'Failed to save configuration',
                        indicator: 'red'
                    });
                    saveBtn.prop('disabled', false).html('Save Changes');
                }
            },
            error: function() {
                frappe.show_alert({
                    message: 'Error saving configuration',
                    indicator: 'red'
                });
                saveBtn.prop('disabled', false).html('Save Changes');
            }
        });
    }

    // Toggle plugin enabled/disabled with race condition prevention
    function togglePlugin(pluginName, enabled) {
        const stateKey = `plugin_${pluginName}`;

        // Prevent duplicate toggle
        if (state.toggleInProgress[stateKey]) {
            return;
        }

        // Mark as in progress
        state.toggleInProgress[stateKey] = true;
        state.autoRefreshEnabled = false;

        // Update UI to show in-progress state
        const checkbox = $(`.fac-plugin-toggle[data-plugin="${pluginName}"]`);
        const originalState = !enabled;  // Original state is opposite of what we're trying to set
        checkbox.prop('disabled', true);
        checkbox.closest('.fac-plugin-item').addClass('toggle-in-progress');

        frappe.call({
            method: "frappe_assistant_core.api.admin_api.toggle_plugin",
            args: {
                plugin_name: pluginName,
                enable: enabled
            },
            callback: function(response) {
                if (response.message && response.message.success) {
                    frappe.show_alert({
                        message: response.message.message,
                        indicator: enabled ? 'green' : 'orange'
                    });
                    // Update stats only (not full reload to prevent visual glitch)
                    loadStats();
                } else {
                    // Reset checkbox to original state on error
                    checkbox.prop('checked', originalState);
                    frappe.show_alert({
                        message: response.message?.message || 'Unknown error',
                        indicator: 'red'
                    });
                }
            },
            error: function() {
                // Reset checkbox to original state on error
                checkbox.prop('checked', originalState);
                frappe.show_alert({
                    message: 'Error toggling plugin',
                    indicator: 'red'
                });
            },
            always: function() {
                // Clear in-progress state
                delete state.toggleInProgress[stateKey];
                state.autoRefreshEnabled = true;

                // Re-enable checkbox and remove in-progress styling
                checkbox.prop('disabled', false);
                checkbox.closest('.fac-plugin-item').removeClass('toggle-in-progress');
            }
        });
    }

    // Toggle individual tool enabled/disabled
    function toggleTool(toolName, enabled) {
        const stateKey = `tool_${toolName}`;

        // Prevent duplicate toggle
        if (state.toggleInProgress[stateKey]) {
            return;
        }

        // Mark as in progress
        state.toggleInProgress[stateKey] = true;
        state.autoRefreshEnabled = false;

        // Update UI to show in-progress state
        const checkbox = $(`.fac-tool-toggle[data-tool="${toolName}"]`);
        const originalState = !enabled;
        checkbox.prop('disabled', true);
        checkbox.closest('.fac-tool-item-detailed').addClass('toggle-in-progress');

        frappe.call({
            method: "frappe_assistant_core.api.admin_api.toggle_tool",
            args: {
                tool_name: toolName,
                enabled: enabled ? 1 : 0
            },
            callback: function(response) {
                if (response.message && response.message.success) {
                    frappe.show_alert({
                        message: response.message.message,
                        indicator: enabled ? 'green' : 'orange'
                    });
                    // Update local data
                    const tool = toolsData.find(t => t.name === toolName);
                    if (tool) {
                        tool.tool_enabled = enabled;
                        tool.effectively_enabled = tool.plugin_enabled && enabled;
                    }
                    loadStats();
                } else {
                    // Reset checkbox to original state on error
                    checkbox.prop('checked', originalState);
                    frappe.show_alert({
                        message: response.message?.message || 'Unknown error',
                        indicator: 'red'
                    });
                }
            },
            error: function() {
                // Reset checkbox to original state on error
                checkbox.prop('checked', originalState);
                frappe.show_alert({
                    message: 'Error toggling tool',
                    indicator: 'red'
                });
            },
            always: function() {
                // Clear in-progress state
                delete state.toggleInProgress[stateKey];
                state.autoRefreshEnabled = true;

                // Re-enable checkbox and remove in-progress styling
                checkbox.prop('disabled', false);
                checkbox.closest('.fac-tool-item-detailed').removeClass('toggle-in-progress');
            }
        });
    }

    // Load recent activity
    function loadRecentActivity() {
        frappe.call({
            method: "frappe_assistant_core.api.admin_api.get_usage_statistics",
            callback: function(response) {
                if (response.message && response.message.success) {
                    const activities = response.message.data.recent_activity || [];
                    if (activities.length > 0) {
                        const tableHtml = `
                            <table class="fac-table">
                                <thead>
                                    <tr>
                                        <th>Action</th>
                                        <th>Tool</th>
                                        <th>User</th>
                                        <th>Status</th>
                                        <th>Time</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${activities.slice(0, 5).map(a => `
                                        <tr>
                                            <td>${a.action}</td>
                                            <td>${a.tool_name || '-'}</td>
                                            <td>${a.user}</td>
                                            <td>
                                                <span class="indicator-pill ${a.status === 'Success' ? 'green' : 'red'}">
                                                    ${a.status}
                                                </span>
                                            </td>
                                            <td style="color: var(--text-muted);">
                                                ${frappe.datetime.str_to_user(a.timestamp)}
                                            </td>
                                        </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        `;
                        $('#recent-activity').html(tableHtml);
                    } else {
                        $('#recent-activity').html('<div style="padding: 20px; text-align: center; color: var(--text-muted);">No recent activity</div>');
                    }
                }
            },
            error: function() {
                $('#recent-activity').html('<div style="padding: 20px; text-align: center; color: var(--red-500);">Failed to load activity</div>');
            }
        });
    }

    // Event handlers
    $('#toggle-server').on('click', toggleServer);
    $('#open-settings').on('click', function() {
        frappe.set_route('Form', 'Assistant Core Settings');
    });
    $('#refresh-tools').on('click', loadToolRegistry);

    // View mode tab handlers
    $('.fac-view-tab').on('click', function() {
        const viewMode = $(this).data('view');
        if (viewMode === state.viewMode) return;

        // Update active state
        $('.fac-view-tab').removeClass('active');
        $(this).addClass('active');

        // Update state
        state.viewMode = viewMode;

        // Show/hide filter bar and bulk actions bar
        if (viewMode === 'tools') {
            $('#tools-filter-bar').show();
            $('#tools-bulk-actions').show();
        } else {
            $('#tools-filter-bar').hide();
            $('#tools-bulk-actions').hide();
        }

        // Reload the registry
        loadToolRegistry();
    });

    // Filter handlers (for tools view)
    $('#tool-search').on('input', frappe.utils.debounce(function() {
        if (state.viewMode === 'tools') {
            renderToolsList();
        }
    }, 300));

    $('#category-filter, #plugin-filter').on('change', function() {
        if (state.viewMode === 'tools') {
            renderToolsList();
        }
    });

    // Bulk toggle by category function
    function bulkToggleByCategory(category, plugin, enabled) {
        const actionText = enabled ? 'enable' : 'disable';
        const categoryText = category ? category.replace('_', ' ') : 'all categories';
        const pluginText = plugin ? ` in ${plugin}` : '';

        // Disable buttons during operation
        $('#bulk-enable-btn, #bulk-disable-btn').prop('disabled', true);
        const btn = enabled ? $('#bulk-enable-btn') : $('#bulk-disable-btn');
        const originalHtml = btn.html();
        btn.html(`<i class="fa fa-spinner fa-spin"></i> ${enabled ? 'Enabling' : 'Disabling'}...`);

        frappe.call({
            method: "frappe_assistant_core.api.admin_api.bulk_toggle_tools_by_category",
            args: {
                category: category || null,
                plugin_name: plugin || null,
                enabled: enabled
            },
            callback: function(response) {
                if (response.message && response.message.success) {
                    frappe.show_alert({
                        message: response.message.message,
                        indicator: enabled ? 'green' : 'orange'
                    });
                    // Refresh the tools list
                    loadToolsView();
                    loadStats();
                } else {
                    frappe.show_alert({
                        message: response.message?.message || `Failed to ${actionText} tools`,
                        indicator: 'red'
                    });
                }
            },
            error: function() {
                frappe.show_alert({
                    message: `Error: Failed to ${actionText} tools`,
                    indicator: 'red'
                });
            },
            always: function() {
                // Re-enable buttons
                $('#bulk-enable-btn, #bulk-disable-btn').prop('disabled', false);
                btn.html(originalHtml);
            }
        });
    }

    // Bulk action button handlers
    $('#bulk-enable-btn').on('click', function() {
        const category = $('#bulk-category-select').val();
        const plugin = $('#bulk-plugin-select').val();
        bulkToggleByCategory(category, plugin, true);
    });

    $('#bulk-disable-btn').on('click', function() {
        const category = $('#bulk-category-select').val();
        const plugin = $('#bulk-plugin-select').val();
        bulkToggleByCategory(category, plugin, false);
    });

    // =========================================================================
    // Top-level tab switching
    // =========================================================================

    function switchTab(tabName) {
        if (state.activeTab === tabName) return;
        state.activeTab = tabName;

        $('.fac-top-tab').removeClass('active');
        $(`.fac-top-tab[data-tab="${tabName}"]`).addClass('active');

        $('.fac-tab-panel').removeClass('active');
        $(`#tab-panel-${tabName}`).addClass('active');

        if (tabName === 'prompts' && state.promptsData.length === 0) {
            loadPromptTemplatesView();
        } else if (tabName === 'skills' && state.skillsData.length === 0) {
            loadSkillsView();
        }
    }

    $('.fac-top-tab').on('click', function() {
        switchTab($(this).data('tab'));
    });

    // =========================================================================
    // Prompt Templates tab
    // =========================================================================

    function loadPromptTemplatesView() {
        $('#prompt-templates-list').html(
            '<div style="padding:20px;text-align:center;color:var(--text-muted);"><i class="fa fa-spinner fa-spin"></i> Loading...</div>'
        );
        frappe.call({
            method: "frappe_assistant_core.api.admin_api.get_prompt_templates_list",
            callback: function(response) {
                if (response.message && response.message.success) {
                    state.promptsData = response.message.templates;
                    renderPromptTemplatesList();
                } else {
                    $('#prompt-templates-list').html(
                        '<div style="padding:20px;text-align:center;color:var(--red-500);">Failed to load prompt templates</div>'
                    );
                }
            },
            error: function() {
                $('#prompt-templates-list').html(
                    '<div style="padding:20px;text-align:center;color:var(--red-500);">Error loading prompt templates</div>'
                );
            }
        });
    }

    function renderPromptTemplatesList() {
        const searchTerm = $('#prompt-search').val().toLowerCase();
        const statusFilter = $('#prompt-status-filter').val();

        const filtered = state.promptsData.filter(t => {
            if (searchTerm && !t.title.toLowerCase().includes(searchTerm) &&
                !(t.prompt_id || '').toLowerCase().includes(searchTerm)) return false;
            if (statusFilter && t.status !== statusFilter) return false;
            return true;
        });

        if (filtered.length === 0) {
            $('#prompt-templates-list').html(
                '<div style="padding:20px;text-align:center;color:var(--text-muted);">No templates match the filters</div>'
            );
            return;
        }

        const html = filtered.map(t => {
            const isToggling = state.toggleInProgress[`prompt_${t.name}`];
            const isPublished = t.status === 'Published';
            const statusClass = (t.status || 'draft').toLowerCase();
            const lastUsed = t.last_used ? frappe.datetime.str_to_user(t.last_used) : 'Never';

            return `
            <div class="fac-item-card ${isToggling ? 'toggle-in-progress' : ''}" data-name="${t.name}">
                <div class="fac-item-header">
                    <div class="fac-item-title">
                        ${frappe.utils.escape_html(t.title)}
                        <span class="fac-status-badge ${statusClass}">${t.status}</span>
                    </div>
                    <div class="fac-item-actions">
                        <button class="fac-tool-settings-btn fac-prompt-preview-btn"
                                data-name="${t.name}" title="Preview template">
                            <i class="fa fa-eye"></i>
                        </button>
                        <a href="/app/prompt-template/${encodeURIComponent(t.name)}" target="_blank"
                           class="fac-tool-settings-btn" title="Open in DocType">
                            <i class="fa fa-external-link"></i>
                        </a>
                        <label class="switch" style="margin:0;" title="${isPublished ? 'Click to unpublish' : 'Click to publish'}">
                            <input type="checkbox" class="fac-prompt-toggle"
                                   data-name="${t.name}"
                                   ${isPublished ? 'checked' : ''}
                                   ${isToggling ? 'disabled' : ''}>
                            <span class="slider round"></span>
                        </label>
                    </div>
                </div>
                <div class="fac-item-subtitle">${frappe.utils.escape_html(t.prompt_id || t.name)}</div>
                <div class="fac-item-meta">
                    ${t.category ? `<span class="fac-meta-chip"><i class="fa fa-folder-o"></i> ${frappe.utils.escape_html(t.category)}</span>` : ''}
                    <span class="fac-meta-chip"><i class="fa fa-eye"></i> ${t.visibility || 'Private'}</span>
                    ${t.is_system ? '<span class="fac-meta-chip system-chip">System</span>' : ''}
                    <span class="fac-meta-chip">Used ${t.use_count || 0}x</span>
                    <span class="fac-meta-chip"><i class="fa fa-clock-o"></i> ${lastUsed}</span>
                </div>
                <div class="fac-expand-panel" id="prompt-preview-${t.name}"></div>
            </div>`;
        }).join('');

        $('#prompt-templates-list').html(html);

        $('.fac-prompt-toggle').off('change').on('change', function() {
            togglePromptTemplateStatus($(this).data('name'), $(this).is(':checked'));
        });

        $('.fac-prompt-preview-btn').off('click').on('click', function() {
            showTemplatePreview($(this).data('name'));
        });
    }

    function togglePromptTemplateStatus(name, publish) {
        const stateKey = `prompt_${name}`;
        if (state.toggleInProgress[stateKey]) return;

        state.toggleInProgress[stateKey] = true;
        state.autoRefreshEnabled = false;

        const checkbox = $(`.fac-prompt-toggle[data-name="${name}"]`);
        const originalState = !publish;
        checkbox.prop('disabled', true);
        checkbox.closest('.fac-item-card').addClass('toggle-in-progress');

        frappe.call({
            method: "frappe_assistant_core.api.admin_api.toggle_prompt_template_status",
            args: { name: name, publish: publish ? 1 : 0 },
            callback: function(response) {
                if (response.message && response.message.success) {
                    frappe.show_alert({ message: response.message.message, indicator: publish ? 'green' : 'orange' });
                    const tmpl = state.promptsData.find(t => t.name === name);
                    if (tmpl) tmpl.status = response.message.new_status;
                    renderPromptTemplatesList();
                    loadStats();
                } else {
                    checkbox.prop('checked', originalState);
                    frappe.show_alert({ message: response.message?.message || 'Unknown error', indicator: 'red' });
                }
            },
            error: function() {
                checkbox.prop('checked', originalState);
                frappe.show_alert({ message: 'Error toggling template status', indicator: 'red' });
            },
            always: function() {
                delete state.toggleInProgress[stateKey];
                state.autoRefreshEnabled = true;
                checkbox.prop('disabled', false);
                checkbox.closest('.fac-item-card').removeClass('toggle-in-progress');
            }
        });
    }

    function showTemplatePreview(name) {
        const panel = $(`#prompt-preview-${name}`);
        const btn = $(`.fac-prompt-preview-btn[data-name="${name}"]`);

        if (panel.hasClass('open')) {
            panel.removeClass('open');
            btn.removeClass('active');
            return;
        }

        panel.addClass('open').html(
            '<div style="color:var(--text-muted);font-size:12px;"><i class="fa fa-spinner fa-spin"></i> Loading preview...</div>'
        );
        btn.addClass('active');

        frappe.call({
            method: "frappe_assistant_core.api.admin_api.preview_prompt_template",
            args: { name: name },
            callback: function(response) {
                if (response.message && response.message.success) {
                    const d = response.message;
                    const argsHtml = d.arguments && d.arguments.length > 0
                        ? d.arguments.map(a =>
                            `<span class="fac-tool-badge" title="${frappe.utils.escape_html(a.description || '')}">${frappe.utils.escape_html(a.argument_name)}${a.is_required ? '*' : ''}</span>`
                        ).join(' ')
                        : '<em style="color:var(--text-muted);">No arguments</em>';

                    const content = d.template_content || '';
                    const renderedContent = renderMarkdown(content);

                    panel.html(`
                        <div style="margin-bottom:10px;display:flex;align-items:center;gap:16px;flex-wrap:wrap;">
                            <span><strong style="font-size:11px;color:var(--text-muted);text-transform:uppercase;">Engine:</strong> ${frappe.utils.escape_html(d.rendering_engine || '')}</span>
                            <span><strong style="font-size:11px;color:var(--text-muted);text-transform:uppercase;">Arguments:</strong> ${argsHtml}</span>
                        </div>
                        <div class="fac-preview-content" style="font-size:13px;">${renderedContent}</div>
                    `);
                } else {
                    panel.html(`<div style="color:var(--red-500);">${response.message?.message || 'Failed to load preview'}</div>`);
                }
            },
            error: function() {
                panel.html('<div style="color:var(--red-500);">Error loading preview</div>');
            }
        });
    }

    $('#prompt-search').on('input', frappe.utils.debounce(function() {
        if (state.activeTab === 'prompts') renderPromptTemplatesList();
    }, 300));

    $('#prompt-status-filter').on('change', function() {
        if (state.activeTab === 'prompts') renderPromptTemplatesList();
    });

    $('#refresh-prompts').on('click', loadPromptTemplatesView);

    // =========================================================================
    // Skills tab
    // =========================================================================

    function loadSkillsView() {
        $('#skills-list').html(
            '<div style="padding:20px;text-align:center;color:var(--text-muted);"><i class="fa fa-spinner fa-spin"></i> Loading...</div>'
        );
        frappe.call({
            method: "frappe_assistant_core.api.admin_api.get_skills_list",
            callback: function(response) {
                if (response.message && response.message.success) {
                    state.skillsData = response.message.skills;
                    renderSkillsList();
                } else {
                    $('#skills-list').html(
                        '<div style="padding:20px;text-align:center;color:var(--red-500);">Failed to load skills</div>'
                    );
                }
            },
            error: function() {
                $('#skills-list').html(
                    '<div style="padding:20px;text-align:center;color:var(--red-500);">Error loading skills</div>'
                );
            }
        });
    }

    function renderSkillsList() {
        const searchTerm = $('#skill-search').val().toLowerCase();
        const typeFilter = $('#skill-type-filter').val();
        const statusFilter = $('#skill-status-filter').val();

        const filtered = state.skillsData.filter(s => {
            if (searchTerm && !s.title.toLowerCase().includes(searchTerm) &&
                !(s.skill_id || '').toLowerCase().includes(searchTerm)) return false;
            if (typeFilter && s.skill_type !== typeFilter) return false;
            if (statusFilter && s.status !== statusFilter) return false;
            return true;
        });

        if (filtered.length === 0) {
            $('#skills-list').html(
                '<div style="padding:20px;text-align:center;color:var(--text-muted);">No skills match the filters</div>'
            );
            return;
        }

        const html = filtered.map(s => {
            const isToggling = state.toggleInProgress[`skill_${s.name}`];
            const isPublished = s.status === 'Published';
            const statusClass = (s.status || 'draft').toLowerCase();
            const lastUsed = s.last_used ? frappe.datetime.str_to_user(s.last_used) : 'Never';

            return `
            <div class="fac-item-card ${isToggling ? 'toggle-in-progress' : ''}" data-name="${s.name}">
                <div class="fac-item-header">
                    <div class="fac-item-title">
                        ${frappe.utils.escape_html(s.title)}
                        <span class="fac-status-badge ${statusClass}">${s.status}</span>
                    </div>
                    <div class="fac-item-actions">
                        <button class="fac-tool-settings-btn fac-skill-content-btn"
                                data-name="${s.name}" title="View skill content">
                            <i class="fa fa-book"></i>
                        </button>
                        <a href="/app/fac-skill/${encodeURIComponent(s.name)}" target="_blank"
                           class="fac-tool-settings-btn" title="Open in DocType">
                            <i class="fa fa-external-link"></i>
                        </a>
                        <label class="switch" style="margin:0;" title="${isPublished ? 'Click to unpublish' : 'Click to publish'}">
                            <input type="checkbox" class="fac-skill-toggle"
                                   data-name="${s.name}"
                                   ${isPublished ? 'checked' : ''}
                                   ${isToggling ? 'disabled' : ''}>
                            <span class="slider round"></span>
                        </label>
                    </div>
                </div>
                <div class="fac-item-subtitle">${frappe.utils.escape_html(s.skill_id || s.name)}</div>
                <div class="fac-item-meta">
                    <span class="fac-meta-chip">${frappe.utils.escape_html(s.skill_type || '')}</span>
                    ${s.linked_tool ? `<span class="fac-meta-chip"><i class="fa fa-wrench"></i> ${frappe.utils.escape_html(s.linked_tool)}</span>` : ''}
                    <span class="fac-meta-chip"><i class="fa fa-eye"></i> ${s.visibility || 'Private'}</span>
                    ${s.is_system ? '<span class="fac-meta-chip system-chip">System</span>' : ''}
                    <span class="fac-meta-chip">Used ${s.use_count || 0}x</span>
                    <span class="fac-meta-chip"><i class="fa fa-clock-o"></i> ${lastUsed}</span>
                </div>
                <div class="fac-expand-panel" id="skill-content-${s.name}"></div>
            </div>`;
        }).join('');

        $('#skills-list').html(html);

        $('.fac-skill-toggle').off('change').on('change', function() {
            toggleSkillStatus($(this).data('name'), $(this).is(':checked'));
        });

        $('.fac-skill-content-btn').off('click').on('click', function() {
            showSkillContent($(this).data('name'));
        });
    }

    function toggleSkillStatus(name, publish) {
        const stateKey = `skill_${name}`;
        if (state.toggleInProgress[stateKey]) return;

        state.toggleInProgress[stateKey] = true;
        state.autoRefreshEnabled = false;

        const checkbox = $(`.fac-skill-toggle[data-name="${name}"]`);
        const originalState = !publish;
        checkbox.prop('disabled', true);
        checkbox.closest('.fac-item-card').addClass('toggle-in-progress');

        frappe.call({
            method: "frappe_assistant_core.api.admin_api.toggle_skill_status",
            args: { name: name, publish: publish ? 1 : 0 },
            callback: function(response) {
                if (response.message && response.message.success) {
                    frappe.show_alert({ message: response.message.message, indicator: publish ? 'green' : 'orange' });
                    const skill = state.skillsData.find(s => s.name === name);
                    if (skill) skill.status = response.message.new_status;
                    renderSkillsList();
                    loadStats();
                } else {
                    checkbox.prop('checked', originalState);
                    frappe.show_alert({ message: response.message?.message || 'Unknown error', indicator: 'red' });
                }
            },
            error: function() {
                checkbox.prop('checked', originalState);
                frappe.show_alert({ message: 'Error toggling skill status', indicator: 'red' });
            },
            always: function() {
                delete state.toggleInProgress[stateKey];
                state.autoRefreshEnabled = true;
                checkbox.prop('disabled', false);
                checkbox.closest('.fac-item-card').removeClass('toggle-in-progress');
            }
        });
    }

    function showSkillContent(name) {
        const panel = $(`#skill-content-${name}`);
        const btn = $(`.fac-skill-content-btn[data-name="${name}"]`);

        if (panel.hasClass('open')) {
            panel.removeClass('open');
            btn.removeClass('active');
            return;
        }

        panel.addClass('open').html(
            '<div style="color:var(--text-muted);font-size:12px;"><i class="fa fa-spinner fa-spin"></i> Loading content...</div>'
        );
        btn.addClass('active');

        frappe.call({
            method: "frappe.client.get_value",
            args: { doctype: "FAC Skill", filters: { name: name }, fieldname: "content" },
            callback: function(response) {
                if (response.message && response.message.content) {
                    const rendered = renderMarkdown(response.message.content);
                    panel.html(`<div style="font-size:13px;">${rendered}</div>`);
                } else {
                    panel.html('<div style="color:var(--text-muted);">No content available</div>');
                }
            },
            error: function() {
                panel.html('<div style="color:var(--red-500);">Error loading content</div>');
            }
        });
    }

    $('#skill-search').on('input', frappe.utils.debounce(function() {
        if (state.activeTab === 'skills') renderSkillsList();
    }, 300));

    $('#skill-type-filter, #skill-status-filter').on('change', function() {
        if (state.activeTab === 'skills') renderSkillsList();
    });

    $('#refresh-skills').on('click', loadSkillsView);

    // Initial load
    loadServerStatus();
    loadStats();
    loadToolRegistry();
    loadRecentActivity();

    // Auto-refresh every 30 seconds (respects autoRefreshEnabled flag)
    setInterval(function() {
        // Skip auto-refresh if disabled or any toggle is in progress
        if (!state.autoRefreshEnabled || Object.keys(state.toggleInProgress).length > 0) {
            return;
        }

        loadServerStatus();
        loadStats();
        loadRecentActivity();
        // Note: We intentionally don't auto-refresh loadToolRegistry() here
        // to avoid interfering with user toggle interactions
    }, 30000);
};
