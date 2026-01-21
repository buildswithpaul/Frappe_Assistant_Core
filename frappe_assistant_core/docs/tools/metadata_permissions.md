# metadata_permissions

Get permission information for a DocType and user.

## When to Use

- Checking user access before operations
- Understanding permission structure
- Debugging permission issues
- Verifying roles have correct access

## Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| doctype | string | Yes | - | DocType name |
| user | string | No | Current user | User to check permissions for |

## Examples

### Check Current User Permissions

```json
{
  "doctype": "Sales Invoice"
}
```

### Check Specific User

```json
{
  "doctype": "Sales Invoice",
  "user": "user@company.com"
}
```

## Response Format

```json
{
  "success": true,
  "doctype": "Sales Invoice",
  "user": "user@company.com",
  "permissions": {
    "read": true,
    "write": true,
    "create": true,
    "delete": false,
    "submit": true,
    "cancel": true,
    "amend": false
  },
  "user_roles": [
    "System Manager",
    "Sales User",
    "Sales Manager"
  ],
  "permission_rules": [
    {
      "role": "Sales User",
      "read": 1,
      "write": 1,
      "create": 1,
      "delete": 0,
      "submit": 0,
      "cancel": 0,
      "amend": 0,
      "permlevel": 0
    },
    {
      "role": "Sales Manager",
      "read": 1,
      "write": 1,
      "create": 1,
      "delete": 1,
      "submit": 1,
      "cancel": 1,
      "amend": 1,
      "permlevel": 0
    }
  ]
}
```

## Permission Types

| Permission | Description |
|------------|-------------|
| read | View documents |
| write | Modify documents |
| create | Create new documents |
| delete | Delete documents |
| submit | Submit draft documents |
| cancel | Cancel submitted documents |
| amend | Amend cancelled documents |

## Understanding Results

### User Effective Permissions

The `permissions` object shows what the user can actually do, combining all their roles.

### User Roles

The `user_roles` array shows all roles assigned to the user.

### Permission Rules

The `permission_rules` array shows the raw permission settings for each role in the DocType.

## Use Cases

### Before Creating Document

Check create permission:

```json
{"doctype": "Customer"}
```

If `create: true`, proceed with `create_document`.

### Before Submitting

Check submit permission:

```json
{"doctype": "Sales Invoice"}
```

If `submit: true`, can use `submit_document`.

### Debugging Access Issues

```json
{
  "doctype": "Salary Slip",
  "user": "hr@company.com"
}
```

Review which roles grant access and which are missing.

## Permission Levels

Permission rules may include `permlevel` for field-level permissions:
- Level 0: Basic access
- Higher levels: Restricted fields

## Common Scenarios

| Scenario | Required Permission |
|----------|---------------------|
| Viewing records | read |
| Editing records | write |
| Creating new | create |
| Removing records | delete |
| Finalizing transactions | submit |
| Reversing transactions | cancel |
| Amending transactions | amend |

## Related Tools

- **get_doctype_info** - Get DocType structure
- **metadata_workflow** - Get workflow info
- **run_workflow** - Execute workflow actions
