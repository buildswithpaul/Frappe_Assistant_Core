import { ref } from "vue";
import { api } from "@/api/client";
import { logger } from "@/utils/logger";

/**
 * Give back one seat nobody is sitting in.
 *
 * Kept out of UsersSettings.vue, which is already past the component size
 * the project allows. The backend picks the seat — it refuses when every
 * seat is occupied and clamps at the plan minimum — so there is nothing to
 * choose here beyond confirming.
 *
 * The limit is always re-read afterwards rather than trusting the returned
 * count: the response reports one subscription field, and the banner needs
 * all three seat numbers to agree with the server.
 */
export function useSeatRelease({ refreshLimit, actionError, successMessage, clearMessageAfterDelay }) {
	const releasing = ref(false);

	async function releaseSeat() {
		releasing.value = true;
		actionError.value = "";
		successMessage.value = "";
		try {
			const result = await api.billing.removeUserSeat();
			if (result?.success) {
				successMessage.value =
					"Seat released. Your next bill reflects the lower count.";
				clearMessageAfterDelay("success");
			} else {
				actionError.value = result?.error || "Could not release a seat";
				clearMessageAfterDelay("error");
			}
		} catch (e) {
			logger.error("Seat release failed", e);
			actionError.value = e.message || "Could not release a seat";
			clearMessageAfterDelay("error");
		} finally {
			releasing.value = false;
			await refreshLimit();
		}
	}

	return { releasing, releaseSeat };
}
