import { defineStore } from "pinia";
import { ref } from "vue";

// Shared mobile-drawer state for the app shell: the TopBar hamburger, the
// off-canvas NavigationSidebar, and the scrim all read/write this one flag.
export const useLayoutStore = defineStore("layout", () => {
	const drawerOpen = ref(false);

	function openDrawer() {
		drawerOpen.value = true;
	}
	function closeDrawer() {
		drawerOpen.value = false;
	}
	function toggleDrawer() {
		drawerOpen.value = !drawerOpen.value;
	}

	return { drawerOpen, openDrawer, closeDrawer, toggleDrawer };
});
