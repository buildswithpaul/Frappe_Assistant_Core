/**
 * A link to this site, made relative when the app is open on another address.
 *
 * Answers link to records on the site's configured address (host_name), e.g.
 * http://erp.example.com/desk/sales-invoice/new. FAC Chat can be open on another address for
 * the same site: a custom domain, a proxy, an installed home-screen app. iOS opens a link to
 * any other address in an in-app browser with its own logins, so the user lands on a login
 * page. A relative link stays on the address FAC Chat is on, logged in.
 *
 * @param {string} href - the link as written
 * @param {string} [siteUrl] - the site's own address (boot `site_url`)
 * @param {string} [here] - the address FAC Chat is open on
 * @returns {string} the link to use
 */
export function localizeSiteLink(href, siteUrl = window.site_url, here = window.location.origin) {
	if (!href || !siteUrl) return href;
	let url;
	let site;
	try {
		url = new URL(href);
		site = new URL(siteUrl);
	} catch {
		return href; // relative, or not a URL: already stays where it is
	}
	if (url.origin !== site.origin || url.origin === here) return href;
	return `${url.pathname}${url.search}${url.hash}`;
}
