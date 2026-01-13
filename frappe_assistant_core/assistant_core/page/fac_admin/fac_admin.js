frappe.pages['fac-admin'].on_page_load = function(wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'FAC Admin',
        single_column: true
    });

    // State management to prevent race conditions
    const state = {
        toggleInProgress: {},  // Track which items are being toggled
        refreshInProgress: false,  // Track if auto-refresh is happening
        autoRefreshEnabled: true,  // Can be disabled during operations
        viewMode: 'plugins',  // 'plugins' or 'tools'
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
                grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
                gap: 20px;
                margin-bottom: 20px;
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
                background: var(--bg-light-gray);
                border-radius: 12px;
                font-size: 11px;
                color: var(--text-muted);
                font-weight: 500;
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
                background-color: var(--gray-300);
                transition: .3s;
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
            }
            input:checked + .slider {
                background-color: var(--primary);
            }
            input:checked + .slider:before {
                transform: translateX(20px);
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
                padding: 8px 12px;
                background: var(--bg-color);
                border-radius: var(--border-radius);
                border: 1px solid var(--border-color);
            }
            .fac-endpoint-url {
                font-family: var(--font-stack-monospace);
                font-size: 12px;
                word-break: break-all;
                color: var(--primary);
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
            .fac-category-badge.dangerous, .fac-category-badge.red {
                background: var(--red-100);
                color: var(--red-600);
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
            </div>

            <!-- Tools Registry -->
            <div class="fac-card">
                <div class="fac-card-header">
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

                <!-- Filter Bar (shown in tools view) -->
                <div class="fac-filter-bar" id="tools-filter-bar" style="display: none;">
                    <input type="text" class="fac-filter-input" id="tool-search"
                           placeholder="Search tools...">
                    <select class="fac-filter-select" id="category-filter">
                        <option value="">All Categories</option>
                        <option value="read_only">Read Only</option>
                        <option value="write">Write</option>
                        <option value="read_write">Read & Write</option>
                        <option value="dangerous">Dangerous</option>
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

                    // Populate plugin filter
                    const plugins = [...new Set(toolsData.map(t => t.plugin_name))];
                    const pluginFilter = $('#plugin-filter');
                    pluginFilter.find('option:gt(0)').remove();
                    plugins.forEach(p => {
                        pluginFilter.append(`<option value="${p}">${p.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}</option>`);
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
            // Category filter
            if (categoryFilter && tool.category !== categoryFilter) {
                return false;
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

            return `
                <div class="fac-tool-item-detailed ${isToggling ? 'toggle-in-progress' : ''} ${pluginDisabled ? 'fac-disabled-overlay' : ''}">
                    <div class="fac-tool-header">
                        <div class="fac-tool-title">
                            ${tool.display_name}
                            <span class="fac-category-badge ${tool.category}">${tool.category_label}</span>
                        </div>
                        <label class="switch" style="margin: 0;">
                            <input type="checkbox" class="fac-tool-toggle"
                                   data-tool="${tool.name}"
                                   ${tool.tool_enabled ? 'checked' : ''}
                                   ${isToggling || pluginDisabled ? 'disabled' : ''}>
                            <span class="slider round"></span>
                        </label>
                    </div>
                    <div class="fac-tool-description">${tool.description || 'No description available'}</div>
                    <div class="fac-tool-footer">
                        <span class="fac-tool-badge">${tool.plugin_display_name}</span>
                        ${pluginDisabled ? '<span class="fac-plugin-disabled-notice"><i class="fa fa-exclamation-circle"></i> Plugin disabled</span>' : ''}
                        ${tool.role_access_mode !== 'Allow All' ? '<span class="fac-tool-badge" style="background: var(--blue-100); color: var(--blue-600);"><i class="fa fa-lock"></i> Role restricted</span>' : ''}
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

        // Show/hide filter bar
        if (viewMode === 'tools') {
            $('#tools-filter-bar').show();
        } else {
            $('#tools-filter-bar').hide();
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
