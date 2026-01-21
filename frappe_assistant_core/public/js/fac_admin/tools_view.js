/*
 * Frappe Assistant Core - FAC Admin Tools View
 * Copyright (C) 2025 Paul Clinton
 * AGPL-3.0 License
 */

frappe.provide('frappe.fac_admin');

/**
 * Tools view module for FAC Admin.
 * Handles displaying and managing individual tools.
 */
frappe.fac_admin.ToolsView = class {
    constructor(container, callbacks) {
        this.$container = $(container);
        this.callbacks = callbacks || {};
        this.toolsData = [];
    }

    /**
     * Load and render the tools view
     */
    load() {
        const state = frappe.fac_admin.state;

        // Skip if any toggle is in progress
        if (state.isToggling()) {
            return;
        }

        frappe.fac_admin.API.getToolConfigurations().then(response => {
            if (response.message && response.message.success) {
                this.toolsData = response.message.tools;
                state.toolsData = this.toolsData;
                this.populateFilters();
                this.render();
            } else {
                this.$container.html(
                    '<div style="padding: 20px; text-align: center; color: var(--red-500);">Failed to load tools</div>'
                );
            }
        }).catch(() => {
            this.$container.html(
                '<div style="padding: 20px; text-align: center; color: var(--red-500);">Failed to load tools</div>'
            );
        });
    }

    /**
     * Populate filter dropdowns with plugins
     */
    populateFilters() {
        const plugins = [...new Set(this.toolsData.map(t => t.plugin_name))];
        const pluginFilter = $('#plugin-filter');
        const bulkPluginSelect = $('#bulk-plugin-select');

        pluginFilter.find('option:gt(0)').remove();
        bulkPluginSelect.find('option:gt(0)').remove();

        plugins.forEach(p => {
            const label = p.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase());
            pluginFilter.append(`<option value="${p}">${label}</option>`);
            bulkPluginSelect.append(`<option value="${p}">${label}</option>`);
        });
    }

    /**
     * Render filtered tools list
     */
    render() {
        const state = frappe.fac_admin.state;
        const searchTerm = $('#tool-search').val()?.toLowerCase() || '';
        const categoryFilter = $('#category-filter').val();
        const pluginFilter = $('#plugin-filter').val();

        let filteredTools = this.toolsData.filter(tool => {
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
            this.$container.html(
                '<div style="padding: 20px; text-align: center; color: var(--text-muted);">No tools match the filters</div>'
            );
            return;
        }

        const toolsHtml = filteredTools.map(tool => this.renderToolItem(tool)).join('');
        this.$container.html(toolsHtml);
        this.bindEvents();
    }

    /**
     * Render a single tool item
     * @param {Object} tool - Tool data
     */
    renderToolItem(tool) {
        const state = frappe.fac_admin.state;
        const isToggling = state.toggleInProgress[`tool_${tool.name}`];
        const pluginDisabled = !tool.plugin_enabled;
        const isPanelOpen = state.isConfigPanelOpen(tool.name);
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
    }

    /**
     * Bind event handlers
     */
    bindEvents() {
        const self = this;

        // Tool toggle handlers
        this.$container.find('.fac-tool-toggle').off('change').on('change', function() {
            const toolName = $(this).data('tool');
            const isEnabled = $(this).is(':checked');
            self.toggleTool(toolName, isEnabled, $(this));
        });

        // Settings button handlers
        this.$container.find('.fac-tool-settings-btn').off('click').on('click', function() {
            const toolName = $(this).data('tool');
            self.toggleConfigPanel(toolName);
        });

        // Role mode change handlers
        this.$container.find('.fac-role-mode-select').off('change').on('change', function() {
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
        this.$container.find('.fac-add-role-btn').off('click').on('click', function() {
            const toolName = $(this).data('tool');
            self.showAddRoleDialog(toolName);
        });

        // Remove role handlers
        this.$container.find('.remove-role').off('click').on('click', function() {
            const toolName = $(this).data('tool');
            const role = $(this).data('role');
            self.removeRole(toolName, role);
        });

        // Cancel button handlers
        this.$container.find('.fac-config-cancel').off('click').on('click', function() {
            const toolName = $(this).data('tool');
            self.toggleConfigPanel(toolName, false);
            self.render();
        });

        // Save button handlers
        this.$container.find('.fac-config-save').off('click').on('click', function() {
            const toolName = $(this).data('tool');
            self.saveToolConfig(toolName);
        });
    }

    /**
     * Toggle config panel visibility
     * @param {string} toolName - Tool name
     * @param {boolean} [forceState] - Optional forced state
     */
    toggleConfigPanel(toolName, forceState) {
        const state = frappe.fac_admin.state;
        const panel = $(`#config-panel-${toolName}`);
        const btn = $(`.fac-tool-settings-btn[data-tool="${toolName}"]`);

        const isOpen = state.toggleConfigPanel(toolName, forceState);

        if (isOpen) {
            panel.addClass('open');
            btn.addClass('active');
            // Load roles if not already loaded
            if (state.availableRoles.length === 0) {
                this.loadAvailableRoles();
            }
        } else {
            panel.removeClass('open');
            btn.removeClass('active');
        }
    }

    /**
     * Load available roles
     */
    loadAvailableRoles() {
        const state = frappe.fac_admin.state;
        frappe.fac_admin.API.getAvailableRoles().then(response => {
            if (response.message && response.message.success) {
                state.availableRoles = response.message.roles;
            }
        });
    }

    /**
     * Show add role dialog
     * @param {string} toolName - Tool name
     */
    showAddRoleDialog(toolName) {
        const state = frappe.fac_admin.state;
        const tool = this.toolsData.find(t => t.name === toolName);
        const existingRoles = (tool?.role_access || []).map(r => r.role);
        const availableRoles = state.availableRoles.filter(r => !existingRoles.includes(r.name));

        if (availableRoles.length === 0) {
            frappe.show_alert({
                message: 'All available roles have been added',
                indicator: 'orange'
            });
            return;
        }

        const self = this;
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
                self.addRole(toolName, values.role);
                dialog.hide();
            }
        });
        dialog.show();
    }

    /**
     * Add role to tool
     * @param {string} toolName - Tool name
     * @param {string} role - Role name
     */
    addRole(toolName, role) {
        const tool = this.toolsData.find(t => t.name === toolName);
        if (!tool.role_access) {
            tool.role_access = [];
        }
        tool.role_access.push({ role: role, allow_access: 1 });

        const self = this;
        const container = $(`#role-tags-${toolName}`);
        const addBtn = container.find('.fac-add-role-btn');
        addBtn.before(`
            <span class="fac-role-tag" data-role="${role}">
                ${role}
                <i class="fa fa-times remove-role" data-tool="${toolName}" data-role="${role}"></i>
            </span>
        `);

        container.find(`.remove-role[data-role="${role}"]`).off('click').on('click', function() {
            self.removeRole(toolName, role);
        });
    }

    /**
     * Remove role from tool
     * @param {string} toolName - Tool name
     * @param {string} role - Role name
     */
    removeRole(toolName, role) {
        const tool = this.toolsData.find(t => t.name === toolName);
        if (tool && tool.role_access) {
            tool.role_access = tool.role_access.filter(r => r.role !== role);
        }
        $(`#role-tags-${toolName} .fac-role-tag[data-role="${role}"]`).remove();
    }

    /**
     * Save tool configuration
     * @param {string} toolName - Tool name
     */
    saveToolConfig(toolName) {
        const self = this;
        const tool = this.toolsData.find(t => t.name === toolName);
        const panel = $(`#config-panel-${toolName}`);

        const roleAccessMode = panel.find('.fac-role-mode-select').val();
        const category = panel.find('.fac-category-select').val();
        const roles = tool.role_access || [];

        const saveBtn = panel.find('.fac-config-save');
        saveBtn.prop('disabled', true).html('<i class="fa fa-spinner fa-spin"></i> Saving...');

        frappe.fac_admin.API.updateToolRoleAccess(toolName, roleAccessMode, roles).then(response => {
            if (response.message && response.message.success) {
                return frappe.fac_admin.API.updateToolCategory(toolName, category, true);
            } else {
                throw new Error(response.message?.message || 'Failed to save configuration');
            }
        }).then(catResponse => {
            if (catResponse.message && catResponse.message.success) {
                frappe.show_alert({
                    message: 'Tool configuration saved',
                    indicator: 'green'
                });

                tool.role_access_mode = roleAccessMode;
                tool.category = category;

                self.toggleConfigPanel(toolName, false);
                self.load();
            } else {
                throw new Error(catResponse.message?.message || 'Failed to update category');
            }
        }).catch(error => {
            frappe.show_alert({
                message: error.message || 'Error saving configuration',
                indicator: 'red'
            });
        }).finally(() => {
            saveBtn.prop('disabled', false).html('Save Changes');
        });
    }

    /**
     * Toggle a tool's enabled state
     * @param {string} toolName - Tool name
     * @param {boolean} enabled - Enable or disable
     * @param {jQuery} $checkbox - The checkbox element
     */
    toggleTool(toolName, enabled, $checkbox) {
        const self = this;
        const state = frappe.fac_admin.state;
        const stateKey = `tool_${toolName}`;

        if (state.toggleInProgress[stateKey]) {
            return;
        }

        state.startToggle(stateKey);

        const originalState = !enabled;
        $checkbox.prop('disabled', true);
        $checkbox.closest('.fac-tool-item-detailed').addClass('toggle-in-progress');

        frappe.fac_admin.API.toggleTool(toolName, enabled).then(response => {
            if (response.message && response.message.success) {
                frappe.show_alert({
                    message: response.message.message,
                    indicator: enabled ? 'green' : 'orange'
                });

                const tool = self.toolsData.find(t => t.name === toolName);
                if (tool) {
                    tool.tool_enabled = enabled;
                    tool.effectively_enabled = tool.plugin_enabled && enabled;
                }

                if (self.callbacks.onStatsChange) {
                    self.callbacks.onStatsChange();
                }
            } else {
                $checkbox.prop('checked', originalState);
                frappe.show_alert({
                    message: response.message?.message || 'Unknown error',
                    indicator: 'red'
                });
            }
        }).catch(() => {
            $checkbox.prop('checked', originalState);
            frappe.show_alert({
                message: 'Error toggling tool',
                indicator: 'red'
            });
        }).finally(() => {
            state.endToggle(stateKey);
            $checkbox.prop('disabled', false);
            $checkbox.closest('.fac-tool-item-detailed').removeClass('toggle-in-progress');
        });
    }

    /**
     * Bulk toggle tools by category
     * @param {string|null} category - Category filter
     * @param {string|null} plugin - Plugin filter
     * @param {boolean} enabled - Enable or disable
     */
    bulkToggle(category, plugin, enabled) {
        const self = this;

        $('#bulk-enable-btn, #bulk-disable-btn').prop('disabled', true);
        const btn = enabled ? $('#bulk-enable-btn') : $('#bulk-disable-btn');
        const originalHtml = btn.html();
        btn.html(`<i class="fa fa-spinner fa-spin"></i> ${enabled ? 'Enabling' : 'Disabling'}...`);

        frappe.fac_admin.API.bulkToggleToolsByCategory(category, plugin, enabled).then(response => {
            if (response.message && response.message.success) {
                frappe.show_alert({
                    message: response.message.message,
                    indicator: enabled ? 'green' : 'orange'
                });
                self.load();
                if (self.callbacks.onStatsChange) {
                    self.callbacks.onStatsChange();
                }
            } else {
                frappe.show_alert({
                    message: response.message?.message || `Failed to ${enabled ? 'enable' : 'disable'} tools`,
                    indicator: 'red'
                });
            }
        }).catch(() => {
            frappe.show_alert({
                message: `Error: Failed to ${enabled ? 'enable' : 'disable'} tools`,
                indicator: 'red'
            });
        }).finally(() => {
            $('#bulk-enable-btn, #bulk-disable-btn').prop('disabled', false);
            btn.html(originalHtml);
        });
    }
};
