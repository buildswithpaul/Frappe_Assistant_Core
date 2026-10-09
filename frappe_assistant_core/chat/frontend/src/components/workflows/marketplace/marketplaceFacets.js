export function sameTemplateSet(a = [], b = []) {
	if (!a.length || a.length !== b.length) return false;
	const names = new Set(a.map((t) => t.name));
	return b.every((t) => names.has(t.name));
}

export function categoriesFrom(templates = [], selected = null) {
	const set = new Set(templates.map((t) => (t.category || "").trim()).filter(Boolean));
	if (selected && selected !== "All") set.add(selected);
	return [...set].sort((x, y) => x.localeCompare(y));
}
