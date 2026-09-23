import { computed } from "vue";

/**
 * Minimap coloring helpers — Quiet Ledger teal node dots + theme-aware mask.
 *
 * Node dots resolve to the live `--ql-accent` token (teal: #0F6E5C light /
 * #2DAA8F dark) so the mini-map reads as a single calm accent rather than a
 * rainbow of per-type hues. The mask is a translucent wash keyed on the
 * resolved theme so the off-viewport area dims without tinting the paper.
 *
 * @param {object} themeStore - Pinia theme store exposing reactive
 *   `effectiveTheme` ("light" | "dark").
 */
export function useWorkflowMinimap(themeStore) {
	function minimapNodeColor() {
		return getComputedStyle(document.documentElement)
			.getPropertyValue("--ql-accent")
			.trim();
	}

	const minimapMaskColor = computed(() =>
		themeStore.effectiveTheme === "dark"
			? "rgba(255, 255, 255, 0.06)"
			: "rgba(0, 0, 0, 0.05)"
	);

	return { minimapNodeColor, minimapMaskColor };
}
