# How to Use recent_errors

## Overview

The `recent_errors` tool reads the errors this site logged recently: Error Log entries and failed scheduled jobs, newest first. It only reads and never writes an Error Log row. It needs the System Manager role.

Use it after running or saving a Server Script, hook or scheduled job you built, to see the traceback it caused instead of guessing.

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `minutes` | integer | No | How far back to look. Default 60, maximum 1440 |
| `contains` | string | No | Only errors whose text contains this, for example a Server Script name |
| `limit` | integer | No | Most rows from each list. Default 10, maximum 50 |

## Reading the result

- `errors`: Error Log rows with `when`, `title` (the log's method), `reference` (the DocType and name it was about, if any) and `error`.
- `failed_jobs`: Scheduled Job Log rows with status `Failed`, with `when`, `job` and `details`. `contains` matches the job name or its details.

`contains` is matched literally: `%` and `_` are ordinary characters.

`error` and `details` keep only the last 4000 characters, which is where a traceback names its cause.

Error text can include request data or secrets. Treat it as private and do not repeat it outside this conversation.

## Best Practices

1. **Run, then read** — trigger the script, then call this with `contains` set to its name.
2. **Keep the window short** — a small `minutes` avoids mixing in older, unrelated errors.
3. **An empty list is not proof the script worked** — it may not have run; confirm the trigger fired.
