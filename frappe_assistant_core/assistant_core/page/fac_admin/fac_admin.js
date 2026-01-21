/*
 * Frappe Assistant Core - FAC Admin Page
 * Copyright (C) 2025 Paul Clinton
 * AGPL-3.0 License
 *
 * This is the entry point for the FAC Admin page.
 * The actual implementation is split into modules located in:
 * - public/js/fac_admin/state.js - State management
 * - public/js/fac_admin/api.js - API wrapper
 * - public/js/fac_admin/plugins_view.js - Plugins view
 * - public/js/fac_admin/tools_view.js - Tools view
 * - public/js/fac_admin/resources_view.js - Resources view
 * - public/js/fac_admin/main.js - Main orchestrator
 *
 * CSS styles are in:
 * - public/css/fac_admin.css
 */

frappe.pages['fac-admin'].on_page_load = function(wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'FAC Admin',
        single_column: true
    });

    // Initialize and start the admin page
    const admin = new frappe.fac_admin.Main(page);
    admin.init();
};
