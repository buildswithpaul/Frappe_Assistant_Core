/**
 * useChartTheme — resolves FACO CSS theme variables to concrete hex colors
 * for canvas-based chart libraries (ECharts) that can't interpret
 * `var(--...)` strings directly.
 *
 * Returns a reactive object that updates when the theme toggles, so charts
 * re-render with the new palette without remounting.
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

function readVars() {
	if (typeof window === "undefined") return {};
	const style = getComputedStyle(document.documentElement);
	const out = {};
	for (const [key, name] of Object.entries(VAR_NAMES)) {
		out[key] = style.getPropertyValue(name).trim() || null;
	}
	out.isDark = document.documentElement.getAttribute("data-theme") === "dark";
	return out;
}

export function useChartTheme() {
	const colors = ref(readVars());

	function refresh() {
		colors.value = readVars();
	}

	let observer = null;

	onMounted(() => {
		// Refresh once after mount (CSS vars may not be computed yet at
		// setup time on first paint).
		refresh();

		// Watch for theme toggles — FACO swaps themes via a data-theme
		// attribute on <html>. MutationObserver is cheap and avoids the
		// need for a global bus.
		observer = new MutationObserver(refresh);
		observer.observe(document.documentElement, {
			attributes: true,
			attributeFilter: ["data-theme", "class"],
		});
	});

	onUnmounted(() => {
		observer?.disconnect();
	});

	return { colors };
}
