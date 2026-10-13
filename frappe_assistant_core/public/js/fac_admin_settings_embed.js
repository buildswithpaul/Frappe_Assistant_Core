// fac_admin_settings_embed.js
// The Settings tab's "Other Frappe apps" group: one switch per discovered app,
// saved as it is flipped. Same interface as SettingsForm.

(function() {
    const ns = frappe.fac_admin;

    ns.EmbedAppsPanel = class EmbedAppsPanel {
        constructor({ group, $body }) {
            this.group = group;
            this.$body = $body;
            this.disposed = false;
        }

        isDirty() {
            return false;
        }

        reset() {}

        dispose() {
            this.disposed = true;
        }

        load() {
            this.$body.html(ns.skeletonCards(1));
            frappe.call({
                method: 'frappe_assistant_core.chat.api.settings.embed.get_embed_apps',
                type: 'GET',
                callback: (r) => this.render(r.message || []),
                error: () => this.renderLoadError(),
            });
        }

        render(apps) {
            if (this.disposed) return;
            const esc = frappe.utils.escape_html;
            if (!apps.length) {
                this.$body.html(`<p class="fac-settings-note">${__('No other Frappe apps are installed on this site.')}</p>`);
                return;
            }
            this.$body.html(`
                <p class="fac-settings-note">${__('Show the FACO widget inside these apps as well as Desk. Only System Users with FAC access see it.')}</p>
                <div class="fac-embed-apps">
                    ${apps.map((app) => `
                        <label class="fac-embed-app">
                            <input type="checkbox" data-app="${esc(app.app)}" ${app.enabled ? 'checked' : ''}>
                            <span>${esc(__(app.title))}</span>
                            <code>${esc(app.route)}</code>
                        </label>`).join('')}
                </div>`);
            this.$body.find('input[data-app]').on('change', (e) => this.toggle($(e.currentTarget)));
            this.loadRavenBot();
        }

        // FAC Bot in Raven: the bot in Raven's conversations, distinct from the widget on its pages.
        loadRavenBot() {
            frappe.call({
                method: 'frappe_assistant_core.chat.api.settings.raven_bot.get_raven_bot',
                type: 'GET',
                callback: (r) => this.renderRavenBot(r.message || {}),
            });
        }

        renderRavenBot({ available, enabled }) {
            if (this.disposed || !available) return;
            this.$body.append(`
                <div class="fac-embed-apps fac-raven-bot">
                    <label class="fac-embed-app">
                        <input type="checkbox" data-raven-bot ${enabled ? 'checked' : ''}>
                        <span>${__('FAC Bot in Raven')}</span>
                        <code>${__('DMs and @mentions')}</code>
                    </label>
                    <p class="fac-settings-note">${__('Each answer runs as the person asking and uses their FACO credits. Add FAC Bot to a channel to use @mentions there.')}</p>
                </div>`);
            this.$body.find('input[data-raven-bot]').on('change', (e) => this.toggleRavenBot($(e.currentTarget)));
        }

        toggleRavenBot($input) {
            const enabled = $input.prop('checked');
            $input.prop('disabled', true);
            frappe.call({
                method: 'frappe_assistant_core.chat.api.settings.raven_bot.set_raven_bot_enabled',
                type: 'POST',
                args: { enabled: enabled ? 1 : 0 },
                callback: () => {
                    $input.prop('disabled', false);
                    frappe.show_alert({
                        message: enabled ? __('FAC Bot switched on') : __('FAC Bot switched off'),
                        indicator: enabled ? 'green' : 'orange',
                    });
                },
                // Frappe has shown the server's message; put the switch back where the server has it.
                error: () => $input.prop({ disabled: false, checked: !enabled }),
            });
        }

        toggle($input) {
            const app = $input.data('app');
            const enabled = $input.prop('checked');
            $input.prop('disabled', true);
            frappe.call({
                method: 'frappe_assistant_core.chat.api.settings.embed.set_embed_app_enabled',
                type: 'POST',
                args: { app_name: app, enabled: enabled ? 1 : 0 },
                callback: () => {
                    $input.prop('disabled', false);
                    frappe.show_alert({
                        message: enabled ? __('Widget shown in {0}', [app]) : __('Widget hidden in {0}', [app]),
                        indicator: enabled ? 'green' : 'orange',
                    });
                },
                // Frappe has shown the server's message; put the switch back where the server has it.
                error: () => $input.prop({ disabled: false, checked: !enabled }),
            });
        }

        renderLoadError() {
            if (this.disposed) return;
            const label = frappe.utils.escape_html(__(this.group.label));
            this.$body.html(`
                <div class="fac-settings-error">
                    ${__('Could not load {0}.', [label])}
                    <button type="button" class="btn btn-xs btn-default">${__('Retry')}</button>
                </div>`);
            this.$body.find('.fac-settings-error button').on('click', () => this.load());
        }
    };
})();
