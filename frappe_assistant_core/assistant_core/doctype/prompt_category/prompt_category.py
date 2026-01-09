# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Prompt Category DocType controller.
Manages hierarchical categories for prompt template organization.
"""

import re

import frappe
from frappe import _
from frappe.utils.nestedset import NestedSet


class PromptCategory(NestedSet):
    nsm_parent_field = "parent_prompt_category"

    def validate(self):
        """Validate category before save."""
        self.validate_category_id()

    def validate_category_id(self):
        """Ensure category_id is URL-safe."""
        if not self.category_id:
            frappe.throw(_("Category ID is required"))

        # Only allow lowercase alphanumeric with hyphens
        if not re.match(r"^[a-z0-9-]+$", self.category_id):
            frappe.throw(_("Category ID must contain only lowercase letters, numbers, and hyphens"))

    def on_update(self):
        """Clear cache after update."""
        super().on_update()
        self.clear_category_cache()

    def on_trash(self):
        """Check for linked prompts before deletion."""
        super().on_trash()
        self._check_linked_prompts()
        self.clear_category_cache()

    def _check_linked_prompts(self):
        """Prevent deletion if prompts are linked to this category."""
        linked_prompts = frappe.db.count("Prompt Template", {"category": self.name})
        if linked_prompts:
            frappe.throw(
                _(
                    "Cannot delete category with {0} linked prompt template(s). "
                    "Move or delete the prompts first."
                ).format(linked_prompts)
            )

    def clear_category_cache(self):
        """Clear category-related caches."""
        frappe.cache.hdel("prompt_categories", frappe.local.site)


@frappe.whitelist()
def get_category_tree():
    """
    Get all categories as a tree structure for UI display.

    Returns:
        list: Nested list of categories with children
    """
    categories = frappe.get_all(
        "Prompt Category",
        fields=[
            "name",
            "category_id",
            "category_name",
            "parent_prompt_category",
            "icon",
            "color",
            "is_group",
            "lft",
            "rgt",
        ],
        order_by="lft",
    )

    # Build tree structure
    root_categories = []
    category_map = {c.name: {**c, "children": []} for c in categories}

    for cat in categories:
        cat_data = category_map[cat.name]
        if cat.parent_prompt_category and cat.parent_prompt_category in category_map:
            category_map[cat.parent_prompt_category]["children"].append(cat_data)
        else:
            root_categories.append(cat_data)

    return root_categories


@frappe.whitelist()
def get_prompt_count_by_category():
    """
    Get count of prompts per category.

    Returns:
        dict: Category name to prompt count mapping
    """
    counts = frappe.db.sql(
        """
        SELECT category, COUNT(*) as count
        FROM `tabPrompt Template`
        WHERE category IS NOT NULL AND category != ''
        GROUP BY category
    """,
        as_dict=True,
    )

    return {c.category: c.count for c in counts}
