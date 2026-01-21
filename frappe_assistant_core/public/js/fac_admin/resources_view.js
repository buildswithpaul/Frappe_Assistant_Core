/*
 * Frappe Assistant Core - FAC Admin Resources View
 * Copyright (C) 2025 Paul Clinton
 * AGPL-3.0 License
 */

frappe.provide('frappe.fac_admin');

/**
 * Resources view module for FAC Admin.
 * Handles displaying and managing MCP Resources (tool documentation).
 */
frappe.fac_admin.ResourcesView = class {
    constructor(container, callbacks) {
        this.$container = $(container);
        this.callbacks = callbacks || {};
        this.toolDocs = [];
        this.resourcesEnabled = false;
    }

    /**
     * Load and render the resources view
     */
    load() {
        this.$container.html(
            '<div style="padding: 20px; text-align: center; color: var(--text-muted);"><i class="fa fa-spinner fa-spin"></i> Loading resources...</div>'
        );

        // Load tool docs and resource stats
        Promise.all([
            frappe.fac_admin.API.getToolDocsList(),
            frappe.fac_admin.API.getResourceStats()
        ]).then(([toolDocsResponse, statsResponse]) => {
            if (toolDocsResponse.message) {
                this.toolDocs = toolDocsResponse.message.tool_docs || [];
            }
            if (statsResponse.message && statsResponse.message.success) {
                this.resourcesEnabled = statsResponse.message.resources_enabled || false;
            }

            this.render();
        }).catch(error => {
            console.error('Failed to load resources:', error);
            this.$container.html(
                '<div style="padding: 20px; text-align: center; color: var(--red-500);">Failed to load resources</div>'
            );
        });
    }

    /**
     * Render the resources view
     */
    render() {
        const toolDocsHtml = this.renderToolDocs();
        const toggleStatusClass = this.resourcesEnabled ? 'fac-toggle-enabled' : 'fac-toggle-disabled';
        const toggleStatusText = this.resourcesEnabled ? 'Enabled' : 'Disabled';
        const toggleStatusIcon = this.resourcesEnabled ? 'fa-check-circle' : 'fa-circle-o';

        this.$container.html(`
            <div class="fac-resources-container">
                <!-- Resources Feature Toggle Section -->
                <div class="fac-resources-section fac-resources-toggle-section">
                    <div class="fac-resources-section-header">
                        <div class="fac-resources-section-title">
                            <i class="fa fa-sliders"></i>
                            Resources Feature
                        </div>
                        <span class="fac-toggle-status ${toggleStatusClass}">
                            <i class="fa ${toggleStatusIcon}"></i> ${toggleStatusText}
                        </span>
                    </div>
                    <div class="fac-resources-description">
                        When enabled, tool descriptions are minimized and detailed documentation is served via MCP resources.
                        This reduces LLM context usage for clients that support MCP resources.
                    </div>
                    <div class="fac-toggle-control">
                        <label class="fac-switch">
                            <input type="checkbox" id="resources-feature-toggle" ${this.resourcesEnabled ? 'checked' : ''}>
                            <span class="fac-slider"></span>
                        </label>
                        <span class="fac-toggle-label">
                            ${this.resourcesEnabled ? 'Minimal descriptions with resource hints' : 'Full tool descriptions (default)'}
                        </span>
                    </div>
                    <div class="fac-resources-info-box">
                        <p><strong>How it works:</strong></p>
                        <ul>
                            <li><strong>Disabled (default)</strong> - Tools have full descriptions, no resources served</li>
                            <li><strong>Enabled</strong> - Tools have minimal descriptions with resource hints, tool documentation served as MCP resources</li>
                        </ul>
                        <p><strong>Access resources via:</strong> <code>fac://tools/{tool_name}</code></p>
                    </div>
                </div>

                <!-- Tool Documentation Section -->
                <div class="fac-resources-section">
                    <div class="fac-resources-section-header">
                        <div class="fac-resources-section-title">
                            <i class="fa fa-file-text-o"></i>
                            Tool Documentation
                        </div>
                        <span class="fac-resources-count">${this.toolDocs.length} docs</span>
                    </div>
                    <div class="fac-resources-description">
                        Markdown documentation files for tools. Located in <code>docs/tools/*.md</code>
                    </div>
                    <div class="fac-tool-docs-list">
                        ${toolDocsHtml}
                    </div>
                </div>
            </div>
        `);

        this.bindEvents();
    }

    /**
     * Render tool documentation list
     */
    renderToolDocs() {
        if (this.toolDocs.length === 0) {
            return '<div class="fac-no-docs">No tool documentation files found. Create <code>.md</code> files in <code>docs/tools/</code> to add documentation.</div>';
        }

        return this.toolDocs.map(doc => {
            const toolName = doc.name || doc.tool_name;
            const exists = doc.size > 0;
            const statusClass = exists ? 'fac-doc-exists' : 'fac-doc-missing';
            const statusIcon = exists ? 'fa-check-circle' : 'fa-exclamation-circle';
            const statusText = exists ? 'Available' : 'Missing';

            return `
                <div class="fac-resource-item ${statusClass}">
                    <div class="fac-resource-info">
                        <div class="fac-resource-name">
                            <i class="fa fa-file-text-o"></i>
                            ${toolName}
                        </div>
                        <div class="fac-resource-uri">
                            <code>${doc.uri || 'fac://tools/' + toolName}</code>
                        </div>
                    </div>
                    <div class="fac-resource-status">
                        <span class="fac-doc-status ${statusClass}">
                            <i class="fa ${statusIcon}"></i> ${statusText}
                        </span>
                    </div>
                </div>
            `;
        }).join('');
    }

    /**
     * Bind event handlers
     */
    bindEvents() {
        const self = this;

        // Resources feature toggle
        $('#resources-feature-toggle').off('change').on('change', function() {
            const enabled = $(this).is(':checked');
            self.toggleResourcesFeature(enabled);
        });
    }

    /**
     * Toggle resources feature
     * @param {boolean} enabled - Enable or disable
     */
    toggleResourcesFeature(enabled) {
        const toggle = $('#resources-feature-toggle');
        const originalState = !enabled;

        // Disable toggle during save
        toggle.prop('disabled', true);

        frappe.fac_admin.API.toggleResourcesFeature(enabled).then(response => {
            if (response.message && response.message.success) {
                this.resourcesEnabled = enabled;

                frappe.show_alert({
                    message: response.message.message,
                    indicator: 'green'
                });

                // Trigger stats refresh callback
                if (this.callbacks.onStatsChange) {
                    this.callbacks.onStatsChange();
                }

                // Re-render to update UI
                this.render();
            } else {
                // Revert toggle on failure
                toggle.prop('checked', originalState);
                frappe.show_alert({
                    message: response.message?.message || 'Failed to update resources feature',
                    indicator: 'red'
                });
            }
        }).catch(error => {
            // Revert toggle on error
            toggle.prop('checked', originalState);
            frappe.show_alert({
                message: 'Error updating resources feature',
                indicator: 'red'
            });
        }).finally(() => {
            toggle.prop('disabled', false);
        });
    }
};
