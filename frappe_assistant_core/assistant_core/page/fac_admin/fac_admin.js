frappe.pages['fac-admin'].on_page_load = function(wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'FAC Admin',
        single_column: true
    });

    // Initialize shared namespace before loading submodules
    frappe.fac_admin = {
        page: page,
        state: {
            toggleInProgress: {},
            refreshInProgress: false,
            autoRefreshEnabled: true,
            viewMode: 'plugins',
            activeTab: 'tools',
            availableRoles: [],
            openConfigPanels: {},
            promptsData: [],
            skillsData: [],
        },
    };

    const ns = frappe.fac_admin;

    // Load CSS and inject HTML, then load JS submodules
    frappe.require("/assets/frappe_assistant_core/css/fac_admin.css");

    page.main.html(`
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

    // Load JS submodules, then wire event handlers and start data loading
    frappe.require([
        "/assets/frappe_assistant_core/js/fac_admin_utils.js",
        "/assets/frappe_assistant_core/js/fac_admin_tools.js",
        "/assets/frappe_assistant_core/js/fac_admin_prompts.js",
        "/assets/frappe_assistant_core/js/fac_admin_skills.js"
    ]).then(function() {

        // =====================================================================
        // Event handlers
        // =====================================================================

        // Server toggle
        $('#toggle-server').on('click', ns.toggleServer);
        $('#open-settings').on('click', function() {
            frappe.set_route('Form', 'Assistant Core Settings');
        });

        // Tool registry refresh
        $('#refresh-tools').on('click', ns.loadToolRegistry);

        // View mode tab handlers (Plugins / Individual Tools)
        $('.fac-view-tab').on('click', function() {
            const viewMode = $(this).data('view');
            if (viewMode === ns.state.viewMode) return;

            $('.fac-view-tab').removeClass('active');
            $(this).addClass('active');

            ns.state.viewMode = viewMode;

            if (viewMode === 'tools') {
                $('#tools-filter-bar').show();
                $('#tools-bulk-actions').show();
            } else {
                $('#tools-filter-bar').hide();
                $('#tools-bulk-actions').hide();
            }

            ns.loadToolRegistry();
        });

        // Filter handlers (for tools view)
        $('#tool-search').on('input', frappe.utils.debounce(function() {
            if (ns.state.viewMode === 'tools') {
                ns.renderToolsList();
            }
        }, 300));

        $('#category-filter, #plugin-filter').on('change', function() {
            if (ns.state.viewMode === 'tools') {
                ns.renderToolsList();
            }
        });

        // Bulk action button handlers
        $('#bulk-enable-btn').on('click', function() {
            const category = $('#bulk-category-select').val();
            const plugin = $('#bulk-plugin-select').val();
            ns.bulkToggleByCategory(category, plugin, true);
        });

        $('#bulk-disable-btn').on('click', function() {
            const category = $('#bulk-category-select').val();
            const plugin = $('#bulk-plugin-select').val();
            ns.bulkToggleByCategory(category, plugin, false);
        });

        // Top-level tab switching
        ns.switchTab = function(tabName) {
            if (ns.state.activeTab === tabName) return;
            ns.state.activeTab = tabName;

            $('.fac-top-tab').removeClass('active');
            $(`.fac-top-tab[data-tab="${tabName}"]`).addClass('active');

            $('.fac-tab-panel').removeClass('active');
            $(`#tab-panel-${tabName}`).addClass('active');

            if (tabName === 'prompts' && ns.state.promptsData.length === 0) {
                ns.loadPromptTemplatesView();
            } else if (tabName === 'skills' && ns.state.skillsData.length === 0) {
                ns.loadSkillsView();
            }
        };

        $('.fac-top-tab').on('click', function() {
            ns.switchTab($(this).data('tab'));
        });

        // Prompt Templates filter handlers
        $('#prompt-search').on('input', frappe.utils.debounce(function() {
            if (ns.state.activeTab === 'prompts') ns.renderPromptTemplatesList();
        }, 300));

        $('#prompt-status-filter').on('change', function() {
            if (ns.state.activeTab === 'prompts') ns.renderPromptTemplatesList();
        });

        $('#refresh-prompts').on('click', ns.loadPromptTemplatesView);

        // Skills filter handlers
        $('#skill-search').on('input', frappe.utils.debounce(function() {
            if (ns.state.activeTab === 'skills') ns.renderSkillsList();
        }, 300));

        $('#skill-type-filter, #skill-status-filter').on('change', function() {
            if (ns.state.activeTab === 'skills') ns.renderSkillsList();
        });

        $('#refresh-skills').on('click', ns.loadSkillsView);

        // =====================================================================
        // Initial data load
        // =====================================================================
        ns.loadServerStatus();
        ns.loadStats();
        ns.loadToolRegistry();
        ns.loadRecentActivity();

        // Auto-refresh every 30 seconds (respects autoRefreshEnabled flag)
        setInterval(function() {
            if (!ns.state.autoRefreshEnabled || Object.keys(ns.state.toggleInProgress).length > 0) {
                return;
            }

            ns.loadServerStatus();
            ns.loadStats();
            ns.loadRecentActivity();
            // Note: We intentionally don't auto-refresh loadToolRegistry() here
            // to avoid interfering with user toggle interactions
        }, 30000);
    });
};
