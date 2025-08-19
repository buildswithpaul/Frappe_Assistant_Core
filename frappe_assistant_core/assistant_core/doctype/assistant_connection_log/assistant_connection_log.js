// Copyright (C) 2025 Paul Clinton
// For license information, please see license.txt

frappe.ui.form.on('Assistant Connection Log', {
    refresh: function(frm) {
        // Add custom buttons or logic if needed
        if (frm.doc.status === "Connected") {
            frm.add_custom_button(__('Close Connection'), function() {
                frappe.call({
                    method: 'frappe_assistant_core.assistant_core.doctype.assistant_connection_log.assistant_connection_log.close_connection',
                    args: {
                        name: frm.doc.name
                    },
                    callback: function(r) {
                        frm.reload_doc();
                    }
                });
            });
        }
        
        // Make form read-only as these are system-generated logs
        frm.set_df_property('*', 'read_only', 1);
    }
});