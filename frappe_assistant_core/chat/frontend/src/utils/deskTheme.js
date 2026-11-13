// Desk's light or dark theme, as html[data-theme] says (the chat SPA's themeStore writes the same
// attribute). The widget and FAC Pages follow it; anything but "dark" is light.

export function deskTheme(doc = document) {
	return doc.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
}

export function followDeskTheme(onChange, doc = document) {
	let last = deskTheme(doc);
	const observer = new MutationObserver(() => {
		const theme = deskTheme(doc);
		if (theme === last) return;
		last = theme;
		onChange(theme);
	});
	observer.observe(doc.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
	return () => observer.disconnect();
}

export function mirrorDeskTheme(host) {
	host.setAttribute("data-theme", deskTheme());
	return followDeskTheme((theme) => host.setAttribute("data-theme", theme));
}
