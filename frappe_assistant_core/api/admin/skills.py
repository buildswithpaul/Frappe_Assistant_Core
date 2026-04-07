# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# AGPL-3.0-or-later — see <https://www.gnu.org/licenses/>.

import frappe


@frappe.whitelist()
def get_skills_list() -> dict:
    """
    List all FAC Skills for the admin dashboard.
    """
    frappe.only_for(["System Manager", "Assistant Admin"])
    try:
        skills = frappe.get_all(
            "FAC Skill",
            fields=[
                "name",
                "title",
                "skill_id",
                "status",
                "skill_type",
                "linked_tool",
                "use_count",
                "last_used",
                "is_system",
                "visibility",
            ],
            order_by="title asc",
        )
        published = sum(1 for s in skills if s.get("status") == "Published")
        return {
            "success": True,
            "skills": skills,
            "total": len(skills),
            "published": published,
        }
    except Exception as e:
        frappe.log_error(f"Failed to get skills list: {str(e)}")
        return {"success": False, "error": str(e), "skills": [], "total": 0, "published": 0}


@frappe.whitelist(methods=["POST"])
def toggle_skill_status(name: str, publish: bool):
    """
    Toggle a FAC Skill between Draft and Published.
    """
    frappe.only_for(["System Manager", "Assistant Admin"])
    try:
        if not frappe.db.exists("FAC Skill", name):
            return {"success": False, "message": f"FAC Skill '{name}' not found"}

        publish = frappe.utils.cint(publish)
        new_status = "Published" if publish else "Draft"

        doc = frappe.get_doc("FAC Skill", name)
        doc.status = new_status
        doc.save(ignore_permissions=True)
        frappe.db.commit()

        frappe.cache.hdel("skills", frappe.local.site)

        return {
            "success": True,
            "message": f"FAC Skill '{doc.title}' set to {new_status}",
            "new_status": new_status,
        }
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(f"Failed to toggle skill '{name}': {str(e)}")
        return {"success": False, "message": f"Error: {str(e)}"}
