// fac_admin_tools.js
// Tool registry, plugin management, server status, stats, and bulk actions
// for FAC Admin page.
// Extracted from fac_admin.js lines 1096-1957

(function() {
    const ns = frappe.fac_admin;

    // Load server status
    ns.loadServerStatus = function() {
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

                    const statusPill = $('#server-status-pill');
                    statusText.text('Frappe Assistant Core');
                    if (isEnabled) {
                        statusIcon.removeClass('inactive').addClass('active');
                        statusPill
                            .removeClass('fac-status-pill--stopped')
                            .addClass('fac-status-pill--running')
                            .html('<span class="fac-status-dot" aria-hidden="true"></span> Running');
                        toggleBtn.removeClass('btn-primary').addClass('btn-warning');
                        toggleText.html('<i class="fa fa-stop" aria-hidden="true"></i> Disable');
                    } else {
                        statusIcon.removeClass('active').addClass('inactive');
                        statusPill
                            .removeClass('fac-status-pill--running')
                            .addClass('fac-status-pill--stopped')
                            .html('<span class="fac-status-dot" aria-hidden="true"></span> Stopped');
                        toggleBtn.removeClass('btn-warning').addClass('btn-primary');
                        toggleText.html('<i class="fa fa-play" aria-hidden="true"></i> Enable');
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
    };

    // Toggle server
    ns.toggleServer = function() {
        frappe.call({
            method: "frappe_assistant_core.api.admin_api.get_server_settings",
            callback: function(response) {
                if (!response.message) return;
                const currentState = response.message.server_enabled;
                const newState = currentState ? 0 : 1;

                const doToggle = function() {
                    frappe.call({
                        method: "frappe_assistant_core.api.admin_api.update_server_settings",
                        args: { server_enabled: newState },
                        callback: function(result) {
                            if (result.message) {
                                frappe.show_alert({
                                    message: newState ? 'FAC Server Enabled' : 'FAC Server Disabled',
                                    indicator: newState ? 'green' : 'orange'
                                });
                                setTimeout(function() { ns.loadServerStatus(); }, 300);
                            }
                        }
                    });
                };

                if (newState === 0) {
                    frappe.confirm(
                        'Disable the FAC server? All MCP clients will lose access until it is re-enabled.',
                        doToggle
                    );
                } else {
                    doToggle();
                }
            }
        });
    };

    // Load plugin and tool stats
    ns.loadStats = function() {
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
    };

    // Store tools data for filtering
    ns.toolsData = [];

    // Load tool registry based on current view mode
    ns.loadToolRegistry = function() {
        if (ns.state.viewMode === 'plugins') {
            ns.loadPluginView();
        } else {
            ns.loadToolsView();
        }
    };

    // Load plugin view (grouped by plugin)
    ns.loadPluginView = function() {
        // Skip if any toggle is in progress
        if (Object.keys(ns.state.toggleInProgress).length > 0) {
            return;
        }

        frappe.call({
            method: "frappe_assistant_core.api.admin_api.get_plugin_stats",
            callback: function(response) {
                if (response.message && response.message.plugins) {
                    const plugins = response.message.plugins;
                    if (plugins.length > 0) {
                        const pluginsHtml = plugins.map(plugin => {
                            const isToggling = ns.state.toggleInProgress[`plugin_${plugin.plugin_id}`];
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
                                                   aria-label="Enable plugin ${frappe.utils.escape_html(plugin.name)}"
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
                            ns.togglePlugin(pluginName, isEnabled);
                        });
                    } else {
                        $('#tool-registry').html(`
                            <div class="fac-empty-state">
                                <i class="fa fa-cube" aria-hidden="true"></i>
                                <div class="fac-empty-title">No plugins installed</div>
                                <div class="fac-empty-subtitle">Install plugins to start registering tools with the MCP server.</div>
                            </div>
                        `);
                    }
                }
            },
            error: function() {
                $('#tool-registry').html('<div style="padding: 20px; text-align: center; color: var(--red-500);">Failed to load plugins</div>');
            }
        });
    };

    // Load individual tools view
    ns.loadToolsView = function() {
        // Skip if any toggle is in progress
        if (Object.keys(ns.state.toggleInProgress).length > 0) {
            return;
        }

        frappe.call({
            method: "frappe_assistant_core.api.admin_api.get_tool_configurations",
            callback: function(response) {
                if (response.message && response.message.success) {
                    ns.toolsData = response.message.tools;

                    // Populate plugin filter
                    const plugins = [...new Set(ns.toolsData.map(t => t.plugin_name))];
                    const pluginFilter = $('#plugin-filter');
                    pluginFilter.find('option:gt(0)').remove();
                    plugins.forEach(p => {
                        const label = p.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase());
                        pluginFilter.append(`<option value="${p}">${label}</option>`);
                    });

                    ns.renderToolsList();
                    ns.updateBulkScopeCount();
                } else {
                    $('#tool-registry').html('<div style="padding: 20px; text-align: center; color: var(--red-500);">Failed to load tools</div>');
                }
            },
            error: function() {
                $('#tool-registry').html('<div style="padding: 20px; text-align: center; color: var(--red-500);">Failed to load tools</div>');
            }
        });
    };

    // Reset tool search / filters to defaults and re-render
    ns.clearToolFilters = function() {
        $('#tool-search').val('');
        $('#category-filter').val('');
        $('#plugin-filter').val('');
        ns.renderToolsList();
    };

    // Render filtered tools list
    ns.renderToolsList = function() {
        const searchTerm = $('#tool-search').val().toLowerCase();
        const categoryFilter = $('#category-filter').val();
        const pluginFilter = $('#plugin-filter').val();

        let filteredTools = ns.toolsData.filter(tool => {
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
            const zeroData = !ns.toolsData || ns.toolsData.length === 0;
            if (zeroData) {
                $('#tool-registry').html(`
                    <div class="fac-empty-state">
                        <i class="fa fa-wrench" aria-hidden="true"></i>
                        <div class="fac-empty-title">No tools registered</div>
                        <div class="fac-empty-subtitle">Enable a plugin in the Plugins tab to register tools.</div>
                    </div>
                `);
            } else {
                $('#tool-registry').html(`
                    <div class="fac-empty-state">
                        <i class="fa fa-search" aria-hidden="true"></i>
                        <div class="fac-empty-title">No tools match the current filters</div>
                        <button type="button" class="btn btn-xs btn-default fac-clear-filters-btn">Clear filters</button>
                    </div>
                `);
                $('.fac-clear-filters-btn').on('click', ns.clearToolFilters);
            }
            return;
        }

        const toolsHtml = filteredTools.map(tool => {
            const isToggling = ns.state.toggleInProgress[`tool_${tool.name}`];
            const pluginDisabled = !tool.plugin_enabled;
            const isPanelOpen = ns.state.openConfigPanels[tool.name];
            const roleTagsHtml = (tool.role_access || []).map(r =>
                `<span class="fac-role-tag" data-role="${r.role}">
                    ${r.role}
                    <button type="button" class="fac-role-remove-btn" aria-label="Remove role ${frappe.utils.escape_html(r.role)}" data-tool="${tool.name}" data-role="${r.role}">
                        <i class="fa fa-times remove-role" data-tool="${tool.name}" data-role="${r.role}" aria-hidden="true"></i>
                    </button>
                </span>`
            ).join('');

            const q = searchTerm;
            const titleHtml = ns.highlight(tool.display_name, q);
            const descHtml = ns.highlight(tool.description || 'No description available', q);
            return `
                <div class="fac-tool-item-detailed ${isToggling ? 'toggle-in-progress' : ''} ${pluginDisabled ? 'fac-disabled-overlay' : ''}" data-tool-name="${tool.name}">
                    <div class="fac-tool-header">
                        <div class="fac-tool-title">
                            ${titleHtml}
                            <span class="fac-category-badge ${tool.category}">${tool.category_label}</span>
                        </div>
                        <div class="fac-tool-actions">
                            <button class="fac-tool-settings-btn ${isPanelOpen ? 'active' : ''}"
                                    data-tool="${tool.name}"
                                    aria-label="Configure role access for ${frappe.utils.escape_html(tool.display_name)}"
                                    aria-expanded="${isPanelOpen ? 'true' : 'false'}"
                                    title="Configure role access">
                                <i class="fa fa-cog" aria-hidden="true"></i>
                            </button>
                            <label class="switch" style="margin: 0;">
                                <input type="checkbox" class="fac-tool-toggle"
                                       data-tool="${tool.name}"
                                       aria-label="Enable tool ${frappe.utils.escape_html(tool.display_name)}"
                                       ${tool.tool_enabled ? 'checked' : ''}
                                       ${isToggling || pluginDisabled ? 'disabled' : ''}>
                                <span class="slider round"></span>
                            </label>
                        </div>
                    </div>
                    <div class="fac-tool-description-wrap">
                        <div class="fac-tool-description">${descHtml}</div>
                        <button type="button" class="fac-desc-toggle" aria-expanded="false">Show more</button>
                    </div>
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
                                    <button type="button" class="fac-add-role-btn" data-tool="${tool.name}" aria-label="Add role to ${frappe.utils.escape_html(tool.display_name)}">
                                        <i class="fa fa-plus" aria-hidden="true"></i> Add Role
                                    </button>
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

        // Hide "Show more" toggle on descriptions that don't actually overflow.
        $('#tool-registry .fac-tool-description-wrap').each(function() {
            const desc = $(this).find('.fac-tool-description')[0];
            const toggle = $(this).find('.fac-desc-toggle');
            if (desc && desc.scrollHeight <= desc.clientHeight + 2) {
                toggle.hide();
            }
        });

        // Show more / Show less for long tool descriptions
        $('.fac-desc-toggle').off('click').on('click', function() {
            const $wrap = $(this).closest('.fac-tool-description-wrap');
            const expanded = $wrap.toggleClass('expanded').hasClass('expanded');
            $(this)
                .text(expanded ? 'Show less' : 'Show more')
                .attr('aria-expanded', expanded ? 'true' : 'false');
        });

        // Add toggle handlers
        $('.fac-tool-toggle').off('change').on('change', function() {
            const toolName = $(this).data('tool');
            const isEnabled = $(this).is(':checked');
            ns.toggleTool(toolName, isEnabled);
        });

        // Add settings button handlers
        $('.fac-tool-settings-btn').off('click').on('click', function() {
            const toolName = $(this).data('tool');
            ns.toggleConfigPanel(toolName);
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
            ns.showAddRoleDialog(toolName);
        });

        // Remove role handlers
        $('.remove-role').off('click').on('click', function() {
            const toolName = $(this).data('tool');
            const role = $(this).data('role');
            ns.removeRole(toolName, role);
        });

        // Cancel button handlers
        $('.fac-config-cancel').off('click').on('click', function() {
            const toolName = $(this).data('tool');
            ns.toggleConfigPanel(toolName, false);
            // Re-render to reset any unsaved changes
            ns.renderToolsList();
        });

        // Save button handlers
        $('.fac-config-save').off('click').on('click', function() {
            const toolName = $(this).data('tool');
            ns.saveToolConfig(toolName);
        });
    };

    // Toggle config panel visibility
    ns.toggleConfigPanel = function(toolName, forceState) {
        const panel = $(`#config-panel-${toolName}`);
        const btn = $(`.fac-tool-settings-btn[data-tool="${toolName}"]`);

        if (forceState === false || (forceState === undefined && panel.hasClass('open'))) {
            panel.removeClass('open');
            btn.removeClass('active');
            delete ns.state.openConfigPanels[toolName];
        } else {
            panel.addClass('open');
            btn.addClass('active');
            ns.state.openConfigPanels[toolName] = true;
            // Load roles if not already loaded
            if (ns.state.availableRoles.length === 0) {
                ns.loadAvailableRoles();
            }
        }
    };

    // Load available roles
    ns.loadAvailableRoles = function() {
        frappe.call({
            method: "frappe_assistant_core.api.admin_api.get_available_roles",
            callback: function(response) {
                if (response.message && response.message.success) {
                    ns.state.availableRoles = response.message.roles;
                }
            }
        });
    };

    // Show add role dialog
    ns.showAddRoleDialog = function(toolName) {
        const tool = ns.toolsData.find(t => t.name === toolName);
        const existingRoles = (tool?.role_access || []).map(r => r.role);
        const availableRoles = ns.state.availableRoles.filter(r => !existingRoles.includes(r.name));

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
                ns.addRole(toolName, values.role);
                dialog.hide();
            }
        });
        dialog.show();
    };

    // Add role to tool
    ns.addRole = function(toolName, role) {
        const tool = ns.toolsData.find(t => t.name === toolName);
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
                <button type="button" class="fac-role-remove-btn" aria-label="Remove role ${frappe.utils.escape_html(role)}" data-tool="${toolName}" data-role="${role}">
                    <i class="fa fa-times remove-role" data-tool="${toolName}" data-role="${role}" aria-hidden="true"></i>
                </button>
            </span>
        `);

        // Re-attach remove handler
        container.find(`.remove-role[data-role="${role}"]`).off('click').on('click', function() {
            ns.removeRole(toolName, role);
        });
    };

    // Remove role from tool
    ns.removeRole = function(toolName, role) {
        const tool = ns.toolsData.find(t => t.name === toolName);
        if (tool && tool.role_access) {
            tool.role_access = tool.role_access.filter(r => r.role !== role);
        }
        $(`#role-tags-${toolName} .fac-role-tag[data-role="${role}"]`).remove();
    };

    // Save tool configuration
    ns.saveToolConfig = function(toolName) {
        const tool = ns.toolsData.find(t => t.name === toolName);
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
                                ns.toggleConfigPanel(toolName, false);
                                ns.loadToolsView();
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
    };

    // Toggle plugin enabled/disabled with race condition prevention
    ns.togglePlugin = function(pluginName, enabled) {
        const stateKey = `plugin_${pluginName}`;

        // Prevent duplicate toggle
        if (ns.state.toggleInProgress[stateKey]) {
            return;
        }

        // Mark as in progress
        ns.state.toggleInProgress[stateKey] = true;
        ns.state.autoRefreshEnabled = false;

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
                    ns.loadStats();
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
                delete ns.state.toggleInProgress[stateKey];
                ns.state.autoRefreshEnabled = true;

                // Re-enable checkbox and remove in-progress styling
                checkbox.prop('disabled', false);
                checkbox.closest('.fac-plugin-item').removeClass('toggle-in-progress');
            }
        });
    };

    // Toggle individual tool enabled/disabled
    ns.toggleTool = function(toolName, enabled) {
        const stateKey = `tool_${toolName}`;

        // Prevent duplicate toggle
        if (ns.state.toggleInProgress[stateKey]) {
            return;
        }

        // Mark as in progress
        ns.state.toggleInProgress[stateKey] = true;
        ns.state.autoRefreshEnabled = false;

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
                    const tool = ns.toolsData.find(t => t.name === toolName);
                    if (tool) {
                        tool.tool_enabled = enabled;
                        tool.effectively_enabled = tool.plugin_enabled && enabled;
                    }
                    ns.loadStats();
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
                delete ns.state.toggleInProgress[stateKey];
                ns.state.autoRefreshEnabled = true;

                // Re-enable checkbox and remove in-progress styling
                checkbox.prop('disabled', false);
                checkbox.closest('.fac-tool-item-detailed').removeClass('toggle-in-progress');
            }
        });
    };

    // Load recent activity
    ns.loadRecentActivity = function() {
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
                                    ${activities.slice(0, 5).map(a => {
                                        const ok = a.status === 'Success';
                                        const icon = ok ? 'fa-check-circle' : 'fa-times-circle';
                                        return `
                                        <tr>
                                            <td>${frappe.utils.escape_html(a.action)}</td>
                                            <td>${frappe.utils.escape_html(a.tool_name || '-')}</td>
                                            <td>${frappe.utils.escape_html(a.user)}</td>
                                            <td>
                                                <span class="indicator-pill ${ok ? 'green' : 'red'}">
                                                    <i class="fa ${icon}" aria-hidden="true"></i>
                                                    ${frappe.utils.escape_html(a.status)}
                                                </span>
                                            </td>
                                            <td style="color: var(--text-muted);">
                                                ${frappe.datetime.str_to_user(a.timestamp)}
                                            </td>
                                        </tr>
                                    `;}).join('')}
                                </tbody>
                            </table>
                        `;
                        $('#recent-activity').html(tableHtml);
                    } else {
                        $('#recent-activity').html(`
                            <div class="fac-empty-state fac-empty-state--compact">
                                <i class="fa fa-history" aria-hidden="true"></i>
                                <div class="fac-empty-title">No activity yet</div>
                                <div class="fac-empty-subtitle">Tool calls will appear here.</div>
                            </div>
                        `);
                    }
                }
            },
            error: function() {
                $('#recent-activity').html('<div style="padding: 20px; text-align: center; color: var(--red-500);">Failed to load activity</div>');
            }
        });
    };

    // Bulk toggle by category function
    // Count tools that match the current bulk filter (category + plugin)
    ns.countBulkScope = function(category, plugin) {
        if (!ns.toolsData) return 0;
        return ns.toolsData.filter(t => {
            if (category && t.category !== category) return false;
            if (plugin && t.plugin_name !== plugin) return false;
            return true;
        }).length;
    };

    // Update the "Will affect N tools" hint and toggle button disabled state.
    // Scope reads from the unified filter bar (category + plugin).
    ns.updateBulkScopeCount = function() {
        const category = $('#category-filter').val();
        const plugin = $('#plugin-filter').val();
        const n = ns.countBulkScope(category, plugin);
        const $hint = $('#bulk-scope-count');
        if (n === 0) {
            $hint.text('No tools match');
        } else {
            $hint.text(`${n} tool${n === 1 ? '' : 's'} match`);
        }
        $('#bulk-enable-btn, #bulk-disable-btn').prop('disabled', n === 0);
    };

    ns.bulkToggleByCategory = function(category, plugin, enabled) {
        const actionText = enabled ? 'enable' : 'disable';
        const n = ns.countBulkScope(category, plugin);

        const doBulk = function() {
            ns._performBulkToggle(category, plugin, enabled);
        };

        if (!enabled && n > 0) {
            frappe.confirm(
                `Disable ${n} tool${n === 1 ? '' : 's'}? Users will no longer be able to invoke ${n === 1 ? 'it' : 'them'} via MCP.`,
                doBulk
            );
        } else {
            doBulk();
        }
    };

    ns._performBulkToggle = function(category, plugin, enabled) {
        const actionText = enabled ? 'enable' : 'disable';

        // Disable buttons during operation
        $('#bulk-enable-btn, #bulk-disable-btn').prop('disabled', true);
        const btn = enabled ? $('#bulk-enable-btn') : $('#bulk-disable-btn');
        const originalHtml = btn.html();
        btn.html(`<i class="fa fa-spinner fa-spin" aria-hidden="true"></i> ${enabled ? 'Enabling' : 'Disabling'}...`);

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
                    ns.loadToolsView();
                    ns.loadStats();
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
                // Re-enable buttons (will be re-evaluated by updateBulkScopeCount)
                $('#bulk-enable-btn, #bulk-disable-btn').prop('disabled', false);
                if (typeof ns.updateBulkScopeCount === 'function') {
                    ns.updateBulkScopeCount();
                }
                btn.html(originalHtml);
            }
        });
    };
})();
