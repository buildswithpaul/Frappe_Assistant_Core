/** Pure search, filter, grouping and counting for the Pages list. */

export const FILTERS = ["all", "mine", "shared", "drafts"];

const isShared = (page) => page.visibility === "Shared";

export function matchesFilter(page, filter) {
	if (filter === "mine") return !isShared(page);
	if (filter === "shared") return isShared(page);
	if (filter === "drafts") return Boolean(page.draft);
	return true;
}

/** Pages whose title (or name, when untitled) contains the query, ignoring case. */
export function searchPages(pages, query) {
	const needle = (query || "").trim().toLowerCase();
	if (!needle) return pages;
	return pages.filter((page) => (page.title || page.name).toLowerCase().includes(needle));
}

/** Splits into the user's own pages and shared ones (drafts included), keeping order. */
export function groupPages(pages) {
	return {
		mine: pages.filter((page) => !isShared(page)),
		shared: pages.filter(isShared),
	};
}

export function countPages(pages) {
	return Object.fromEntries(
		FILTERS.map((filter) => [filter, pages.filter((page) => matchesFilter(page, filter)).length]),
	);
}
