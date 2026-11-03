/**
 * Which usage view a visitor sees. Members only ever see their own usage; an admin sees the
 * workspace unless the URL asks for their own (`?view=me`).
 */
export function resolveUsageView(isAdmin, query) {
	if (!isAdmin) return "me";
	return query?.view === "me" ? "me" : "workspace";
}
