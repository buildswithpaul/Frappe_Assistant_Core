/*
 * Frappe Assistant Core - FAC Admin Plugins View
 * Copyright (C) 2025 Paul Clinton
 * AGPL-3.0 License
 */

frappe.provide('frappe.fac_admin');

/**
 * Plugins view module for FAC Admin.
 * Handles displaying and toggling plugins.
 */
frappe.fac_admin.PluginsView = class {
    constructor(container, callbacks) {
        this.$container = $(container);
        this.callbacks = callbacks || {};
    }

    /**
     * Load and render the plugins view
     */
    load() {
        const state = frappe.fac_admin.state;

        // Skip if any toggle is in progress
        if (state.isToggling()) {
            return;
        }

        frappe.fac_admin.API.getPluginStats().then(response => {
            if (response.message && response.message.plugins) {
                this.render(response.message.plugins);
            }
        }).catch(() => {
            this.$container.html(
                '<div style="padding: 20px; text-align: center; color: var(--red-500);">Failed to load plugins</div>'
            );
        });
    }

    /**
     * Render the plugins list
     * @param {Array} plugins - List of plugin objects
     */
    render(plugins) {
        const state = frappe.fac_admin.state;

        if (plugins.length === 0) {
            this.$container.html(
                '<div style="padding: 20px; text-align: center; color: var(--text-muted);">No plugins available</div>'
            );
            return;
        }

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
            `;
        }).join('');

        this.$container.html(pluginsHtml);
        this.bindEvents();
    }

    /**
     * Bind event handlers
     */
    bindEvents() {
        const self = this;

        this.$container.find('.fac-plugin-toggle').off('change').on('change', function() {
            const pluginName = $(this).data('plugin');
            const isEnabled = $(this).is(':checked');
            self.togglePlugin(pluginName, isEnabled, $(this));
        });
    }

    /**
     * Toggle a plugin's enabled state
     * @param {string} pluginName - Plugin identifier
     * @param {boolean} enabled - Enable or disable
     * @param {jQuery} $checkbox - The checkbox element
     */
    togglePlugin(pluginName, enabled, $checkbox) {
        const state = frappe.fac_admin.state;
        const stateKey = `plugin_${pluginName}`;

        // Prevent duplicate toggle
        if (state.toggleInProgress[stateKey]) {
            return;
        }

        // Mark as in progress
        state.startToggle(stateKey);

        // Update UI to show in-progress state
        const originalState = !enabled;
        $checkbox.prop('disabled', true);
        $checkbox.closest('.fac-plugin-item').addClass('toggle-in-progress');

        frappe.fac_admin.API.togglePlugin(pluginName, enabled).then(response => {
            if (response.message && response.message.success) {
                frappe.show_alert({
                    message: response.message.message,
                    indicator: enabled ? 'green' : 'orange'
                });

                // Trigger stats refresh callback
                if (this.callbacks.onStatsChange) {
                    this.callbacks.onStatsChange();
                }
            } else {
                // Reset checkbox to original state on error
                $checkbox.prop('checked', originalState);
                frappe.show_alert({
                    message: response.message?.message || 'Unknown error',
                    indicator: 'red'
                });
            }
        }).catch(() => {
            // Reset checkbox to original state on error
            $checkbox.prop('checked', originalState);
            frappe.show_alert({
                message: 'Error toggling plugin',
                indicator: 'red'
            });
        }).finally(() => {
            // Clear in-progress state
            state.endToggle(stateKey);

            // Re-enable checkbox and remove in-progress styling
            $checkbox.prop('disabled', false);
            $checkbox.closest('.fac-plugin-item').removeClass('toggle-in-progress');
        });
    }
};
