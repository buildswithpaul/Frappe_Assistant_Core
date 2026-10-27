import { defineStore } from "pinia";
import { computed, ref, watch } from "vue";

import { facPage } from "@/api/domains/facPage";
import { usePagePanel } from "@/composables/usePagePanel";
import { logger } from "@/utils/logger";

export const usePagesStore = defineStore("pages", () => {
	const pages = ref([]);
	const loaded = ref(false);
	const hasPages = computed(() => pages.value.length > 0);

	async function load() {
		try {
			pages.value = (await facPage.listPages()) || [];
		} catch (error) {
			logger.error("FAC Pages could not be listed", error);
			pages.value = [];
		} finally {
			loaded.value = true;
		}
	}

	let loading = null;
	/** Loads the list the first time it is asked for. */
	function ensureLoaded() {
		if (!loaded.value && !loading) loading = load().finally(() => (loading = null));
		return loading || Promise.resolve();
	}

	// A chip's version moves exactly when a page write lands in chat, so the list is stale then.
	const { chips } = usePagePanel();
	const versionSum = computed(() => chips.value.reduce((sum, chip) => sum + (chip.version || 0), 0));
	watch(versionSum, () => {
		if (loaded.value) load();
	});

	return { pages, loaded, hasPages, load, ensureLoaded };
});
