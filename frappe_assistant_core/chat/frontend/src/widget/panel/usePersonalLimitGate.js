import { computed, onMounted, onUnmounted } from "vue";
import { useUserStore } from "@/stores/userStore";
import { personalLimitBlock } from "@/utils/personalLimit";

/**
 * The user's own monthly limit, as the widget's composer must honour it.
 *
 * AR refuses a member at their limit before it looks at the team's credits, so a send would only
 * come back as user_limit_reached. The widget boots without FAC Chat's initialize, so it reads the
 * status itself, and again whenever Desk regains focus: the "Change limit" link opens Settings in
 * another tab, and the hold lifts once the user comes back with a new limit.
 */
export function usePersonalLimitGate(win = window) {
	const userStore = useUserStore();
	const block = computed(() => personalLimitBlock(userStore.myCreditStatus));
	const recheck = () => userStore.loadMyCreditStatus();
	const onVisible = () => {
		if (win.document.visibilityState === "visible") recheck();
	};

	onMounted(() => {
		recheck();
		win.addEventListener("focus", recheck);
		win.document.addEventListener("visibilitychange", onVisible);
	});
	onUnmounted(() => {
		win.removeEventListener("focus", recheck);
		win.document.removeEventListener("visibilitychange", onVisible);
	});

	return { block, recheck };
}
