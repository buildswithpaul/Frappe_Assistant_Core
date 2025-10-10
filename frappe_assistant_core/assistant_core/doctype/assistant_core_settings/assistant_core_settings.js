// Copyright (c) 2025, Paul Clinton and contributors
// For license information, please see license.txt

frappe.ui.form.on("Assistant Core Settings", {
    refresh(frm) {
        // Load plugin status in HTML field
        frm.call('get_plugin_status').then(response => {
            if (response.message && response.message.success) {
                frm.set_df_property('plugin_status_html', 'options', response.message.html);
                frm.refresh_field('plugin_status_html');
            }
        });

        // Add custom buttons
        frm.add_custom_button(__('Refresh Plugin System'), function() {
            frappe.call({
                method: 'refresh_plugins',
                doc: frm.doc,
                callback: function(response) {
                    if (!response.exc) {
                        frm.reload_doc();
                    }
                }
            });
        }, __('Actions'));
    }
});
