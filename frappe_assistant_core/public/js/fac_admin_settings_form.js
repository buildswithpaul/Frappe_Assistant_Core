// fac_admin_settings_form.js
// One settings group: renders its DocType fields with frappe.ui.FieldGroup and saves them
// through savedocs, the DocType form's own save, so validate(), the save hooks and
// permissions all run as they do on the form.

(function() {
    const ns = frappe.fac_admin;
    const NO_VALUE = ['Section Break', 'Tab Break', 'Column Break', 'HTML'];

    function isBlank(value) {
        return value === null || value === undefined || value === '';
    }

    function sameValue(a, b) {
        return (isBlank(a) && isBlank(b)) || String(a) === String(b);
    }

    function pick(doc, fieldnames) {
        const out = {};
        fieldnames.forEach(function(fieldname) {
            out[fieldname] = isBlank(doc[fieldname]) ? null : doc[fieldname];
        });
        return out;
    }

    ns.SettingsForm = class SettingsForm {
        constructor({ group, $body }) {
            this.group = group;
            this.$body = $body;
            this.doctype = group.doctype;
            this.fieldGroup = null;
            this.fieldnames = [];
            this.baseline = {};
            this.disposed = false;
        }

        get canWrite() {
            return !this.group.read_only && frappe.model.can_write(this.doctype);
        }

        load() {
            this.$body.html(ns.skeletonCards(2));
            frappe.model.with_doctype(this.doctype).then(() => {
                if (this.disposed) return;
                // getdoc's response carries the doc in `docs`, which frappe.call syncs into locals.
                frappe.call({
                    method: 'frappe.desk.form.load.getdoc',
                    type: 'GET',
                    args: { doctype: this.doctype, name: this.doctype },
                    callback: () => this.render(),
                    error: () => this.renderLoadError(),
                });
            });
        }

        docfields() {
            const meta = frappe.get_meta(this.doctype);
            return this.group.fields
                .map((fieldname) => meta.fields.find((df) => df.fieldname === fieldname))
                .filter(Boolean)
                .map((source) => {
                    const df = Object.assign({}, source);
                    if (df.fieldtype === 'Tab Break') df.fieldtype = 'Section Break';
                    if (!this.canWrite) df.read_only = 1;
                    df.onchange = () => this.refreshActions();
                    return df;
                });
        }

        render() {
            if (this.disposed) return;
            const doc = frappe.get_doc(this.doctype, this.doctype);
            const fields = this.docfields();
            this.fieldnames = fields.filter((df) => !NO_VALUE.includes(df.fieldtype)).map((df) => df.fieldname);
            this.baseline = pick(doc, this.fieldnames);

            this.$body.html('<div class="fac-settings-form"></div><div class="fac-settings-actions"></div>');
            this.fieldGroup = new frappe.ui.FieldGroup({
                fields: fields,
                body: this.$body.find('.fac-settings-form')[0],
            });
            this.fieldGroup.make();
            // Int and Float controls fire onchange only on blur; keep Save in step while typing.
            this.$body.find('.fac-settings-form').on('input', frappe.utils.debounce(() => this.refreshActions(), 150));
            this.renderActions();
            this.fieldGroup.set_values(this.baseline).then(() => this.refreshActions());
        }

        renderActions() {
            const $actions = this.$body.find('.fac-settings-actions');
            if (!this.canWrite) {
                const note = this.group.read_only
                    ? __('This information is read-only.')
                    : __('Only a System Manager can change these settings.');
                $actions.html(`<p class="fac-settings-note">${note}</p>`);
                this.$save = null;
                return;
            }
            $actions.html(`<button type="button" class="btn btn-sm btn-primary" disabled>${__('Save')}</button>`);
            this.$save = $actions.find('button');
            this.$save.on('click', () => this.save());
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

        changes() {
            const out = {};
            if (!this.fieldGroup) return out;
            this.fieldnames.forEach((fieldname) => {
                const value = this.fieldGroup.get_value(fieldname);
                if (!sameValue(value, this.baseline[fieldname])) out[fieldname] = value;
            });
            return out;
        }

        isDirty() {
            return Object.keys(this.changes()).length > 0;
        }

        refreshActions() {
            if (this.$save) this.$save.prop('disabled', !this.isDirty());
        }

        reset() {
            if (this.fieldGroup) this.fieldGroup.set_values(this.baseline).then(() => this.refreshActions());
        }

        dispose() {
            this.disposed = true;
        }

        save() {
            const changes = this.changes();
            if (!Object.keys(changes).length) return;
            // The loaded doc carries `modified`, so a concurrent edit raises Frappe's
            // "document has been modified" error instead of being overwritten.
            const doc = Object.assign({}, frappe.get_doc(this.doctype, this.doctype), changes);
            this.$save.prop('disabled', true);
            frappe.call({
                method: 'frappe.desk.form.save.savedocs',
                type: 'POST',
                args: { doc: JSON.stringify(doc), action: 'Save' },
                freeze: true,
                callback: () => {
                    if (this.disposed) return;
                    // savedocs returns the saved doc in `docs`; frappe.call has synced it into locals.
                    this.baseline = pick(frappe.get_doc(this.doctype, this.doctype), this.fieldnames);
                    this.fieldGroup.set_values(this.baseline).then(() => this.refreshActions());
                    frappe.show_alert({ message: __('{0} saved', [__(this.group.label)]), indicator: 'green' });
                },
                // Frappe has already shown the server's message; the edits stay so nothing typed is lost.
                error: () => this.refreshActions(),
            });
        }
    };
})();
