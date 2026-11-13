// The Pages gallery the fac-pages Desk page shows at /app/fac-pages. Keep this first line a comment:
// fac_pages.js inlines the file through Frappe's render_include from a line that starts with "//".
//
// It lists what list_pages returns, which is what get_page would open, so the user only sees pages
// that open. Desk is the one place a user without FAC Chat can find a page shared with them. The
// cards come from fac_page_card.js; this file lays them out with search and filters. Tested by
// chat/frontend/src/widget/desk/facPageIndex.spec.js.

// Each filter chip: its label and which pages it keeps.
const FAC_PAGE_INDEX_FILTERS = [
	["all", "All", () => true],
	["mine", "Mine", (page) => page.visibility !== "Shared"],
	["shared", "Shared", (page) => page.visibility === "Shared" && !page.draft],
	["drafts", "Drafts", (page) => page.draft],
];

// eslint-disable-next-line no-unused-vars
function fac_page_index({ pages, href, updated, kit_css, can_chat, actions = {} } = {}) {
	const root = fac_page_index_el("div", "fac-page-index", "display:flex;flex-direction:column;gap:16px;padding:16px;");
	const all = fac_page_index_order(pages || []);
	const card_options = { href, updated, kit_css, can_chat, actions };
	if (!all.length) {
		root.append(
			fac_page_index_el("p", "text-muted fac-page-index-empty", "margin:0;", __("No pages have been shared with you yet."))
		);
		if (can_chat && actions.new_page) root.append(fac_page_index_grid([fac_page_index_new_tile(actions.new_page)]));
		return root;
	}

	const state = { filter: "all", query: "" };
	const search = fac_page_index_el("input", "form-control input-sm fac-page-index-search", "max-width:320px;");
	search.type = "search";
	search.placeholder = __("Search pages…");
	search.setAttribute("aria-label", __("Search pages"));

	const chips = fac_page_index_el("div", "fac-page-index-chips", "display:flex;flex-wrap:wrap;gap:6px;");
	const chip_buttons = [];
	for (const [key, label, keeps] of FAC_PAGE_INDEX_FILTERS) {
		const count = all.filter(keeps).length;
		if (key === "drafts" && !count) continue;
		const chip = fac_page_index_el("button", "btn btn-default btn-xs fac-page-index-chip", "border-radius:999px;", `${__(label)} ${count}`);
		chip.type = "button";
		chip.dataset.filter = key;
		chip.addEventListener("click", () => {
			state.filter = key;
			apply();
		});
		chip_buttons.push(chip);
		chips.append(chip);
	}

	const cards = all.map((page) => {
		const card = fac_page_card(page, card_options);
		card.dataset.search = `${page.title || page.name} ${page.description || ""}`.toLowerCase();
		card._fac_page = page;
		return card;
	});
	const tiles = can_chat && actions.new_page ? [fac_page_index_new_tile(actions.new_page)] : [];
	const grid = fac_page_index_grid([...cards, ...tiles]);
	const nomatch = fac_page_index_el("p", "text-muted fac-page-index-nomatch", "margin:0;");
	nomatch.hidden = true;

	function apply() {
		const keeps = FAC_PAGE_INDEX_FILTERS.find(([key]) => key === state.filter)[2];
		const query = state.query.trim().toLowerCase();
		let shown = 0;
		for (const card of cards) {
			card.hidden = !(keeps(card._fac_page) && (!query || card.dataset.search.includes(query)));
			if (!card.hidden) shown++;
		}
		for (const chip of chip_buttons) chip.classList.toggle("active", chip.dataset.filter === state.filter);
		nomatch.hidden = shown > 0;
		nomatch.textContent = query ? __("No pages match “{0}”", [state.query.trim()]) : __("No pages here yet.");
	}
	search.addEventListener("input", () => {
		state.query = search.value;
		apply();
	});

	root.append(search, chips, grid, nomatch);
	fac_page_index_scale_previews(grid);
	apply();
	return root;
}

// The user's own pages first, then shared ones, each in the order list_pages gave.
function fac_page_index_order(pages) {
	return [...pages.filter((page) => page.visibility !== "Shared"), ...pages.filter((page) => page.visibility === "Shared")];
}

function fac_page_index_grid(items) {
	const grid = fac_page_index_el(
		"ul",
		"fac-page-index-list",
		"display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px;margin:0;padding:0;list-style:none;"
	);
	grid.append(...items);
	return grid;
}

function fac_page_index_new_tile(new_page) {
	const tile = fac_page_index_el(
		"li",
		"fac-page-index-new",
		"display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;min-height:180px;cursor:pointer;" +
			"border:1px dashed var(--border-color);border-radius:var(--border-radius-lg);color:var(--text-color);"
	);
	tile.setAttribute("role", "button");
	tile.tabIndex = 0;
	tile.append(
		fac_page_index_el("span", "fac-page-index-new-label", "font-weight:600;", __("+ New page")),
		fac_page_index_el("span", "text-muted small", "", __("Describe it to FACO"))
	);
	tile.addEventListener("click", () => new_page());
	tile.addEventListener("keydown", (event) => {
		if (event.key === "Enter" || event.key === " ") {
			event.preventDefault();
			new_page();
		}
	});
	return tile;
}

// A preview lays the page out FAC_PAGE_PREVIEW_WIDTH wide and is scaled to its card's width.
function fac_page_index_scale_previews(grid) {
	if (typeof ResizeObserver === "undefined") return;
	new ResizeObserver(() => {
		const box = grid.querySelector(".fac-page-index-preview");
		if (box && box.clientWidth) grid.style.setProperty("--fac-preview-scale", String(box.clientWidth / FAC_PAGE_PREVIEW_WIDTH));
	}).observe(grid);
}
