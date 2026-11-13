// One card of the Pages gallery at /app/fac-pages. Keep this first line a comment: fac_pages.js
// inlines the file through Frappe's render_include from a line that starts with "//".
//
// A card shows a preview of the page, its title, description, who it is shared with and when it
// changed, and a menu of what the user may do with it, as list_pages says. The preview is the
// page's static html, cleaned as a draft's, in an empty-sandbox frame with the draft CSP
// (fac_page_draft.js): it runs nothing and fetches nothing, so it shows layout, never data. Every
// title, description and role is the page author's text, so it is set as text, never as html.
// Tested by chat/frontend/src/widget/desk/facPageCard.spec.js.

const FAC_PAGE_INDEX_MAX_ROLES = 2;
// The width a preview lays the page out at before it is scaled down to the card.
const FAC_PAGE_PREVIEW_WIDTH = 1280;

// eslint-disable-next-line no-unused-vars
function fac_page_card(page, { href, updated, kit_css, can_chat, actions = {} } = {}) {
	const item = fac_page_index_el(
		"li",
		"fac-page-index-card",
		"position:relative;display:flex;flex-direction:column;border:1px solid var(--border-color);" +
			"border-radius:var(--border-radius-lg);background:var(--card-bg);overflow:hidden;"
	);
	const link = fac_page_index_el(
		"a",
		"fac-page-index-card-link",
		"display:flex;flex-direction:column;height:100%;color:var(--text-color);text-decoration:none;"
	);
	link.href = href(page.name);
	const meta = fac_page_index_el("div", "fac-page-index-meta", "display:flex;flex-direction:column;gap:3px;padding:10px 12px;");
	meta.append(
		fac_page_index_el("span", "fac-page-index-title", "font-weight:600;overflow-wrap:anywhere;padding-right:24px;", page.title || page.name)
	);
	if (page.description) {
		meta.append(fac_page_index_el("span", "text-muted small fac-page-index-description", "overflow-wrap:anywhere;", page.description));
	}
	meta.append(fac_page_index_el("span", "text-muted small fac-page-index-context", "", fac_page_index_context(page)));
	if (page.modified) {
		meta.append(fac_page_index_el("span", "text-muted small fac-page-index-updated", "", __("Updated {0}", [updated(page.modified)])));
	}
	link.append(fac_page_preview(page, kit_css), meta);
	item.append(link);
	const menu = fac_page_card_menu(page, can_chat, actions);
	if (menu) item.append(menu);
	return item;
}

function fac_page_preview(page, kit_css) {
	const box = fac_page_index_el(
		"div",
		"fac-page-index-preview",
		"position:relative;aspect-ratio:16/10;overflow:hidden;background:var(--subtle-fg);border-bottom:1px solid var(--border-color);"
	);
	if (!page.preview_html) {
		const letter = String(page.title || page.name || "?").trim().charAt(0).toUpperCase();
		box.append(
			fac_page_index_el(
				"div",
				"fac-page-index-tile",
				"position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:32px;" +
					"font-weight:600;color:var(--text-muted);",
				letter
			)
		);
		return box;
	}
	const frame = document.createElement("iframe");
	frame.setAttribute("sandbox", "");
	frame.setAttribute("loading", "lazy");
	frame.setAttribute("tabindex", "-1");
	frame.setAttribute("aria-hidden", "true");
	frame.style.cssText =
		`position:absolute;top:0;left:0;width:${FAC_PAGE_PREVIEW_WIDTH}px;height:${FAC_PAGE_PREVIEW_WIDTH * 0.625}px;` +
		"border:0;transform-origin:0 0;transform:scale(var(--fac-preview-scale, 0.22));pointer-events:none;background:#fff;";
	frame.srcdoc = fac_page_draft_srcdoc({ html: page.preview_html, style: page.preview_style, kit_css });
	box.append(frame);
	return box;
}

// Only what the user may do, as list_pages says; the server still decides each action.
function fac_page_card_menu(page, can_chat, actions) {
	const entries = [
		[__("Edit with FACO"), actions.edit, can_chat && page.can_manage],
		[__("Rename"), actions.rename, page.can_manage],
		[__("Share"), actions.share, can_chat && page.can_share],
		[__("Delete"), actions.remove, page.can_manage],
	].filter(([, action, allowed]) => action && allowed);
	if (!entries.length) return null;

	const wrap = fac_page_index_el("div", "fac-page-index-menu-wrap", "position:absolute;top:6px;right:6px;");
	const button = fac_page_index_el("button", "btn btn-default btn-xs fac-page-index-menu", "line-height:1;padding:2px 6px;", "⋯");
	button.type = "button";
	button.setAttribute("aria-label", __("Page actions"));
	button.setAttribute("aria-haspopup", "menu");
	button.setAttribute("aria-expanded", "false");
	const list = fac_page_index_el(
		"div",
		"fac-page-index-menu-list",
		"position:absolute;right:0;top:100%;z-index:5;min-width:160px;margin-top:4px;padding:4px 0;display:flex;flex-direction:column;" +
			"background:var(--card-bg);border:1px solid var(--border-color);border-radius:var(--border-radius-md);box-shadow:var(--shadow-md);"
	);
	list.setAttribute("role", "menu");
	list.hidden = true;
	const items = entries.map(([label, action]) => {
		const entry = fac_page_index_el(
			"button",
			"fac-page-index-menu-item",
			"padding:6px 12px;border:0;background:none;text-align:left;white-space:nowrap;color:var(--text-color);",
			label
		);
		entry.type = "button";
		entry.setAttribute("role", "menuitem");
		entry.addEventListener("click", () => {
			close(false);
			action(page);
		});
		list.append(entry);
		return entry;
	});

	const outside = (event) => {
		if (!wrap.contains(event.target)) close(false);
	};
	function open() {
		list.hidden = false;
		button.setAttribute("aria-expanded", "true");
		document.addEventListener("click", outside, true);
		items[0].focus();
	}
	function close(refocus) {
		if (list.hidden) return;
		list.hidden = true;
		button.setAttribute("aria-expanded", "false");
		document.removeEventListener("click", outside, true);
		if (refocus) button.focus();
	}
	button.addEventListener("click", (event) => {
		event.preventDefault();
		if (list.hidden) open();
		else close(true);
	});
	// Escape closes; arrow keys move between the items, as a menu does.
	list.addEventListener("keydown", (event) => {
		const at = items.indexOf(document.activeElement);
		if (event.key === "Escape") {
			event.preventDefault();
			close(true);
		} else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
			event.preventDefault();
			const step = event.key === "ArrowDown" ? 1 : -1;
			items[(at + step + items.length) % items.length].focus();
		}
	});
	wrap.append(button, list);
	return wrap;
}

// Desk's frappe.confirm renders its message as html, and __ does not escape its arguments.
// eslint-disable-next-line no-unused-vars
function fac_page_delete_message(title) {
	return __("Delete the page “{0}”? This cannot be undone.", [fac_page_index_escape(title)]);
}

const FAC_PAGE_INDEX_ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

function fac_page_index_escape(text) {
	return String(text == null ? "" : text).replace(/[&<>"']/g, (char) => FAC_PAGE_INDEX_ESCAPES[char]);
}

function fac_page_index_context(page) {
	if (page.draft) return __("Draft · not published yet, only admins see it");
	if (page.visibility !== "Shared") return __("Only you");
	const roles = page.roles || [];
	if (!roles.length) return __("Shared");
	const shown = roles.slice(0, FAC_PAGE_INDEX_MAX_ROLES).join(", ");
	const more = roles.length - FAC_PAGE_INDEX_MAX_ROLES;
	return __("Shared with {0}", [more > 0 ? `${shown} +${more}` : shown]);
}

function fac_page_index_el(tag, class_name, css, text) {
	const el = document.createElement(tag);
	if (class_name) el.className = class_name;
	if (css) el.style.cssText = css;
	if (text !== undefined) el.textContent = text;
	return el;
}
