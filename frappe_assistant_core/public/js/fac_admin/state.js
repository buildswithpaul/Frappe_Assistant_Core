/*
 * Frappe Assistant Core - FAC Admin State Management
 * Copyright (C) 2025 Paul Clinton
 * AGPL-3.0 License
 */

frappe.provide('frappe.fac_admin');

/**
 * Centralized state management for FAC Admin page.
 * Prevents race conditions and maintains consistent UI state.
 */
frappe.fac_admin.State = class {
    constructor() {
        this.toggleInProgress = {};      // Track which items are being toggled
        this.refreshInProgress = false;  // Track if auto-refresh is happening
        this.autoRefreshEnabled = true;  // Can be disabled during operations
        this.viewMode = 'plugins';       // 'plugins', 'tools', or 'resources'
        this.availableRoles = [];        // Cached list of available roles
        this.openConfigPanels = {};      // Track which tool config panels are open
        this.toolsData = [];             // Cached tools data for filtering
        this.wikiSpaces = [];            // Cached wiki spaces
    }

    /**
     * Check if any toggle operation is in progress
     */
    isToggling() {
        return Object.keys(this.toggleInProgress).length > 0;
    }

    /**
     * Mark a toggle operation as started
     * @param {string} key - Unique key for the toggle (e.g., 'plugin_core', 'tool_list_documents')
     */
    startToggle(key) {
        this.toggleInProgress[key] = true;
        this.autoRefreshEnabled = false;
    }

    /**
     * Mark a toggle operation as completed
     * @param {string} key - Unique key for the toggle
     */
    endToggle(key) {
        delete this.toggleInProgress[key];
        if (!this.isToggling()) {
            this.autoRefreshEnabled = true;
        }
    }

    /**
     * Check if auto-refresh should run
     */
    canAutoRefresh() {
        return this.autoRefreshEnabled && !this.isToggling();
    }

    /**
     * Set the current view mode
     * @param {string} mode - 'plugins', 'tools', or 'resources'
     */
    setViewMode(mode) {
        this.viewMode = mode;
    }

    /**
     * Toggle a config panel's open state
     * @param {string} toolName - Name of the tool
     * @param {boolean} [forceState] - Optional forced state
     * @returns {boolean} New state of the panel
     */
    toggleConfigPanel(toolName, forceState) {
        if (forceState === false || (forceState === undefined && this.openConfigPanels[toolName])) {
            delete this.openConfigPanels[toolName];
            return false;
        } else {
            this.openConfigPanels[toolName] = true;
            return true;
        }
    }

    /**
     * Check if a config panel is open
     * @param {string} toolName - Name of the tool
     */
    isConfigPanelOpen(toolName) {
        return !!this.openConfigPanels[toolName];
    }
};

// Create global state instance
frappe.fac_admin.state = new frappe.fac_admin.State();
