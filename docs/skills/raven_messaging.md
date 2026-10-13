# Posting in Raven

## When this applies

The user asks you to send, post or share something in Raven ("post this summary in #support",
"tell Priya the invoice is approved"). Only post when asked, and only as the user — never as a bot.

## 1. Find where to post

- **A channel**: `list_documents` on `Raven Channel` with `channel_name` like the name the user gave, `is_direct_message = 0`, `is_archived = 0`. Confirm the user is a member: `Raven Channel Member` with `channel_id = <channel>` and `user_id = <the user>`. If several match, ask which. Raven requires membership to post even in **Open** channels: if the user is not a member, ask them to join the channel in Raven first.
- **A direct message with a person**: a `Raven Channel` with `is_direct_message = 1` whose `dm_user_1` and `dm_user_2` are the two users' IDs — the greater ID (string order) is `dm_user_1`. If none exists, tell the user to open a DM with that person in Raven first. **Never create channels or DMs.**

## 2. Post

`create_document` with doctype `Raven Message`:

```json
{"channel_id": "<channel name>", "message_type": "Text", "text": "<p>…</p>"}
```

- `text` is HTML: wrap paragraphs in `<p>`, use `<strong>`, `<ul><li>` for lists.
- **Mention** someone: `<span data-type="userMention" data-id="<user id>">@Full Name</span>` — Raven notifies them.
- **Attach a record** (shows as a linked card): add `"link_doctype": "HD Ticket", "link_document": "<name>"`.
- **Reply to a message**: add `"is_reply": 1, "linked_message": "<Raven Message name>"`.

The user sees an approval card with the message before it is sent — write it ready to send, not as a draft for them to edit.

## Rules

- Post exactly what the user asked for; quote numbers and names from the records you read.
- Never post internal notes (Helpdesk `HD Ticket Comment`) to a channel customers can see.
- If `create_document` is refused, the user is not a member of that channel or not a Raven user — say so.
