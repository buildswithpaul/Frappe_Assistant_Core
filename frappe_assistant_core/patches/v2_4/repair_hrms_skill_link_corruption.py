# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Repair for GitHub issue #153.

The removed patch v2_4.rename_skill_to_fac_skill (shipped in v2.4.0) called
frappe.rename_doc("DocType", "Skill", "FAC Skill") on sites where HRMS's own
"Skill" DocType existed. That rename:

  1. Rewrote every tabDocField/tabCustom Field/tabProperty Setter row whose
     Link options was "Skill" to "FAC Skill", breaking HRMS doctypes
     (Employee Skill, Skill Assessment, Expected Skill Set, Designation Skill).

  2. Renamed the physical table tabSkill -> tabFAC Skill. HRMS skill records
     got stranded inside tabFAC Skill. A later bench migrate reloaded HRMS's
     Skill doctype fixture which recreated tabSkill empty, leaving the old
     HRMS rows mixed in with FAC's SK-##### rows.

This patch undoes both effects on sites that already ran the broken patch.
It is a no-op on sites that never ran it.
"""

import frappe
from frappe.query_builder.utils import PseudoColumn


def execute():
    _repair_link_references()
    _recover_stranded_hrms_records()
    frappe.clear_cache()


def _repair_link_references():
    """Revert options='FAC Skill' back to 'Skill' on non-FAC parents.

    Scoped to non-Assistant Core DocTypes because FAC does not ship any
    Link field pointing at its own FAC Skill DocType, so every row we see
    with options='FAC Skill' on a non-FAC parent is corruption from the
    removed rename patch.
    """

    fac_doctypes = frappe.get_all("DocType", filters={"module": "Assistant Core"}, pluck="name")

    DocField = frappe.qb.DocType("DocField")
    update_df = (
        frappe.qb.update(DocField)
        .set(DocField.options, "Skill")
        .where((DocField.options == "FAC Skill") & (DocField.fieldtype == "Link"))
    )
    if fac_doctypes:
        update_df = update_df.where(DocField.parent.notin(fac_doctypes))
    update_df.run()

    CustomField = frappe.qb.DocType("Custom Field")
    update_cf = (
        frappe.qb.update(CustomField)
        .set(CustomField.options, "Skill")
        .where((CustomField.options == "FAC Skill") & (CustomField.fieldtype == "Link"))
    )
    if fac_doctypes:
        update_cf = update_cf.where(CustomField.dt.notin(fac_doctypes))
    update_cf.run()

    PropertySetter = frappe.qb.DocType("Property Setter")
    update_ps = (
        frappe.qb.update(PropertySetter)
        .set(PropertySetter.value, "Skill")
        .where(
            (PropertySetter.property == "options")
            & (PropertySetter.value == "FAC Skill")
            & (PropertySetter.field_name.notnull())
        )
    )
    if fac_doctypes:
        update_ps = update_ps.where(PropertySetter.doc_type.notin(fac_doctypes))
    update_ps.run()


def _recover_stranded_hrms_records():
    """Move HRMS skill rows out of tabFAC Skill back into tabSkill.

    FAC's autoname is format:SK-{#####}, so any tabFAC Skill row whose name
    does not match ^SK-[0-9]+$ is a stranded HRMS record from step 2 of the
    corruption. Pull the HRMS-relevant columns, INSERT into tabSkill via
    frappe.db.bulk_insert, and delete the stranded rows from tabFAC Skill.
    """

    if not frappe.db.exists("DocType", "Skill"):
        # Site has no HRMS Skill doctype at all; nothing to recover into.
        return

    FACSkill = frappe.qb.DocType("FAC Skill")
    not_fac_autoname = PseudoColumn("name NOT REGEXP '^SK-[0-9]+$'")

    stranded = (
        frappe.qb.from_(FACSkill)
        .select(
            FACSkill.name,
            FACSkill.skill_name,
            FACSkill.description,
            FACSkill.creation,
            FACSkill.modified,
            FACSkill.modified_by,
            FACSkill.owner,
            FACSkill.docstatus,
            FACSkill.idx,
        )
        .where(not_fac_autoname)
        .run(as_dict=True)
    )

    if not stranded:
        return

    # Make sure tabSkill has the HRMS schema we're about to INSERT into.
    frappe.reload_doc("hr", "doctype", "skill")

    Skill = frappe.qb.DocType("Skill")
    existing = set(frappe.qb.from_(Skill).select(Skill.name).run(pluck="name"))

    to_insert = [row for row in stranded if row["name"] not in existing]

    for row in to_insert:
        frappe.qb.into(Skill).columns(
            Skill.name,
            Skill.skill_name,
            Skill.description,
            Skill.creation,
            Skill.modified,
            Skill.modified_by,
            Skill.owner,
            Skill.docstatus,
            Skill.idx,
        ).insert(
            row["name"],
            row["skill_name"],
            row["description"],
            row["creation"],
            row["modified"],
            row["modified_by"],
            row["owner"],
            row["docstatus"],
            row["idx"],
        ).run()

    frappe.qb.from_(FACSkill).delete().where(not_fac_autoname).run()

    if to_insert:
        frappe.logger().info(
            "FAC issue #153 repair: recovered %s HRMS Skill records from "
            "tabFAC Skill, deleted %s stranded rows.",
            len(to_insert),
            len(stranded),
        )
