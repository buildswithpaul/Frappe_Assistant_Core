// fac_admin_settings.js
// Settings tab: the group sub-nav, deep links and the unsaved-changes guard.
// One group's form lives in fac_admin_settings_form.js.

(function() {
    const ns = frappe.fac_admin;
    const TABS = ['tools', 'prompts', 'skills', 'settings'];
    const settings = ns.settings = { groups: [], activeKey: null, form: null, loading: false, loaded: false };

    function urlParams() {
        return new URLSearchParams(window.location.search);
    }

    ns.initialTab = function() {
        const tab = urlParams().get('tab');
        return TABS.includes(tab) ? tab : 'tools';
    };

    // A settings load can finish after the user has left the page; never stamp another route.
    // Settings without a group yet keeps the URL's group, which the pending load still reads.
    ns.writeSettingsUrl = function(tab, group) {
        if (frappe.get_route()[0] !== 'fac-admin') return;
        const url = new URL(window.location.href);
        url.searchParams.set('tab', tab);
        if (tab !== 'settings') url.searchParams.delete('group');
        else if (group) url.searchParams.set('group', group);
        window.history.replaceState(window.history.state, '', url.pathname + url.search + url.hash);
    };

    ns.settingsIsDirty = function() {
        return Boolean(settings.form && settings.form.isDirty());
    };

    ns.confirmLeaveSettings = function(proceed) {
        if (!ns.settingsIsDirty()) return proceed();
        frappe.confirm(__('You have unsaved changes in this group. Discard them?'), function() {
            settings.form.reset();
            proceed();
        });
    };

    ns.loadSettingsView = function() {
        if (settings.loaded || settings.loading) return;
        settings.loading = true;
        $('#settings-nav').empty();
        $('#settings-pane').html(ns.skeletonCards(2));
        frappe.call({
            method: 'frappe_assistant_core.api.admin_api.get_settings_groups',
            type: 'GET',
            callback: function(r) {
                settings.loading = false;
                settings.loaded = true;
                settings.groups = (r.message && r.message.groups) || [];
                if (!settings.groups.length) {
                    $('#settings-pane').html(
                        `<p class="fac-settings-note">${__('Only a System Manager can view these settings.')}</p>`
                    );
                    return;
                }
                renderNav();
                const wanted = urlParams().get('group');
                const first = settings.groups.find(g => g.key === wanted) || settings.groups[0];
                if (first) showGroup(first.key);
            },
            error: function() {
                settings.loading = false;
                renderLoadError();
            }
        });
    };

    function renderNav() {
        const esc = frappe.utils.escape_html;
        $('#settings-nav').html(settings.groups.map(g => `
            <button type="button" class="fac-settings-nav-item" role="tab" data-group="${esc(g.key)}"
                    aria-selected="false" aria-controls="settings-pane" tabindex="-1">
                <i class="fa ${esc(g.icon || 'fa-cog')}" aria-hidden="true"></i>
                <span>${esc(__(g.label))}</span>
            </button>`).join(''));
    }

    function renderLoadError() {
        $('#settings-pane').html(`
            <div class="fac-settings-error">
                ${__('Could not load the settings.')}
                <button type="button" class="btn btn-xs btn-default" id="settings-retry">${__('Retry')}</button>
            </div>`);
    }

    function showGroup(key) {
        const group = settings.groups.find(g => g.key === key);
        if (!group) return;
        if (settings.form) settings.form.dispose();
        settings.activeKey = key;
        $('.fac-settings-nav-item')
            .removeClass('active')
            .attr({ 'aria-selected': 'false', tabindex: '-1' });
        $(`.fac-settings-nav-item[data-group="${key}"]`)
            .addClass('active')
            .attr({ 'aria-selected': 'true', tabindex: '0' });
        ns.writeSettingsUrl('settings', key);
        if (typeof ns.SettingsForm !== 'function') return;
        settings.form = new ns.SettingsForm({ group: group, $body: $('#settings-pane') });
        settings.form.load();
    }

    ns.selectSettingsGroup = function(key) {
        if (key === settings.activeKey) return;
        ns.confirmLeaveSettings(function() { showGroup(key); });
    };

    ns.bindSettingsEvents = function() {
        $('#settings-nav').on('click', '.fac-settings-nav-item', function() {
            ns.selectSettingsGroup($(this).data('group'));
        });

        // Vertical tab list: Up/Down/Home/End move focus and select (WAI-ARIA tabs pattern).
        $('#settings-nav').on('keydown', '.fac-settings-nav-item', function(e) {
            const keys = ['ArrowUp', 'ArrowDown', 'Home', 'End'];
            if (!keys.includes(e.key)) return;
            e.preventDefault();
            const $items = $('.fac-settings-nav-item');
            const count = $items.length;
            const index = $items.index(this);
            let next = index;
            if (e.key === 'ArrowDown') next = (index + 1) % count;
            else if (e.key === 'ArrowUp') next = (index - 1 + count) % count;
            else if (e.key === 'Home') next = 0;
            else if (e.key === 'End') next = count - 1;
            const $next = $items.eq(next);
            $next.trigger('focus');
            ns.selectSettingsGroup($next.data('group'));
        });

        $('#settings-pane').on('click', '#settings-retry', function() {
            settings.loaded = false;
            ns.loadSettingsView();
        });

        window.addEventListener('beforeunload', function(e) {
            if (!ns.settingsIsDirty()) return;
            e.preventDefault();
            e.returnValue = '';
        });
    };
})();
