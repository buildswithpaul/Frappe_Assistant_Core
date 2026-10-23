# Mockup Kit

## Overview

Use this kit to write the `mockup_html` shown with a build plan. The mockup is plain HTML in a sandboxed preview that already carries the kit's styles. It cannot load anything from the network and cannot reach the page around it, so write static markup only.

## Rules

- Write the inside of a page: no `<html>`, `<head>` or `<body>` tags.
- Use inline `<svg>` or `data:` URIs for images. Nothing external loads (no fonts, scripts, stylesheets or image URLs).
- Keep it under 200 KB, and show the screen as the user will see it, with sample data.

## Classes

| Class | Use |
|---|---|
| `mk-page` | outer wrapper, adds padding and spacing |
| `mk-card` | bordered panel |
| `mk-btn`, `mk-btn-primary` | buttons (primary is the filled one) |
| `mk-badge` | small status pill |
| `mk-table` | table with a muted header row |
| `mk-field` | a label above an input, select or textarea |
| `mk-tabs` | row of tabs; mark the current child with `active` |
| `mk-stat` | a small label over a large number |

## Example

```html
<div class="mk-page">
  <div class="mk-tabs"><span class="active">Overview</span><span>Activity</span></div>
  <div class="mk-card">
    <div class="mk-stat"><span>Open orders</span><span>24</span></div>
  </div>
  <div class="mk-field"><label>Customer</label><input value="Acme Ltd"></div>
  <table class="mk-table">
    <tr><th>Order</th><th>Status</th></tr>
    <tr><td>SO-0001</td><td><span class="mk-badge">Draft</span></td></tr>
  </table>
  <button class="mk-btn mk-btn-primary">Save</button>
</div>
```
