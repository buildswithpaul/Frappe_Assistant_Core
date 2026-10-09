export function hasFeaturedSubset(all = []) {
	const featured = all.filter((t) => t.featured).length;
	return featured > 0 && featured < all.length;
}

export function categoriesFrom(templates = [], selected = null) {
	const set = new Set(templates.map((t) => (t.category || "").trim()).filter(Boolean));
	if (selected && selected !== "All") set.add(selected);
	return [...set].sort((x, y) => x.localeCompare(y));
}
