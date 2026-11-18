import { defineStore } from "pinia";
import { computed, ref } from "vue";

export const useSupportStore = defineStore("support", () => {
	const isOpen = ref(false);
	// "issue" | "feedback"
	const mode = ref("issue");
	// Seeded when opened from an active chat; null otherwise.
	const conversationId = ref(null);
	// Seed text for the issue description (e.g. a failed turn's details); null otherwise.
	const prefill = ref(null);

	// Mounted SupportModal instances. Where none is mounted (the Desk widget) open() would
	// do nothing visible, so entry points hide themselves when canOpen is false.
	const hosts = ref(0);
	const canOpen = computed(() => hosts.value > 0);

	function registerHost() {
		hosts.value += 1;
	}

	function unregisterHost() {
		hosts.value = Math.max(0, hosts.value - 1);
	}

	function open({ mode: m = "issue", conversationId: cid = null, prefill: seed = null } = {}) {
		mode.value = m;
		conversationId.value = cid;
		prefill.value = seed;
		isOpen.value = true;
	}

	function close() {
		isOpen.value = false;
		conversationId.value = null;
		prefill.value = null;
	}

	return { isOpen, mode, conversationId, prefill, canOpen, registerHost, unregisterHost, open, close };
});
