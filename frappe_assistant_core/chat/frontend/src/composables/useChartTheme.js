/**
 * useChartTheme — resolves FACO CSS theme variables to concrete hex colors
 * for canvas-based chart libraries (ECharts) that can't interpret
 * `var(--...)` strings directly.
 *
 * Returns a reactive object that updates when the theme toggles, so charts
 * re-render with the new palette without remounting.
 *
 * Pass the chart's element when it may render in the Desk widget: there the
 * tokens and data-theme live on the shadow host (the widget build retargets
 * :root to :host), so <html> carries no tokens at all.
 */

import { ref, onMounted, onUnmounted } from "vue";

const VAR_NAMES = {
	text: "--ql-text",
	textSecondary: "--ql-text-secondary",
	muted: "--ql-text-muted",
	border: "--ql-border",
	bg: "--ql-bg",
	card: "--ql-surface",
	primary: "--ql-accent",
};

/** The element that declares the tokens and data-theme: the shadow host, or <html>. */
function themeRoot(el) {
	const root = el?.getRootNode?.();
	return root instanceof ShadowRoot ? root.host : document.documentElement;
}

function readVars(el) {
	if (typeof window === "undefined") return {};
	const root = themeRoot(el);
	const style = getComputedStyle(root);
	const out = {};
	for (const [key, name] of Object.entries(VAR_NAMES)) {
		out[key] = style.getPropertyValue(name).trim() || null;
	}
	out.isDark = root.getAttribute("data-theme") === "dark";
	return out;
}

export function useChartTheme(elementRef = null) {
	const colors = ref(readVars());

	function refresh() {
		colors.value = readVars(elementRef?.value);
	}

	let observer = null;

	onMounted(() => {
		// Refresh once after mount (CSS vars may not be computed yet at
		// setup time on first paint).
		refresh();

		// Watch for theme toggles — FACO swaps themes via a data-theme
		// attribute on <html>, which the widget mirrors onto its host.
		// MutationObserver is cheap and avoids the need for a global bus.
		observer = new MutationObserver(refresh);
		observer.observe(themeRoot(elementRef?.value), {
			attributes: true,
			attributeFilter: ["data-theme", "class"],
		});
	});

	onUnmounted(() => {
		observer?.disconnect();
	});

	return { colors };
}
