import frappe


def _user_or_admin(user, doctype_table, user_field="user"):
    if not user:
        user = frappe.session.user

    if user in (None, "", "Guest"):
        return "1=0"

    if "System Manager" in frappe.get_roles(user):
        return ""

    escaped_user = frappe.db.escape(user)
    return f"`tab{doctype_table}`.{user_field} = {escaped_user}"


def _doc_owner_or_admin(doc, user):
    if not user:
        user = frappe.session.user
    if "System Manager" in frappe.get_roles(user):
        return True
    return getattr(doc, "user", None) == user


def get_faco_message_permission_query_conditions(user=None):
    return _user_or_admin(user, "FAC Chat Message")


def get_faco_usage_log_permission_query_conditions(user=None):
    return _user_or_admin(user, "FAC Chat Usage Log")


def get_faco_user_preferences_permission_query_conditions(user=None):
    return _user_or_admin(user, "FAC Chat User Preferences")


def has_faco_message_permission(doc, user=None, permission_type=None):
    return _doc_owner_or_admin(doc, user)


def has_faco_usage_log_permission(doc, user=None, permission_type=None):
    return _doc_owner_or_admin(doc, user)


def has_faco_user_preferences_permission(doc, user=None, permission_type=None):
    return _doc_owner_or_admin(doc, user)
