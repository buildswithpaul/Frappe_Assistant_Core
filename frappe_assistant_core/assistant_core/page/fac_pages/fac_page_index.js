// The list of pages the fac-pages Desk page shows at /app/fac-pages. Keep this first line a comment:
// fac_pages.js inlines the file through Frappe's render_include from a line that starts with "//".
//
// It lists what list_pages returns, which is what get_page would open, so the user only sees pages
// that open. Desk is the one place a user without FAC Chat can find a page shared with them. Every
// title and role is the page author's text, so it is set as text, never as html. Tested by
// chat/frontend/src/widget/desk/facPageIndex.spec.js.

const FAC_PAGE_INDEX_MAX_ROLES = 2;

// eslint-disable-next-line no-unused-vars
function fac_page_index({ pages, href, updated, chat_url } = {}) {
	const root = fac_page_index_el("div", "fac-page-index", "display:flex;flex-direction:column;gap:24px;padding:16px;");
	if (chat_url) {
		const link = fac_page_index_el("a", "btn btn-default btn-sm fac-page-index-chat", "align-self:flex-end;");
		link.href = chat_url;
		link.textContent = __("Open in FAC Chat");
		root.append(link);
	}
	const mine = (pages || []).filter((page) => page.visibility !== "Shared");
	const shared = (pages || []).filter((page) => page.visibility === "Shared");
	if (!mine.length && !shared.length) {
		root.append(
			fac_page_index_el("p", "text-muted fac-page-index-empty", "margin:0;", __("No pages have been shared with you yet."))
		);
		return root;
	}
	if (mine.length) root.append(fac_page_index_section(__("Your pages"), mine, href, updated));
	if (shared.length) root.append(fac_page_index_section(__("Shared with you"), shared, href, updated));
	return root;
}

function fac_page_index_section(title, pages, href, updated) {
	const section = fac_page_index_el("section", "fac-page-index-section");
	const heading = fac_page_index_el(
		"h2",
		"fac-page-index-heading",
		"margin:0 0 12px;font-size:12px;font-weight:600;letter-spacing:0.04em;text-transform:uppercase;color:var(--text-muted);",
		`${title} · ${pages.length}`
	);
	const list = fac_page_index_el(
		"ul",
		"fac-page-index-list",
		"display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px;margin:0;padding:0;list-style:none;"
	);
	for (const page of pages) list.append(fac_page_index_item(page, href, updated));
	section.append(heading, list);
	return section;
}

function fac_page_index_item(page, href, updated) {
	const item = fac_page_index_el("li");
	const link = fac_page_index_el(
		"a",
		"fac-page-index-item",
		"display:flex;flex-direction:column;gap:4px;height:100%;padding:12px 14px;border:1px solid var(--border-color);" +
			"border-radius:var(--border-radius-lg);background:var(--card-bg);color:var(--text-color);text-decoration:none;"
	);
	link.href = href(page.name);
	link.append(
		fac_page_index_el("span", "fac-page-index-title", "font-weight:600;overflow-wrap:anywhere;", page.title || page.name),
		fac_page_index_el("span", "text-muted small fac-page-index-context", "", fac_page_index_context(page))
	);
	if (page.modified) {
		link.append(
			fac_page_index_el("span", "text-muted small fac-page-index-updated", "", __("Updated {0}", [updated(page.modified)]))
		);
	}
	item.append(link);
	return item;
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
