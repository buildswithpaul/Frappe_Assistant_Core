# How to Use test_as_user

## Overview

The `test_as_user` tool asks Frappe's permission rules what another user may do. It saves nothing, runs no code and does not switch user. It needs the System Manager role, and any enabled user can be checked.

Use it after changing roles, User Permissions or sharing for a build, to confirm the right people can reach the new DocType or record and the wrong people cannot.

Each check comes back as one of:

- `allowed`: the user has the permission.
- `refused`: the user does not. `reason` is a fixed sentence, not Frappe's own text.
- `error`: the check could not be answered, for example an unknown DocType or a record that does not exist. The other checks still run.

The result never contains a field value of the record.

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user` | string | Yes | Email of an enabled user. A missing or disabled user checks nothing and returns `success: false` |
| `checks` | array | Yes | 1 to 20 checks |

Each check:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `ptype` | string | Yes | `read`, `write`, `create`, `delete`, `submit`, `cancel`, `amend`, `print`, `email`, `share`, `export` or `report` |
| `doctype` | string | Yes | DocType to check |
| `name` | string | No | A record name. Omit it for the DocType-level answer |
| `parent_doctype` | string | No | The parent DocType, when `doctype` is a child table |

## Reading roles_that_allow

`roles_that_allow` lists the roles that grant that permission on the DocType at permission level 0. It is filled on every check, allowed or refused; on a refusal it shows which role to grant. For a child table, the roles come from the parent DocType. Roles marked "if owner" in the role table are listed here but only allow the record's owner. A record-level refusal can still happen to a user who holds one of these roles, because User Permissions, sharing and the owner rule apply on top.

## FAC Pages

A `read` check on a named FAC Page answers whether the user can open that page, as the page itself decides it: a published page opens for a holder of one of its roles, an unpublished page or one with no roles for a System Manager only. `roles_that_allow` then lists the page's roles (while it is published) and System Manager, not the DocType's roles. Other permission types on FAC Page are answered from the DocType, which is System Manager only.

## Limits

- Administrator is always allowed.
- A permission hook that reads `frappe.session.user` instead of its `user` argument answers for the caller, not the user you named.

## Best Practices

1. **Check both levels** — a DocType-level `allowed` does not mean a given record is allowed; add a check with `name` for a record the user should not see.
2. **Check the refusal too** — include a user who should be refused, not only the one who should pass.
3. **Re-run after each change** to roles, User Permissions or sharing, instead of trusting the earlier answer.
