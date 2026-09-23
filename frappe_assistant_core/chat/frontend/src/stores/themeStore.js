import { defineStore } from "pinia";
import { ref, computed, watch } from "vue";

export const useThemeStore = defineStore("theme", () => {
	// Theme priority:
	// 1. data-theme on <html> (set by Frappe desk on /app pages)
	// 2. window.theme from boot data (injected by copilot.py for the SPA)
	// 3. System preference (prefers-color-scheme)
	const htmlTheme = document.documentElement.getAttribute("data-theme");
	const bootTheme = window.theme || null;
	const initialTheme = htmlTheme || bootTheme || null;

	const frappeTheme = ref(initialTheme);
	const systemPrefersDark = ref(window.matchMedia("(prefers-color-scheme: dark)").matches);

	const effectiveTheme = computed(() => {
		if (frappeTheme.value && frappeTheme.value !== "automatic") {
			return frappeTheme.value;
		}
		// "automatic" or no preference: follow system
		return systemPrefersDark.value ? "dark" : "light";
	});

	const isDark = computed(() => effectiveTheme.value === "dark");

	// Keep data-theme on <html> in sync so CSS selectors like [data-theme="dark"] work
	watch(
		effectiveTheme,
		(theme) => {
			document.documentElement.setAttribute("data-theme", theme);
		},
		{ immediate: true }
	);

	function initThemeWatcher() {
		const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
		mediaQuery.addEventListener("change", (e) => {
			systemPrefersDark.value = e.matches;
		});

		// Watch for external changes to data-theme (e.g. if Frappe desk toggles theme)
		const observer = new MutationObserver((mutations) => {
			for (const mutation of mutations) {
				if (mutation.type === "attributes") {
					const attr = mutation.attributeName;
					if (attr === "data-theme" || attr === "data-theme-mode") {
						const newTheme = document.documentElement.getAttribute("data-theme");
						if (newTheme && newTheme !== effectiveTheme.value) {
							frappeTheme.value = newTheme;
						}
					}
				}
			}
		});

		observer.observe(document.documentElement, {
			attributes: true,
			attributeFilter: ["data-theme", "data-theme-mode"],
		});
	}

	return {
		effectiveTheme,
		isDark,
		frappeTheme,
		initThemeWatcher,
	};
});
