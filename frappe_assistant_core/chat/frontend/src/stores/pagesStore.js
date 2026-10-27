import { defineStore } from "pinia";
import { computed, ref, watch } from "vue";

import { facPage } from "@/api/domains/facPage";
import { usePagePanel } from "@/composables/usePagePanel";
import { logger } from "@/utils/logger";

export const usePagesStore = defineStore("pages", () => {
	const pages = ref([]);
	const loaded = ref(false);
	const error = ref(false);
	const hasPages = computed(() => pages.value.length > 0);

	// Only the newest request may write, so a slow older response cannot overwrite a newer list.
	let latestRequest = 0;
	async function load() {
		const request = ++latestRequest;
		try {
			const result = (await facPage.listPages()) || [];
			if (request !== latestRequest) return;
			pages.value = result;
			error.value = false;
			loaded.value = true;
		} catch (err) {
			logger.error("FAC Pages could not be listed", err);
			// The earlier list stays, and `loaded` stays as it was so ensureLoaded tries again.
			if (request === latestRequest) error.value = true;
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

	return { pages, loaded, error, hasPages, load, ensureLoaded };
});
