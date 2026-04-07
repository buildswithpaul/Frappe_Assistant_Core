# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# AGPL-3.0-or-later — see <https://www.gnu.org/licenses/>.

import frappe


@frappe.whitelist()
def get_prompt_templates_list() -> dict:
    """
    List all Prompt Templates for the admin dashboard.
    """
    frappe.only_for(["System Manager", "Assistant Admin"])
    try:
        templates = frappe.get_all(
            "Prompt Template",
            fields=[
                "name",
                "title",
                "prompt_id",
                "status",
                "category",
                "use_count",
                "last_used",
                "is_system",
                "visibility",
            ],
            order_by="title asc",
        )
        published = sum(1 for t in templates if t.get("status") == "Published")
        return {
            "success": True,
            "templates": templates,
            "total": len(templates),
            "published": published,
        }
    except Exception as e:
        frappe.log_error(f"Failed to get prompt templates list: {str(e)}")
        return {"success": False, "error": str(e), "templates": [], "total": 0, "published": 0}


@frappe.whitelist(methods=["POST"])
def toggle_prompt_template_status(name: str, publish: bool):
    """
    Toggle a Prompt Template between Draft and Published.
    """
    frappe.only_for(["System Manager", "Assistant Admin"])
    try:
        if not frappe.db.exists("Prompt Template", name):
            return {"success": False, "message": f"Prompt Template '{name}' not found"}

        publish = frappe.utils.cint(publish)
        new_status = "Published" if publish else "Draft"

        doc = frappe.get_doc("Prompt Template", name)
        doc.status = new_status
        doc.save(ignore_permissions=True)
        frappe.db.commit()

        frappe.cache.hdel("prompt_templates", frappe.local.site)

        return {
            "success": True,
            "message": f"Prompt Template '{doc.title}' set to {new_status}",
            "new_status": new_status,
        }
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(f"Failed to toggle prompt template '{name}': {str(e)}")
        return {"success": False, "message": f"Error: {str(e)}"}


@frappe.whitelist()
def preview_prompt_template(name: str):
    """
    Fetch a Prompt Template's content and arguments for inline preview in the admin UI.
    """
    frappe.only_for(["System Manager", "Assistant Admin"])
    try:
        if not frappe.db.exists("Prompt Template", name):
            return {"success": False, "message": f"Prompt Template '{name}' not found"}

        doc = frappe.get_doc("Prompt Template", name)
        arguments = [
            {
                "argument_name": arg.argument_name,
                "argument_type": arg.argument_type,
                "is_required": arg.is_required,
                "default_value": arg.default_value,
                "description": arg.description,
            }
            for arg in (doc.arguments or [])
        ]
        return {
            "success": True,
            "name": doc.name,
            "title": doc.title,
            "template_content": doc.template_content,
            "rendering_engine": doc.rendering_engine,
            "arguments": arguments,
        }
    except Exception as e:
        frappe.log_error(f"Failed to preview prompt template '{name}': {str(e)}")
        return {"success": False, "message": f"Error: {str(e)}"}
