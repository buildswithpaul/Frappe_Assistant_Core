const DESK_PREFIX = /^\/(?:app|desk)\/(.+)$/;

/**
 * The Desk route segments for a same-origin /app/... (v15) or /desk/... (v16) link, or null to let the
 * browser handle it. A link carrying a query string or hash is left to a normal navigation: set_route
 * has no place for the filters, and dropping them would open the wrong list.
 */
export function deskRouteFor(href) {
	if (!href) return null;
	let url;
	try {
		url = new URL(href, window.location.origin);
	} catch {
		return null;
	}
	if (url.origin !== window.location.origin || url.search || url.hash) return null;
	const match = DESK_PREFIX.exec(url.pathname);
	return match ? match[1].split("/").map(decodeURIComponent) : null;
}
