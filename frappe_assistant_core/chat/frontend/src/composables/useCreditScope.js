import { computed } from "vue";
import { useUserStore } from "@/stores/userStore";

/**
 * The credit allowance that actually governs the current user.
 *
 * A member whose admin capped them is blocked by that cap, never by the team
 * pool, so every surface that quotes a credit figure has to resolve the same
 * way — a cap of 0 means "uncapped" and falls back to the shared pool. A team
 * pool of -1 means unlimited; callers decide how to render that.
 *
 * @returns {import("vue").ComputedRef<{isPersonal: boolean, total: number, used: number}>}
 */
export function useCreditScope() {
	const userStore = useUserStore();

	return computed(() => {
		const mine = userStore.myCreditStatus;
		const limit = mine?.has_individual_limit ? Number(mine.monthly_credit_limit) || 0 : 0;
		if (limit > 0) {
			return {
				isPersonal: true,
				total: limit,
				used: Number(mine.credits_used_this_month) || 0,
			};
		}

		const quota = userStore.quotaInfo;
		return {
			isPersonal: false,
			total: Number(quota?.quota_total) || 0,
			used: Number(quota?.quota_used) || 0,
		};
	});
}
