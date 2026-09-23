import { computed } from "vue";
import { useLayoutStore } from "@/stores/layoutStore";
import { useIsMobile } from "@/composables/useIsMobile";

/**
 * Unified hamburger behavior for every top bar. Below 1024px the sidebar is an
 * off-canvas drawer (matching the CSS `max-width: 1023px` rule), so the hamburger
 * opens/closes that drawer; at >=1024px it falls back to the host's existing
 * sidebar-collapse emit. The `isDrawerWidth` flag (phone OR tablet) keeps the JS
 * trigger aligned with the CSS breakpoint so the drawer is reachable on tablets.
 *
 * @returns {{ isMobile: import('vue').Ref<boolean>, isDrawerWidth: import('vue').ComputedRef<boolean>, onHamburger: (emit?: () => void) => void }}
 */
export function useNavToggle() {
	const layout = useLayoutStore();
	const { isMobile, isTablet } = useIsMobile();

	// Drawer form applies at < 1024 (phone + tablet).
	const isDrawerWidth = computed(() => isMobile.value || isTablet.value);

	function onHamburger(emitToggle) {
		if (isDrawerWidth.value) layout.toggleDrawer();
		else if (typeof emitToggle === "function") emitToggle();
	}

	return { isMobile, isDrawerWidth, onHamburger };
}
