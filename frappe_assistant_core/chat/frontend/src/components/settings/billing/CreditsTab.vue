<template>
	<div class="credits-tab">
		<PersonalLimitNotice
			v-if="limitBlock"
			:used="limitBlock.used"
			:limit="limitBlock.limit"
			@open-users="router.push({ name: 'settings-users' })"
		/>
		<PrepaidCreditsCard
			:credit-balance="creditBalance"
			:transactions="transactions"
			:next-expiry="nextExpiry"
			@buy-credits="$emit('buy-credits')"
		/>
		<UsageChart />
	</div>
</template>

<script setup>
import { computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import { useUserStore } from "@/stores/userStore";
import { personalLimitBlock } from "@/utils/personalLimit";
import PersonalLimitNotice from "./PersonalLimitNotice.vue";
import PrepaidCreditsCard from "./PrepaidCreditsCard.vue";
import UsageChart from "./UsageChart.vue";

defineProps({
	creditBalance: { type: Number, default: null },
	transactions: { type: Array, default: () => [] },
	nextExpiry: { type: Object, default: null },
});
defineEmits(["buy-credits"]);

const router = useRouter();
const userStore = useUserStore();

// The Desk widget sends a blocked user straight here (Buy credits), so the tab itself says when a
// personal limit, not the team's credits, is what stops them (#34571), before they open the buy flow.
const limitBlock = computed(() => personalLimitBlock(userStore.myCreditStatus));
onMounted(() => userStore.loadMyCreditStatus());
</script>
