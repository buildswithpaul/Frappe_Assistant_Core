import { defineStore } from "pinia";
import { ref } from "vue";
import { api } from "@/api/client";
import { useTemplateStore } from "@/stores/templateStore";
import { startHostedCheckout } from "@/composables/_billing/hostedCheckout";

export const usePacksStore = defineStore("packs", () => {
	const items = ref([]);
	const purchases = ref([]);
	const loading = ref(false);
	const error = ref(null);
	const contents = ref({}); // pack_id -> { prompts, skills, loading, error }

	async function load() {
		loading.value = true;
		error.value = null;
		try {
			const res = await api.packs.list();
			items.value = res?.packs || [];
		} catch (e) {
			error.value = e?.message || String(e);
			items.value = [];
		} finally {
			loading.value = false;
		}
	}

	async function loadPurchases() {
		try {
			const res = await api.packs.listPurchases();
			purchases.value = res?.purchases || [];
		} catch (e) {
			error.value = e?.message || String(e);
			purchases.value = [];
		}
	}

	async function loadContents(pack_id) {
		if (contents.value[pack_id]?.prompts) return; // cached
		contents.value = {
			...contents.value,
			[pack_id]: { ...(contents.value[pack_id] || {}), loading: true, error: null },
		};
		try {
			const res = await api.packs.getContents(pack_id);
			contents.value = {
				...contents.value,
				[pack_id]: {
					prompts: res?.prompts || [],
					skills: res?.skills || [],
					loading: false,
					error: null,
				},
			};
		} catch (e) {
			contents.value = {
				...contents.value,
				[pack_id]: { prompts: [], skills: [], loading: false, error: e?.message || String(e) },
			};
		}
	}

	async function activateFreePack(pack_id) {
		await api.packs.activateFree(pack_id);
		const templateStore = useTemplateStore();
		templateStore.templates = [];
		templateStore.categories = [];
		await Promise.all([load(), templateStore.loadTemplates()]);
	}

	async function togglePurchasedPack(pack_id, enabled) {
		const previous = items.value.find((p) => p.pack_id === pack_id)?.enabled;
		items.value = items.value.map((p) =>
			p.pack_id === pack_id ? { ...p, enabled } : p,
		);
		try {
			await api.packs.togglePurchased(pack_id, enabled);
			const templateStore = useTemplateStore();
			templateStore.templates = [];
			templateStore.categories = [];
			await templateStore.loadTemplates();
		} catch (e) {
			items.value = items.value.map((p) =>
				p.pack_id === pack_id ? { ...p, enabled: previous } : p,
			);
			throw e;
		}
	}

	// Payment happens on FAC Cloud, not here. Never resolves — the browser
	// navigates away and comes back to this page once the pack is enabled,
	// which `load()` on mount then reflects.
	async function purchasePack(pack_id) {
		await startHostedCheckout("Pack", { pack_id });
	}

	// Backwards-compatible alias used by existing code paths.
	// NOTE: delegates to togglePurchasedPack which calls toggle_purchased_pack
	// (acquisition-enforced). Callers on free_grant/admin_grant rows will get
	// a ValidationError — that is correct under the new contract.
	async function setEnabled(pack_id, enabled) {
		await togglePurchasedPack(pack_id, enabled);
	}

	return {
		items,
		purchases,
		loading,
		error,
		contents,
		load,
		loadPurchases,
		loadContents,
		activateFreePack,
		togglePurchasedPack,
		purchasePack,
		setEnabled,
	};
});
