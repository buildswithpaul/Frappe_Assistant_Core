import { ref, onMounted, onBeforeUnmount } from "vue";

/**
 * Reactive viewport flags. Updates on window resize; cleans up on unmount.
 *
 * @param {number} breakpoint - Width below which the viewport is "mobile".
 * @returns {{ isMobile: import('vue').Ref<boolean>, isTablet: import('vue').Ref<boolean> }}
 *   isMobile = width < breakpoint. isTablet = breakpoint ≤ width < 1024.
 */
export function useIsMobile(breakpoint = 768) {
	const isMobile = ref(false);
	const isTablet = ref(false);

	function check() {
		const w = window.innerWidth;
		isMobile.value = w < breakpoint;
		isTablet.value = w >= breakpoint && w < 1024;
	}

	onMounted(() => {
		check();
		window.addEventListener("resize", check);
	});

	onBeforeUnmount(() => {
		window.removeEventListener("resize", check);
	});

	return { isMobile, isTablet };
}
