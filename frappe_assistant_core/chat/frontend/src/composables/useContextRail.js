import { ref, computed, watch, onMounted, onUnmounted } from "vue";

// Breakpoints (px). Inclusive lower bound for each band.
export const RAIL_WIDE_MIN = 1280; // >= → docked rail
export const RAIL_TAB_MIN = 768; // 768..1279 → slim tab that slides open
// < 768 → bottom sheet

/**
 * Resolve rail mode purely from inputs — exported for unit testing without a
 * window. Returns "hidden" | "sheet" | "tab" | "rail".
 */
export function resolveRailMode(width, hasArtifacts) {
	if (!hasArtifacts) return "hidden";
	if (width >= RAIL_WIDE_MIN) return "rail";
	if (width >= RAIL_TAB_MIN) return "tab";
	return "sheet";
}

/**
 * @param {import('vue').Ref<boolean>|import('vue').ComputedRef<boolean>} hasArtifacts
 */
export function useContextRail(hasArtifacts) {
	const viewportWidth = ref(typeof window !== "undefined" ? window.innerWidth : 1280);

	// Whether the collapsible surface (tab → panel, or bottom sheet) is open.
	// Docked "rail" mode ignores this (always shown unless manually collapsed).
	const isOpen = ref(false);

	// Whether the user manually collapsed the *docked* rail to reclaim width.
	// Only meaningful in "rail" mode; a slim reopen tab brings it back. Reset on
	// each new turn's artifacts (see watch below) so a fresh result re-shows it.
	const dockCollapsed = ref(false);

	const mode = computed(() => resolveRailMode(viewportWidth.value, !!hasArtifacts.value));

	// Docked rail shows unless the user collapsed it; tab/sheet show only when opened.
	const isVisible = computed(() => {
		if (mode.value === "rail") return !dockCollapsed.value;
		if (mode.value === "tab" || mode.value === "sheet") return isOpen.value;
		return false;
	});

	// The slim affordance (tab on laptop, sheet handle on mobile) shows whenever
	// there are artifacts but the rail isn't docked.
	const showAffordance = computed(() => mode.value === "tab" || mode.value === "sheet");

	// The docked rail's own reopen tab — shown only when docked and collapsed.
	const showDockReopen = computed(() => mode.value === "rail" && dockCollapsed.value);

	function open() {
		isOpen.value = true;
	}
	function close() {
		isOpen.value = false;
	}
	function toggle() {
		isOpen.value = !isOpen.value;
	}
	function collapseDock() {
		dockCollapsed.value = true;
	}
	function expandDock() {
		dockCollapsed.value = false;
	}

	// A new turn that produces artifacts re-shows a previously collapsed dock —
	// collapsing dismisses the *current* turn's rail, it isn't a sticky setting.
	watch(
		() => hasArtifacts.value,
		(has) => {
			if (has) dockCollapsed.value = false;
		},
	);

	function onResize() {
		viewportWidth.value = window.innerWidth;
		// Collapse any open overlay when we cross up into docked mode so we don't
		// leave a stale "open" flag that fights the docked layout.
		if (mode.value === "rail") isOpen.value = false;
	}

	onMounted(() => {
		if (typeof window !== "undefined") {
			window.addEventListener("resize", onResize, { passive: true });
		}
	});
	onUnmounted(() => {
		if (typeof window !== "undefined") {
			window.removeEventListener("resize", onResize);
		}
	});

	return {
		viewportWidth,
		mode,
		isVisible,
		isOpen,
		showAffordance,
		showDockReopen,
		dockCollapsed,
		open,
		close,
		toggle,
		collapseDock,
		expandDock,
	};
}
