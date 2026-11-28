import { ref, computed } from "vue";
import { defineStore } from "pinia";
import { api } from "@/api/client";
import { logger } from "@/utils/logger";

/**
 * The user's auto-approve mode, as the server holds it. In the mode the assistant runs everyday
 * creates and updates without an approval card and lists them in its reply. The server decides
 * what each turn is sent, so this store only shows the switch and saves the choice.
 */
export const useApprovalModeStore = defineStore("approvalMode", () => {
	// Whether this site's FAC Cloud offers the mode; without it there is no switch.
	const available = ref(false);
	const on = ref(true);
	const noticeSeen = ref(false);
	const saving = ref(false);

	// The mode reaches the assistant only once its notice has been seen.
	const active = computed(() => available.value && on.value && noticeSeen.value);
	const showNotice = computed(() => available.value && !noticeSeen.value);

	/** Take the server's state: `{ available, on, notice_seen }` from start-up or a save. */
	function apply(state) {
		if (!state || typeof state !== "object") return;
		available.value = state.available === true;
		on.value = state.on !== false;
		noticeSeen.value = state.notice_seen === true;
	}

	async function save(request) {
		if (saving.value) return;
		saving.value = true;
		try {
			apply(await request());
		} catch (error) {
			logger.warn("Could not save auto-approve mode", error);
		} finally {
			saving.value = false;
		}
	}

	const setOn = (value) => save(() => api.approvalMode.set(Boolean(value)));
	const acknowledge = () => save(() => api.approvalMode.acknowledge());

	return { available, on, noticeSeen, saving, active, showNotice, apply, setOn, acknowledge };
});
