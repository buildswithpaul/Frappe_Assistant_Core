// Home "Needs you" data: server-ranked signals merged with the client-only
// failed-workflows attention item. Loads after first paint and fails silent.
// Honours the user's home preferences carried on the payload (section off, card
// count, hidden signals); `hide` removes a card at once and restores it on failure.
import { computed, onBeforeUnmount, onMounted, ref, unref } from "vue";
import { api } from "@/api/client";
import { mergeSignals } from "@/components/chat/welcome/homeSignals";
import { useAttention } from "@/composables/useAttention";

const HIDE_FAILED_MS = 6000;

export function useHomeSignals({ cap }) {
	const server = ref(null);
	const loaded = ref(false);
	const failed = ref(false);
	const { attentionItem, loadAttention, dismiss } = useAttention();
	const locallyHidden = ref([]);
	const hideFailed = ref(false);
	let hideFailedTimer = null;

	async function loadHome() {
		try {
			server.value = await api.home.get();
		} catch {
			failed.value = true;
		}
	}

	async function load() {
		await Promise.allSettled([loadHome(), loadAttention()]);
		loaded.value = true;
	}

	let frame = null;
	onMounted(() => {
		frame = requestAnimationFrame(load);
	});
	onBeforeUnmount(() => {
		if (frame !== null) cancelAnimationFrame(frame);
		clearTimeout(hideFailedTimer);
	});

	const isHidden = (item) =>
		locallyHidden.value.includes(item.id) || (server.value?.hidden_signals ?? []).includes(item.id);
	const enabled = computed(() => server.value?.needs_you_enabled !== false);
	const effectiveCap = computed(() => Math.min(unref(cap), server.value?.needs_you_count ?? Infinity));
	const items = computed(() =>
		mergeSignals(
			(server.value?.items ?? []).filter((item) => !isHidden(item)),
			attentionItem.value && !isHidden(attentionItem.value) ? attentionItem.value : null,
			effectiveCap.value
		)
	);

	async function hide(id) {
		hideFailed.value = false;
		locallyHidden.value = [...locallyHidden.value, id];
		try {
			await api.home.hideSignal(id);
			// The server cache is already invalidated: refetch so the next waiting signal fills the gap.
			await loadHome();
		} catch {
			locallyHidden.value = locallyHidden.value.filter((hiddenId) => hiddenId !== id);
			hideFailed.value = true;
			clearTimeout(hideFailedTimer);
			hideFailedTimer = setTimeout(() => (hideFailed.value = false), HIDE_FAILED_MS);
		}
	}
	const lensLabel = computed(() => server.value?.lens_label ?? null);
	const area = computed(() => server.value?.area ?? null);
	const company = computed(() => server.value?.company ?? null);

	return { items, enabled, lensLabel, area, company, loaded, failed, dismiss, hide, hideFailed };
}
