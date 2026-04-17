// fac_admin_skills.js
// Skills management for FAC Admin page.
// Extracted from fac_admin.js lines 2198-2377

(function() {
    const ns = frappe.fac_admin;

    // Load skills view
    ns.loadSkillsView = function() {
        $('#skills-list').html(ns.skeletonCards(3));
        frappe.call({
            method: "frappe_assistant_core.api.admin_api.get_skills_list",
            callback: function(response) {
                if (response.message && response.message.success) {
                    ns.state.skillsData = response.message.skills;
                    ns.renderSkillsList();
                } else {
                    $('#skills-list').html(
                        '<div style="padding:20px;text-align:center;color:var(--red-500);">Failed to load skills</div>'
                    );
                }
            },
            error: function() {
                $('#skills-list').html(
                    '<div style="padding:20px;text-align:center;color:var(--red-500);">Error loading skills</div>'
                );
            }
        });
    };

    // Render skills list
    ns.renderSkillsList = function() {
        const searchTerm = $('#skill-search').val().toLowerCase();
        const typeFilter = $('#skill-type-filter').val();
        const statusFilter = $('#skill-status-filter').val();

        const filtered = ns.state.skillsData.filter(s => {
            if (searchTerm && !s.title.toLowerCase().includes(searchTerm) &&
                !(s.skill_id || '').toLowerCase().includes(searchTerm)) return false;
            if (typeFilter && s.skill_type !== typeFilter) return false;
            if (statusFilter && s.status !== statusFilter) return false;
            return true;
        });

        if (filtered.length === 0) {
            const zeroData = !ns.state.skillsData || ns.state.skillsData.length === 0;
            if (zeroData) {
                $('#skills-list').html(`
                    <div class="fac-empty-state">
                        <i class="fa fa-graduation-cap" aria-hidden="true"></i>
                        <div class="fac-empty-title">No skills yet</div>
                        <div class="fac-empty-subtitle">Skills are reusable workflows or tool-usage patterns exposed to MCP clients.</div>
                        <a href="/app/fac-skill/new?status=Draft" class="btn btn-xs btn-primary">Create skill</a>
                    </div>
                `);
            } else {
                $('#skills-list').html(`
                    <div class="fac-empty-state">
                        <i class="fa fa-search" aria-hidden="true"></i>
                        <div class="fac-empty-title">No skills match the current filters</div>
                        <button type="button" class="btn btn-xs btn-default fac-clear-skill-filters">Clear filters</button>
                    </div>
                `);
                $('.fac-clear-skill-filters').on('click', function() {
                    $('#skill-search').val('');
                    $('#skill-type-filter').val('');
                    $('#skill-status-filter').val('');
                    ns.renderSkillsList();
                });
            }
            return;
        }

        const html = filtered.map(s => {
            const isToggling = ns.state.toggleInProgress[`skill_${s.name}`];
            const isPublished = s.status === 'Published';
            const statusClass = (s.status || 'draft').toLowerCase();
            const lastUsed = s.last_used ? frappe.datetime.str_to_user(s.last_used) : 'Never';

            return `
            <div class="fac-item-card ${isToggling ? 'toggle-in-progress' : ''}" data-name="${s.name}">
                <div class="fac-item-header">
                    <div class="fac-item-title">
                        ${frappe.utils.escape_html(s.title)}
                        <span class="fac-status-badge ${statusClass}">${s.status}</span>
                    </div>
                    <div class="fac-item-actions">
                        <button class="fac-tool-settings-btn fac-skill-content-btn"
                                data-name="${s.name}"
                                aria-label="View content of skill ${frappe.utils.escape_html(s.title)}"
                                title="View skill content">
                            <i class="fa fa-book" aria-hidden="true"></i>
                        </button>
                        <a href="/app/fac-skill/${encodeURIComponent(s.name)}" target="_blank"
                           class="fac-tool-settings-btn"
                           aria-label="Open ${frappe.utils.escape_html(s.title)} in DocType editor"
                           title="Open in DocType">
                            <i class="fa fa-external-link" aria-hidden="true"></i>
                        </a>
                        <label class="switch" style="margin:0;" title="${isPublished ? 'Click to unpublish' : 'Click to publish'}">
                            <input type="checkbox" class="fac-skill-toggle"
                                   data-name="${s.name}"
                                   aria-label="Publish skill ${frappe.utils.escape_html(s.title)}"
                                   ${isPublished ? 'checked' : ''}
                                   ${isToggling ? 'disabled' : ''}>
                            <span class="slider round"></span>
                        </label>
                    </div>
                </div>
                <div class="fac-item-subtitle">${frappe.utils.escape_html(s.skill_id || s.name)}</div>
                <div class="fac-item-meta">
                    <span class="fac-meta-chip">${frappe.utils.escape_html(s.skill_type || '')}</span>
                    ${s.linked_tool ? `<span class="fac-meta-chip"><i class="fa fa-wrench"></i> ${frappe.utils.escape_html(s.linked_tool)}</span>` : ''}
                    <span class="fac-meta-chip"><i class="fa fa-eye"></i> ${s.visibility || 'Private'}</span>
                    ${s.is_system ? '<span class="fac-meta-chip system-chip">System</span>' : ''}
                    <span class="fac-meta-chip">Used ${s.use_count || 0}x</span>
                    <span class="fac-meta-chip"><i class="fa fa-clock-o"></i> ${lastUsed}</span>
                </div>
                <div class="fac-expand-panel" id="skill-content-${s.name}"></div>
            </div>`;
        }).join('');

        $('#skills-list').html(html);

        $('.fac-skill-toggle').off('change').on('change', function() {
            ns.toggleSkillStatus($(this).data('name'), $(this).is(':checked'));
        });

        $('.fac-skill-content-btn').off('click').on('click', function() {
            ns.showSkillContent($(this).data('name'));
        });
    };

    // Toggle skill status (publish/unpublish)
    ns.toggleSkillStatus = function(name, publish) {
        const stateKey = `skill_${name}`;
        if (ns.state.toggleInProgress[stateKey]) return;

        ns.state.toggleInProgress[stateKey] = true;
        ns.state.autoRefreshEnabled = false;

        const checkbox = $(`.fac-skill-toggle[data-name="${name}"]`);
        const originalState = !publish;
        checkbox.prop('disabled', true);
        checkbox.closest('.fac-item-card').addClass('toggle-in-progress');

        frappe.call({
            method: "frappe_assistant_core.api.admin_api.toggle_skill_status",
            args: { name: name, publish: publish ? 1 : 0 },
            callback: function(response) {
                delete ns.state.toggleInProgress[stateKey];
                ns.state.autoRefreshEnabled = true;

                if (response.message && response.message.success) {
                    frappe.show_alert({ message: response.message.message, indicator: publish ? 'green' : 'orange' });
                    const skill = ns.state.skillsData.find(s => s.name === name);
                    if (skill) skill.status = response.message.new_status;
                    ns.renderSkillsList();
                    ns.loadStats();
                } else {
                    checkbox.prop('checked', originalState);
                    checkbox.prop('disabled', false);
                    checkbox.closest('.fac-item-card').removeClass('toggle-in-progress');
                    frappe.show_alert({ message: response.message?.message || 'Unknown error', indicator: 'red' });
                }
            },
            error: function() {
                delete ns.state.toggleInProgress[stateKey];
                ns.state.autoRefreshEnabled = true;
                checkbox.prop('checked', originalState);
                checkbox.prop('disabled', false);
                checkbox.closest('.fac-item-card').removeClass('toggle-in-progress');
                frappe.show_alert({ message: 'Error toggling skill status', indicator: 'red' });
            }
        });
    };

    // Show skill content panel
    ns.showSkillContent = function(name) {
        const panel = $(`#skill-content-${name}`);
        const btn = $(`.fac-skill-content-btn[data-name="${name}"]`);

        if (panel.hasClass('open')) {
            panel.removeClass('open');
            btn.removeClass('active');
            return;
        }

        panel.addClass('open').html(
            '<div style="color:var(--text-muted);font-size:12px;"><i class="fa fa-spinner fa-spin"></i> Loading content...</div>'
        );
        btn.addClass('active');

        frappe.call({
            method: "frappe.client.get_value",
            args: { doctype: "FAC Skill", filters: { name: name }, fieldname: "content" },
            callback: function(response) {
                if (response.message && response.message.content) {
                    const rendered = ns.renderMarkdown(response.message.content);
                    panel.html(`<div style="font-size:13px;">${rendered}</div>`);
                } else {
                    panel.html('<div style="color:var(--text-muted);">No content available</div>');
                }
            },
            error: function() {
                panel.html('<div style="color:var(--red-500);">Error loading content</div>');
            }
        });
    };
})();
