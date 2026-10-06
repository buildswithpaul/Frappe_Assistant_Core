/**
 * Retarget FAC Chat's page-level CSS for a shadow root (widget build only).
 * Inside a shadow root :root and html/body match nothing, so tokens would
 * never apply and theme switches would never land.
 */
const THEME = /(?:html)?\[data-theme=["']?([\w-]+)["']?\]/g;
const PAGE_ONLY = new Set(["html", "body", "#app"]);

export function postcssShadowHost() {
	return {
		postcssPlugin: "fac-shadow-host",
		Rule(rule) {
			const kept = rule.selectors.filter((s) => !PAGE_ONLY.has(s.trim()));
			if (kept.length === 0) {
				rule.remove();
				return;
			}
			rule.selectors = kept.map((s) =>
				s.replace(/:root\b/g, ":host").replace(THEME, (_m, theme) => `:host([data-theme="${theme}"])`)
			);
		},
	};
}
postcssShadowHost.postcss = true;
