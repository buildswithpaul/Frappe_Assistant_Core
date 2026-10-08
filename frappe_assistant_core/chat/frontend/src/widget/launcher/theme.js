export function mirrorDeskTheme(host) {
	const html = document.documentElement;
	const sync = () =>
		host.setAttribute("data-theme", html.getAttribute("data-theme") === "dark" ? "dark" : "light");
	sync();
	const observer = new MutationObserver(sync);
	observer.observe(html, { attributes: true, attributeFilter: ["data-theme"] });
	return () => observer.disconnect();
}
