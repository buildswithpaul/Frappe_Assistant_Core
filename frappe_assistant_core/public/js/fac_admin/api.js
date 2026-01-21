/*
 * Frappe Assistant Core - FAC Admin API Module
 * Copyright (C) 2025 Paul Clinton
 * AGPL-3.0 License
 */

frappe.provide('frappe.fac_admin');

/**
 * API wrapper for FAC Admin operations.
 * Provides a clean interface for all backend calls.
 */
frappe.fac_admin.API = {
    /**
     * Get server settings
     */
    getServerSettings: function() {
        return frappe.call({
            method: "frappe.client.get",
            args: {
                doctype: "Assistant Core Settings",
                name: "Assistant Core Settings"
            }
        });
    },

    /**
     * Update server settings
     * @param {Object} settings - Settings to update
     */
    updateServerSettings: function(settings) {
        return frappe.call({
            method: "frappe_assistant_core.api.admin_api.update_server_settings",
            args: settings
        });
    },

    /**
     * Get plugin statistics
     */
    getPluginStats: function() {
        return frappe.call({
            method: "frappe_assistant_core.api.admin_api.get_plugin_stats"
        });
    },

    /**
     * Get tool statistics
     */
    getToolStats: function() {
        return frappe.call({
            method: "frappe_assistant_core.api.admin_api.get_tool_stats"
        });
    },

    /**
     * Get usage statistics
     */
    getUsageStatistics: function() {
        return frappe.call({
            method: "frappe_assistant_core.api.admin_api.get_usage_statistics"
        });
    },

    /**
     * Get tool configurations
     */
    getToolConfigurations: function() {
        return frappe.call({
            method: "frappe_assistant_core.api.admin_api.get_tool_configurations"
        });
    },

    /**
     * Toggle a plugin
     * @param {string} pluginName - Plugin identifier
     * @param {boolean} enable - Enable or disable
     */
    togglePlugin: function(pluginName, enable) {
        return frappe.call({
            method: "frappe_assistant_core.api.admin_api.toggle_plugin",
            args: {
                plugin_name: pluginName,
                enable: enable
            }
        });
    },

    /**
     * Toggle a tool
     * @param {string} toolName - Tool identifier
     * @param {boolean} enabled - Enable or disable
     */
    toggleTool: function(toolName, enabled) {
        return frappe.call({
            method: "frappe_assistant_core.api.admin_api.toggle_tool",
            args: {
                tool_name: toolName,
                enabled: enabled ? 1 : 0
            }
        });
    },

    /**
     * Bulk toggle tools by category
     * @param {string|null} category - Category filter
     * @param {string|null} plugin - Plugin filter
     * @param {boolean} enabled - Enable or disable
     */
    bulkToggleToolsByCategory: function(category, plugin, enabled) {
        return frappe.call({
            method: "frappe_assistant_core.api.admin_api.bulk_toggle_tools_by_category",
            args: {
                category: category || null,
                plugin_name: plugin || null,
                enabled: enabled
            }
        });
    },

    /**
     * Update tool category
     * @param {string} toolName - Tool identifier
     * @param {string} category - New category
     * @param {boolean} override - Mark as manual override
     */
    updateToolCategory: function(toolName, category, override) {
        return frappe.call({
            method: "frappe_assistant_core.api.admin_api.update_tool_category",
            args: {
                tool_name: toolName,
                category: category,
                override: override
            }
        });
    },

    /**
     * Update tool role access
     * @param {string} toolName - Tool identifier
     * @param {string} mode - Role access mode
     * @param {Array} roles - List of role access entries
     */
    updateToolRoleAccess: function(toolName, mode, roles) {
        return frappe.call({
            method: "frappe_assistant_core.api.admin_api.update_tool_role_access",
            args: {
                tool_name: toolName,
                role_access_mode: mode,
                roles: roles
            }
        });
    },

    /**
     * Get available roles
     */
    getAvailableRoles: function() {
        return frappe.call({
            method: "frappe_assistant_core.api.admin_api.get_available_roles"
        });
    },

    // =========================================
    // Resources API
    // =========================================

    /**
     * Get resource statistics
     */
    getResourceStats: function() {
        return frappe.call({
            method: "frappe_assistant_core.api.admin_api.get_resource_stats"
        });
    },

    /**
     * Get list of tool documentation files
     */
    getToolDocsList: function() {
        return frappe.call({
            method: "frappe_assistant_core.api.admin_api.get_tool_docs_list"
        });
    },

    /**
     * Toggle the resources feature on/off
     * @param {boolean} enabled - Enable or disable the feature
     */
    toggleResourcesFeature: function(enabled) {
        return frappe.call({
            method: "frappe_assistant_core.api.admin_api.toggle_resources_feature",
            args: {
                enabled: enabled ? 1 : 0
            }
        });
    }
};
