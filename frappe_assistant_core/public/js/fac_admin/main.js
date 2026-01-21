/*
 * Frappe Assistant Core - FAC Admin Main Orchestrator
 * Copyright (C) 2025 Paul Clinton
 * AGPL-3.0 License
 */

frappe.provide('frappe.fac_admin');

/**
 * Main orchestrator for FAC Admin page.
 * Coordinates between views and handles common functionality.
 */
frappe.fac_admin.Main = class {
    constructor(page) {
        this.page = page;
        this.pluginsView = null;
        this.toolsView = null;
        this.resourcesView = null;
        this.autoRefreshInterval = null;
    }

    /**
     * Initialize the admin page
     */
    init() {
        this.renderLayout();
        this.initViews();
        this.bindEvents();
        this.loadInitialData();
        this.startAutoRefresh();
    }

    /**
     * Render the main page layout
     */
    renderLayout() {
        const html = `
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
                    <div class="fac-stat-card" style="border-left-color: var(--purple-500);">
                        <h3>Resources</h3>
                        <div id="resource-stats">
                            <div class="fac-stat-value">-</div>
                            <div class="fac-stat-label">Loading...</div>
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
                        <div class="fac-view-tab" data-view="resources">
                            <i class="fa fa-book"></i> Resources
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
        `;

        this.page.main.html(html);
    }

    /**
     * Initialize view modules
     */
    initViews() {
        const callbacks = {
            onStatsChange: () => this.loadStats()
        };

        this.pluginsView = new frappe.fac_admin.PluginsView('#tool-registry', callbacks);
        this.toolsView = new frappe.fac_admin.ToolsView('#tool-registry', callbacks);
        this.resourcesView = new frappe.fac_admin.ResourcesView('#tool-registry', callbacks);
    }

    /**
     * Bind event handlers
     */
    bindEvents() {
        const self = this;

        // Server toggle
        $('#toggle-server').on('click', () => this.toggleServer());

        // Open settings
        $('#open-settings').on('click', () => {
            frappe.set_route('Form', 'Assistant Core Settings');
        });

        // Refresh button
        $('#refresh-tools').on('click', () => this.loadCurrentView());

        // View mode tabs
        $('.fac-view-tab').on('click', function() {
            const viewMode = $(this).data('view');
            self.switchView(viewMode);
        });

        // Filter handlers
        $('#tool-search').on('input', frappe.utils.debounce(function() {
            if (frappe.fac_admin.state.viewMode === 'tools') {
                self.toolsView.render();
            }
        }, 300));

        $('#category-filter, #plugin-filter').on('change', function() {
            if (frappe.fac_admin.state.viewMode === 'tools') {
                self.toolsView.render();
            }
        });

        // Bulk action handlers
        $('#bulk-enable-btn').on('click', function() {
            const category = $('#bulk-category-select').val();
            const plugin = $('#bulk-plugin-select').val();
            self.toolsView.bulkToggle(category, plugin, true);
        });

        $('#bulk-disable-btn').on('click', function() {
            const category = $('#bulk-category-select').val();
            const plugin = $('#bulk-plugin-select').val();
            self.toolsView.bulkToggle(category, plugin, false);
        });
    }

    /**
     * Load initial data
     */
    loadInitialData() {
        this.loadServerStatus();
        this.loadStats();
        this.loadCurrentView();
        this.loadRecentActivity();
    }

    /**
     * Switch between views
     * @param {string} viewMode - 'plugins', 'tools', or 'resources'
     */
    switchView(viewMode) {
        const state = frappe.fac_admin.state;
        if (viewMode === state.viewMode) return;

        // Update active state
        $('.fac-view-tab').removeClass('active');
        $(`.fac-view-tab[data-view="${viewMode}"]`).addClass('active');

        // Update state
        state.setViewMode(viewMode);

        // Show/hide filter bars and bulk actions
        if (viewMode === 'tools') {
            $('#tools-filter-bar').show();
            $('#tools-bulk-actions').show();
        } else {
            $('#tools-filter-bar').hide();
            $('#tools-bulk-actions').hide();
        }

        // Load the view
        this.loadCurrentView();
    }

    /**
     * Load the current view based on state
     */
    loadCurrentView() {
        const viewMode = frappe.fac_admin.state.viewMode;

        switch (viewMode) {
            case 'plugins':
                this.pluginsView.load();
                break;
            case 'tools':
                this.toolsView.load();
                break;
            case 'resources':
                this.resourcesView.load();
                break;
        }
    }

    /**
     * Load server status
     */
    loadServerStatus() {
        frappe.fac_admin.API.getServerSettings().then(response => {
            if (response.message) {
                const settings = response.message;
                const isEnabled = settings.server_enabled;

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

                // Update MCP Endpoint URL
                let endpointUrl = settings.mcp_endpoint_url;
                if (!endpointUrl || endpointUrl === '') {
                    endpointUrl = window.location.origin + '/api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp';
                }
                $('#fac-mcp-endpoint').text(endpointUrl);
            }
        }).catch(error => {
            console.error('Failed to load server status:', error);
            $('#fac-mcp-endpoint').text('Error loading endpoint');
        });
    }

    /**
     * Toggle server enabled/disabled
     */
    toggleServer() {
        frappe.fac_admin.API.getServerSettings().then(response => {
            if (response.message) {
                const currentState = response.message.server_enabled;
                const newState = currentState ? 0 : 1;

                return frappe.fac_admin.API.updateServerSettings({ server_enabled: newState });
            }
        }).then(result => {
            if (result && result.message) {
                const newState = result.message.server_enabled;
                frappe.show_alert({
                    message: newState ? 'FAC Server Enabled' : 'FAC Server Disabled',
                    indicator: newState ? 'green' : 'orange'
                });

                setTimeout(() => this.loadServerStatus(), 300);
            }
        });
    }

    /**
     * Load statistics
     */
    loadStats() {
        // Plugin stats
        frappe.fac_admin.API.getPluginStats().then(response => {
            if (response.message) {
                const stats = response.message;
                $('#plugin-stats').html(`
                    <div class="fac-stat-value">${stats.enabled_count || 0}</div>
                    <div class="fac-stat-label">${stats.enabled_count} enabled / ${stats.total_count} total</div>
                `);
            }
        });

        // Tool stats
        frappe.fac_admin.API.getToolStats().then(response => {
            if (response.message) {
                const stats = response.message;
                $('#tool-stats').html(`
                    <div class="fac-stat-value">${stats.total_tools || 0}</div>
                    <div class="fac-stat-label">Registered tools</div>
                `);
            }
        });

        // Activity stats
        frappe.fac_admin.API.getUsageStatistics().then(response => {
            if (response.message && response.message.success) {
                const stats = response.message.data;
                $('#activity-stats').html(`
                    <div class="fac-stat-value">${stats.audit_logs?.today || 0}</div>
                    <div class="fac-stat-label">Tool executions today</div>
                `);
            }
        });

        // Resource stats
        frappe.fac_admin.API.getResourceStats().then(response => {
            if (response.message && response.message.success) {
                const stats = response.message;
                const totalResources = (stats.tool_docs_count || 0) + (stats.wiki_pages_count || 0);
                $('#resource-stats').html(`
                    <div class="fac-stat-value">${totalResources}</div>
                    <div class="fac-stat-label">${stats.tool_docs_count || 0} tool docs, ${stats.wiki_pages_count || 0} wiki pages</div>
                `);
            }
        });
    }

    /**
     * Load recent activity
     */
    loadRecentActivity() {
        frappe.fac_admin.API.getUsageStatistics().then(response => {
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
                    $('#recent-activity').html(
                        '<div style="padding: 20px; text-align: center; color: var(--text-muted);">No recent activity</div>'
                    );
                }
            }
        }).catch(() => {
            $('#recent-activity').html(
                '<div style="padding: 20px; text-align: center; color: var(--red-500);">Failed to load activity</div>'
            );
        });
    }

    /**
     * Start auto-refresh interval
     */
    startAutoRefresh() {
        this.autoRefreshInterval = setInterval(() => {
            const state = frappe.fac_admin.state;
            if (!state.canAutoRefresh()) {
                return;
            }

            this.loadServerStatus();
            this.loadStats();
            this.loadRecentActivity();
        }, 30000);
    }

    /**
     * Stop auto-refresh interval
     */
    stopAutoRefresh() {
        if (this.autoRefreshInterval) {
            clearInterval(this.autoRefreshInterval);
            this.autoRefreshInterval = null;
        }
    }
};
