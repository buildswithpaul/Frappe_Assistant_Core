import { defineStore } from "pinia";
import { ref } from "vue";

export const useSupportStore = defineStore("support", () => {
	const isOpen = ref(false);
	// "issue" | "feedback"
	const mode = ref("issue");
	// Seeded when opened from an active chat; null otherwise.
	const conversationId = ref(null);

	function open({ mode: m = "issue", conversationId: cid = null } = {}) {
		mode.value = m;
		conversationId.value = cid;
		isOpen.value = true;
	}

	function close() {
		isOpen.value = false;
		conversationId.value = null;
	}

	return { isOpen, mode, conversationId, open, close };
});
