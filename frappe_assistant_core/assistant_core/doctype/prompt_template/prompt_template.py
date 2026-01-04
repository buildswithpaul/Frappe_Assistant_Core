# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Prompt Template DocType controller.
Handles validation, versioning, and lifecycle management for prompt templates.
"""

import re
from typing import Any, Dict, List, Optional

import frappe
from frappe import _
from frappe.model.document import Document
from jinja2 import BaseLoader, Environment, TemplateSyntaxError


class PromptTemplate(Document):
    def validate(self):
        """Validate prompt template before save."""
        self.validate_prompt_id()
        self.validate_template_syntax()
        self.validate_arguments_match_template()
        self.validate_visibility_settings()

    def validate_prompt_id(self):
        """Ensure prompt_id is URL-safe and unique."""
        if not self.prompt_id:
            frappe.throw(_("Prompt ID is required"))

        # Only allow lowercase alphanumeric, underscore, hyphen
        if not re.match(r"^[a-z0-9_-]+$", self.prompt_id):
            frappe.throw(
                _("Prompt ID must contain only lowercase letters, numbers, "
                  "underscores, and hyphens")
            )

        # Check uniqueness (excluding self on update)
        existing = frappe.db.get_value(
            "Prompt Template",
            {"prompt_id": self.prompt_id, "name": ["!=", self.name or ""]},
            "name"
        )
        if existing:
            frappe.throw(_("Prompt ID '{0}' already exists").format(self.prompt_id))

    def validate_template_syntax(self):
        """Validate template content syntax."""
        if not self.template_content:
            frappe.throw(_("Template content is required"))

        if self.rendering_engine == "Jinja2":
            try:
                env = Environment(loader=BaseLoader())
                env.from_string(self.template_content)
            except TemplateSyntaxError as e:
                frappe.throw(_("Invalid Jinja2 syntax: {0}").format(str(e)))

        elif self.rendering_engine == "Format String":
            try:
                # Find all placeholders and test with dummy values
                placeholders = re.findall(r"\{(\w+)\}", self.template_content)
                test_args = {p: "test" for p in placeholders}
                self.template_content.format(**test_args)
            except (KeyError, ValueError) as e:
                frappe.throw(_("Invalid format string: {0}").format(str(e)))

    def validate_arguments_match_template(self):
        """Ensure all template placeholders have argument definitions."""
        if not self.arguments:
            return

        defined_args = {arg.argument_name for arg in self.arguments}

        # Extract placeholders from template
        if self.rendering_engine == "Jinja2":
            # Match {{ variable }} and {{ variable | filter }}
            placeholders = set(
                re.findall(r"\{\{\s*(\w+)(?:\s*\|[^}]*)?\s*\}\}", self.template_content)
            )
        else:
            placeholders = set(re.findall(r"\{(\w+)\}", self.template_content))

        # Warn about undefined placeholders
        undefined = placeholders - defined_args
        if undefined:
            frappe.msgprint(
                _("Warning: Template uses undefined arguments: {0}").format(
                    ", ".join(undefined)
                ),
                indicator="orange"
            )

        # Warn about unused argument definitions
        unused = defined_args - placeholders
        if unused:
            frappe.msgprint(
                _("Warning: Defined arguments not used in template: {0}").format(
                    ", ".join(unused)
                ),
                indicator="yellow"
            )

    def validate_visibility_settings(self):
        """Validate visibility and sharing configuration."""
        if self.visibility == "Shared" and not self.shared_with_roles:
            frappe.throw(
                _("Please specify roles to share with when visibility is 'Shared'")
            )

    def before_save(self):
        """Handle version increment on significant changes."""
        if not self.is_new():
            old_doc = self.get_doc_before_save()
            if old_doc and old_doc.template_content != self.template_content:
                self.version_number = (self.version_number or 1) + 1
                frappe.msgprint(
                    _("Template content changed. Version incremented to {0}").format(
                        self.version_number
                    ),
                    indicator="blue"
                )

    def on_update(self):
        """Clear caches after update."""
        self.clear_prompt_cache()

    def on_trash(self):
        """Prevent deletion of system templates."""
        if self.is_system:
            frappe.throw(_("System templates cannot be deleted"))
        self.clear_prompt_cache()

    def clear_prompt_cache(self):
        """Clear prompt-related caches."""
        frappe.cache.hdel("prompt_templates", frappe.local.site)

    @frappe.whitelist()
    def create_version(self, notes: str = None) -> str:
        """
        Create a new version (copy) of this template.

        Args:
            notes: Optional notes describing this version

        Returns:
            Name of the new version document
        """
        new_doc = frappe.copy_doc(self)
        new_version = (self.version_number or 1) + 1
        new_doc.prompt_id = f"{self.prompt_id}_v{new_version}"
        new_doc.title = f"{self.title} (v{new_version})"
        new_doc.parent_version = self.name
        new_doc.version_number = 1
        new_doc.status = "Draft"
        new_doc.version_notes = notes or f"Derived from {self.prompt_id}"
        new_doc.is_system = 0
        new_doc.use_count = 0
        new_doc.last_used = None
        new_doc.insert()

        frappe.msgprint(
            _("Created new version: {0}").format(new_doc.name),
            indicator="green"
        )

        return new_doc.name

    @frappe.whitelist()
    def duplicate_as_private(self) -> str:
        """
        Duplicate this template as a private copy for the current user.
        Useful for customizing shared/public templates.

        Returns:
            Name of the new document
        """
        user_prefix = frappe.session.user.split("@")[0].replace(".", "_")
        new_doc = frappe.copy_doc(self)
        new_doc.prompt_id = f"{self.prompt_id}_copy_{user_prefix}"
        new_doc.title = f"{self.title} (My Copy)"
        new_doc.parent_version = self.name
        new_doc.version_number = 1
        new_doc.status = "Draft"
        new_doc.visibility = "Private"
        new_doc.owner_user = frappe.session.user
        new_doc.is_system = 0
        new_doc.version_notes = f"Personal copy of {self.prompt_id}"
        new_doc.shared_with_roles = []
        new_doc.use_count = 0
        new_doc.last_used = None
        new_doc.insert()

        return new_doc.name


@frappe.whitelist()
def preview_template(
    template_content: str,
    rendering_engine: str,
    arguments: dict
) -> str:
    """
    Preview a template with test arguments.

    Args:
        template_content: The template string
        rendering_engine: Jinja2, Format String, or Raw
        arguments: Dict of argument values

    Returns:
        Rendered template string
    """
    try:
        if isinstance(arguments, str):
            arguments = frappe.parse_json(arguments)

        if rendering_engine == "Jinja2":
            env = Environment(loader=BaseLoader())
            template = env.from_string(template_content)
            return template.render(**arguments)
        elif rendering_engine == "Format String":
            return template_content.format(**arguments)
        else:
            return template_content
    except Exception as e:
        return f"Error: {str(e)}"


@frappe.whitelist()
def get_version_history(prompt_name: str) -> List[Dict[str, Any]]:
    """
    Get version history for a prompt template.
    Uses Frappe's built-in Version doctype (track_changes=1).

    Args:
        prompt_name: Name of the Prompt Template document

    Returns:
        List of version history entries
    """
    versions = frappe.get_all(
        "Version",
        filters={
            "ref_doctype": "Prompt Template",
            "docname": prompt_name
        },
        fields=["name", "owner", "creation", "data"],
        order_by="creation desc",
        limit=50
    )

    history = []
    for v in versions:
        try:
            data = frappe.parse_json(v.data) if v.data else {}
            history.append({
                "version_id": v.name,
                "modified_by": v.owner,
                "modified_at": v.creation,
                "changes": data.get("changed", []),
                "added": data.get("added", []),
                "removed": data.get("removed", [])
            })
        except Exception:
            continue

    return history


@frappe.whitelist()
def restore_version(prompt_name: str, version_id: str) -> bool:
    """
    Restore a prompt template to a previous version.

    Args:
        prompt_name: Name of the Prompt Template
        version_id: Version document ID to restore

    Returns:
        True on success
    """
    if not frappe.has_permission("Prompt Template", "write"):
        frappe.throw(_("Insufficient permissions"))

    version_doc = frappe.get_doc("Version", version_id)
    if version_doc.ref_doctype != "Prompt Template" or version_doc.docname != prompt_name:
        frappe.throw(_("Version does not belong to this prompt"))

    prompt_doc = frappe.get_doc("Prompt Template", prompt_name)
    version_data = frappe.parse_json(version_doc.data)

    # Apply reverted changes
    for change in version_data.get("changed", []):
        field, old_value, new_value = change[0], change[1], change[2]
        if hasattr(prompt_doc, field):
            setattr(prompt_doc, field, old_value)

    prompt_doc.version_notes = f"Restored to version from {version_doc.creation}"
    prompt_doc.save()

    frappe.msgprint(_("Template restored successfully"), indicator="green")
    return True


@frappe.whitelist()
def search_prompts(
    query: str = None,
    category: str = None,
    tags: str = None,
    status: str = "Published",
    limit: int = 20
) -> List[Dict[str, Any]]:
    """
    Search prompt templates with filters.

    Args:
        query: Search query for title/description/prompt_id
        category: Filter by category
        tags: Comma-separated list of tags
        status: Filter by status (default: Published)
        limit: Max results to return

    Returns:
        List of matching prompts
    """
    filters = {}

    if status:
        filters["status"] = status
    if category:
        filters["category"] = category

    or_filters = None
    if query:
        or_filters = {
            "title": ["like", f"%{query}%"],
            "description": ["like", f"%{query}%"],
            "prompt_id": ["like", f"%{query}%"]
        }

    prompts = frappe.get_all(
        "Prompt Template",
        filters=filters,
        or_filters=or_filters,
        fields=[
            "name", "prompt_id", "title", "description", "category",
            "status", "use_count", "owner_user", "visibility"
        ],
        limit=limit,
        order_by="use_count desc"
    )

    # Filter by tags if specified
    if tags:
        tag_list = [t.strip() for t in tags.split(",")]
        prompts = [p for p in prompts if _prompt_has_tags(p.name, tag_list)]

    return prompts


def _prompt_has_tags(prompt_name: str, required_tags: List[str]) -> bool:
    """Check if prompt has all required tags."""
    prompt_tags = frappe.get_all(
        "Tag Link",
        filters={"parent": prompt_name, "parenttype": "Prompt Template"},
        pluck="tag"
    )
    return set(required_tags).issubset(set(prompt_tags))


@frappe.whitelist()
def get_popular_prompts(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get most frequently used prompts.

    Args:
        limit: Max results to return

    Returns:
        List of popular prompts sorted by use_count
    """
    return frappe.get_all(
        "Prompt Template",
        filters={"status": "Published"},
        fields=["prompt_id", "title", "description", "use_count", "category"],
        order_by="use_count desc",
        limit=limit
    )


@frappe.whitelist()
def get_prompts_by_category(category: str) -> List[Dict[str, Any]]:
    """
    Get all prompts in a category (including subcategories).

    Args:
        category: Category name

    Returns:
        List of prompts in the category
    """
    # Get category and all descendants using nested set
    categories = [category]
    try:
        from frappe.utils.nestedset import get_descendants_of
        descendants = get_descendants_of("Prompt Category", category)
        categories.extend(descendants)
    except Exception:
        pass

    return frappe.get_all(
        "Prompt Template",
        filters={
            "category": ["in", categories],
            "status": "Published"
        },
        fields=["prompt_id", "title", "description", "category"]
    )
