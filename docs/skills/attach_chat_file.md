# How to Use attach_chat_file

## Overview

The `attach_chat_file` tool attaches a file the user uploaded in this chat to a Frappe document,
for example a receipt to a Purchase Invoice or a signed contract to a Customer. The document
gets its own copy of the attachment; the chat keeps the original.

Every file the user has attached in the conversation is listed in your context under
"Files attached in this conversation", each with a **File ID**. Pass that File ID.

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file_id` | string | **Yes** | File ID of the chat upload, from the conversation's file list |
| `doctype` | string | **Yes** | DocType to attach to, e.g. `Purchase Invoice` |
| `name` | string | **Yes** | Document name, e.g. `PINV-26-00050` |

## Response Format

```json
{
  "success": true,
  "message": "Attached receipt.jpg to Purchase Invoice PINV-26-00050.",
  "file_id": "8c1f2a9e41",
  "file_url": "/private/files/receipt.jpg",
  "attached_to": {"doctype": "Purchase Invoice", "name": "PINV-26-00050"},
  "already_attached": false
}
```

## Best Practices

1. **Use the File ID from the conversation's file list.** Never search the File list for a file
   the user sent in chat: names repeat, and another record's file looks just like it.
2. **Never use `update_document` or `create_document` on File to attach a file.** Re-pointing an
   existing File's `attached_to_*` fields moves it off the record it belonged to.
3. **If the user has attached several files, ask which one** unless the request makes it clear.
4. **Confirm the target document** when its name came from your own search rather than the user.

## Edge Cases

- **File not from this chat**: a File ID that the user did not send with a chat message is
  refused.
- **No write permission**: the user needs write access to the target document, the same check
  Desk applies when attaching a file.
- **Already attached**: attaching the same file to the same document again succeeds with
  `already_attached: true` and creates no duplicate.
- **Submitted documents**: attachments can be added to submitted documents when the user can
  write to them.
