// Home "Needs you" data: server-ranked signals merged with the client-only
// failed-workflows attention item. Loads after first paint and fails silent.
import { computed, onMounted, ref, unref } from "vue";
import { api } from "@/api/client";
import { mergeSignals } from "@/components/chat/welcome/homeSignals";
import { useAttention } from "@/composables/useAttention";

export function useHomeSignals({ cap }) {
	const server = ref(null);
	const loaded = ref(false);
	const failed = ref(false);
	const { attentionItem, loadAttention, dismiss } = useAttention();

	async function load() {
		try {
			server.value = await api.home.get();
		} catch {
			failed.value = true;
		} finally {
			loaded.value = true;
		}
	}

	onMounted(() => {
		requestAnimationFrame(() => {
			load();
			loadAttention();
		});
	});

	const items = computed(() => mergeSignals(server.value?.items, attentionItem.value, unref(cap)));
	const lens = computed(() => server.value?.lens_label ?? null);
	const area = computed(() => server.value?.area ?? null);
	const company = computed(() => server.value?.company ?? null);

	return { items, lens, area, company, loaded, failed, dismiss };
}
