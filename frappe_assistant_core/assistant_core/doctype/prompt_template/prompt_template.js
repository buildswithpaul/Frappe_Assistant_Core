// Frappe Assistant Core - AI Assistant integration for Frappe Framework
// Copyright (C) 2025 Paul Clinton
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU Affero General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.

frappe.ui.form.on('Prompt Template', {
    refresh: function(frm) {
        // Add Preview button
        frm.add_custom_button(__('Preview'), function() {
            frm.trigger('show_preview');
        }, __('Actions'));

        // Add actions for saved documents
        if (!frm.is_new()) {
            // Create Version button (only for non-system templates)
            if (!frm.doc.is_system) {
                frm.add_custom_button(__('Create New Version'), function() {
                    frm.trigger('create_version');
                }, __('Actions'));
            }

            // Duplicate as Private button
            frm.add_custom_button(__('Duplicate as Private'), function() {
                frm.trigger('duplicate_private');
            }, __('Actions'));

            // Version History button
            frm.add_custom_button(__('Version History'), function() {
                frm.trigger('show_version_history');
            }, __('Actions'));
        }

        // Protect system templates
        if (frm.doc.is_system) {
            frm.disable_save();
            frm.set_intro(
                __('This is a system template and cannot be modified. Use "Duplicate as Private" to create your own version.'),
                'blue'
            );
        }

        // Show MCP prompt ID info
        if (frm.doc.prompt_id && frm.doc.status === 'Published') {
            frm.set_intro(
                __('MCP Prompt ID: <code>{0}</code> - Available via prompts/list', [frm.doc.prompt_id]),
                'green'
            );
        }

        // Auto-detect arguments when template content changes
        frm.trigger('check_template_arguments');
    },

    show_preview: function(frm) {
        // Collect test values for arguments
        let args = {};
        (frm.doc.arguments || []).forEach(arg => {
            args[arg.argument_name] = arg.default_value || `[${arg.argument_name}]`;
        });

        // Render preview
        frappe.call({
            method: 'frappe_assistant_core.assistant_core.doctype.prompt_template.prompt_template.preview_template',
            args: {
                template_content: frm.doc.template_content,
                rendering_engine: frm.doc.rendering_engine || 'Jinja2',
                arguments: args
            },
            callback: function(r) {
                if (r.message) {
                    let preview_html = `<pre style="white-space: pre-wrap; background: #f5f5f5; padding: 15px; border-radius: 4px; max-height: 500px; overflow-y: auto;">${frappe.utils.escape_html(r.message)}</pre>`;

                    frappe.msgprint({
                        title: __('Template Preview'),
                        message: preview_html,
                        wide: true
                    });
                }
            }
        });
    },

    show_version_history: function(frm) {
        frappe.call({
            method: 'frappe_assistant_core.assistant_core.doctype.prompt_template.prompt_template.get_version_history',
            args: { prompt_name: frm.doc.name },
            callback: function(r) {
                if (r.message && r.message.length > 0) {
                    let html = '<div class="version-history" style="max-height: 400px; overflow-y: auto;">';

                    r.message.forEach((v, idx) => {
                        let changes_html = '';
                        if (v.changes && v.changes.length > 0) {
                            changes_html = v.changes.map(c =>
                                `<span class="badge badge-light" style="margin: 2px;">${c[0]}</span>`
                            ).join(' ');
                        } else {
                            changes_html = '<span class="text-muted">No field changes recorded</span>';
                        }

                        html += `
                            <div class="version-entry mb-3 p-3" style="border: 1px solid #ddd; border-radius: 4px;">
                                <div class="d-flex justify-content-between align-items-center">
                                    <strong>${frappe.datetime.str_to_user(v.modified_at)}</strong>
                                    <span class="text-muted">${v.modified_by}</span>
                                </div>
                                <div class="mt-2">
                                    <small class="text-muted">Changed fields:</small><br>
                                    ${changes_html}
                                </div>
                                <button class="btn btn-xs btn-default mt-2"
                                        onclick="frappe_assistant_core_restore_version('${frm.doc.name}', '${v.version_id}')">
                                    <i class="fa fa-undo"></i> Restore
                                </button>
                            </div>
                        `;
                    });

                    html += '</div>';

                    frappe.msgprint({
                        title: __('Version History'),
                        message: html,
                        wide: true
                    });
                } else {
                    frappe.msgprint(__('No version history available'));
                }
            }
        });
    },

    create_version: function(frm) {
        frappe.prompt([
            {
                fieldname: 'notes',
                fieldtype: 'Small Text',
                label: __('Version Notes'),
                description: __('Describe what changed in this version')
            }
        ], function(values) {
            frappe.call({
                method: 'create_version',
                doc: frm.doc,
                args: { notes: values.notes },
                callback: function(r) {
                    if (r.message) {
                        frappe.show_alert({
                            message: __('New version created'),
                            indicator: 'green'
                        });
                        frappe.set_route('Form', 'Prompt Template', r.message);
                    }
                }
            });
        }, __('Create New Version'), __('Create'));
    },

    duplicate_private: function(frm) {
        frappe.call({
            method: 'duplicate_as_private',
            doc: frm.doc,
            callback: function(r) {
                if (r.message) {
                    frappe.show_alert({
                        message: __('Private copy created'),
                        indicator: 'green'
                    });
                    frappe.set_route('Form', 'Prompt Template', r.message);
                }
            }
        });
    },

    template_content: function(frm) {
        // Auto-detect arguments from template
        frm.trigger('check_template_arguments');
    },

    rendering_engine: function(frm) {
        // Re-check arguments when engine changes
        frm.trigger('check_template_arguments');
    },

    check_template_arguments: function(frm) {
        if (!frm.doc.template_content) return;

        let pattern;
        if (frm.doc.rendering_engine === 'Jinja2' || !frm.doc.rendering_engine) {
            // Match {{ variable }} and {{ variable | filter }}
            pattern = /\{\{\s*(\w+)(?:\s*\|[^}]*)?\s*\}\}/g;
        } else if (frm.doc.rendering_engine === 'Format String') {
            pattern = /\{(\w+)\}/g;
        } else {
            return; // Raw mode, no placeholders
        }

        let matches = [...frm.doc.template_content.matchAll(pattern)];
        let found_args = [...new Set(matches.map(m => m[1]))];
        let existing_args = (frm.doc.arguments || []).map(a => a.argument_name);
        let new_args = found_args.filter(a => !existing_args.includes(a));
        let unused_args = existing_args.filter(a => !found_args.includes(a));

        // Show alerts for new/unused arguments
        if (new_args.length > 0) {
            frappe.show_alert({
                message: __('Found new placeholders: {0}', [new_args.join(', ')]),
                indicator: 'blue'
            }, 5);
        }

        if (unused_args.length > 0 && !frm.is_new()) {
            frappe.show_alert({
                message: __('Unused arguments: {0}', [unused_args.join(', ')]),
                indicator: 'yellow'
            }, 5);
        }
    },

    prompt_id: function(frm) {
        // Auto-convert to lowercase with underscores
        if (frm.doc.prompt_id) {
            let cleaned = frm.doc.prompt_id
                .toLowerCase()
                .replace(/\s+/g, '_')
                .replace(/[^a-z0-9_-]/g, '');

            if (cleaned !== frm.doc.prompt_id) {
                frm.set_value('prompt_id', cleaned);
                frappe.show_alert({
                    message: __('Prompt ID converted to lowercase format'),
                    indicator: 'blue'
                });
            }
        }
    },

    visibility: function(frm) {
        // Clear shared_with_roles when changing from Shared to other visibility
        if (frm.doc.visibility !== 'Shared' && frm.doc.shared_with_roles && frm.doc.shared_with_roles.length > 0) {
            frappe.confirm(
                __('Changing visibility will clear the shared roles. Continue?'),
                function() {
                    frm.clear_table('shared_with_roles');
                    frm.refresh_field('shared_with_roles');
                },
                function() {
                    frm.set_value('visibility', 'Shared');
                }
            );
        }
    }
});

// Global function for restore version button
window.frappe_assistant_core_restore_version = function(prompt_name, version_id) {
    frappe.confirm(
        __('Are you sure you want to restore this version? Current content will be overwritten.'),
        function() {
            frappe.call({
                method: 'frappe_assistant_core.assistant_core.doctype.prompt_template.prompt_template.restore_version',
                args: {
                    prompt_name: prompt_name,
                    version_id: version_id
                },
                callback: function(r) {
                    if (r.message) {
                        frappe.show_alert({
                            message: __('Version restored successfully'),
                            indicator: 'green'
                        });
                        // Close dialog and reload form
                        frappe.msgprint().hide();
                        cur_frm.reload_doc();
                    }
                }
            });
        }
    );
};

// Child table events
frappe.ui.form.on('Prompt Template Argument', {
    argument_type: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];

        // Clear allowed_values if not select/multiselect
        if (!['select', 'multiselect'].includes(row.argument_type)) {
            frappe.model.set_value(cdt, cdn, 'allowed_values', '');
        }

        // Clear length constraints if not string
        if (row.argument_type !== 'string') {
            frappe.model.set_value(cdt, cdn, 'min_length', null);
            frappe.model.set_value(cdt, cdn, 'max_length', null);
        }
    },

    argument_name: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];

        // Auto-set display label from argument name
        if (row.argument_name && !row.display_label) {
            let label = row.argument_name
                .replace(/_/g, ' ')
                .replace(/\b\w/g, l => l.toUpperCase());
            frappe.model.set_value(cdt, cdn, 'display_label', label);
        }
    }
});
