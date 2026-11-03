<template>
	<div class="workspace-usage">
		<!-- Credits are the one thing here that does not depend on the analytics call, so the band
		     stays put while the rest loads, fails or reloads for a new range. -->
		<template v-if="!selectedConversation">
			<CreditsBand
				v-if="quotaInfo"
				:quota="quotaInfo"
				:members-at-limit="membersAtLimit"
				@buy-credits="openCreditPurchase"
			/>
			<p v-if="verificationMessage" class="purchase-message" role="alert">{{ verificationMessage }}</p>
		</template>

		<!-- Loading State -->
		<div v-if="loading" class="analytics-state">
			<div class="loading-spinner"></div>
			<p>{{ __("Loading usage data...") }}</p>
		</div>

		<!-- Error State -->
		<div v-else-if="error" class="analytics-state">
			<svg class="state-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
				/>
			</svg>
			<p>{{ error }}</p>
			<button class="retry-btn" @click="loadData(range)">{{ __("Retry") }}</button>
		</div>

		<!-- Drill-Down View -->
		<ConversationDrillDown
			v-else-if="selectedConversation"
			:conversation="selectedConversation"
			:messages="conversationMessages"
			:loading="messagesLoading"
			@back="clearDrillDown"
		/>

		<!-- Dashboard Content -->
		<template v-else>
			<!-- Summary Cards -->
			<SummaryCards
				:summary="summary"
				:days="range"
				mode="admin"
				:conversation-count="conversationsSummary.total_conversations"
				:credits-trend="creditsTrend"
				:requests-trend="requestsTrend"
			/>

			<!-- Daily Trend Chart -->
			<div class="section">
				<h3 class="section-title">{{ __("Daily Usage Trend") }}</h3>
				<DailyTrendChart :daily="daily" :by-source="bySource" />
			</div>

			<div class="breakdown-grid">
				<div class="section">
					<h3 class="section-title">{{ __("Usage by Source") }}</h3>
					<SourceBreakdown :sources="bySource" />
				</div>
				<div class="section">
					<h3 class="section-title">{{ __("Usage by User") }}</h3>
					<UserBreakdown
						:users="byUser"
						:total-credits="summary.credits_consumed"
					/>
				</div>
			</div>

			<!-- Usage by Model — which models are burning credits. Rendered
			     below the source/user grid so the 1-row bar chart gets the
			     full horizontal width it needs for long model IDs. -->
			<div v-if="byModel.length" class="section">
				<h3 class="section-title">{{ __("Usage by Model") }}</h3>
				<ModelBreakdown
					:models="byModel"
					:total-credits="summary.credits_consumed"
				/>
			</div>

			<!-- Conversation List -->
			<div class="section">
				<h3 class="section-title">{{ __("Conversations") }}</h3>
				<ConversationList
					:conversations="conversations"
					:is-admin="true"
					:loading="conversationsLoading"
					:has-more="conversationsPagination.has_more"
					:total-credits="conversationsSummary.total_credits"
					@select="onConversationSelect"
					@load-more="loadMoreConversations"
				/>
			</div>
		</template>

		<CreditPurchaseModal
			:is-open="showCreditPurchase"
			:gateways="availableGateways"
			:is-processing="purchasingCredits"
			@close="showCreditPurchase = false"
			@purchase="handleCreditPurchase"
		/>
	</div>
</template>

<script setup>
import { onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { storeToRefs } from "pinia";
import { api } from "@/api/client";
import { useUserStore } from "@/stores/userStore";
import SummaryCards from "@/components/analytics/SummaryCards.vue";
import DailyTrendChart from "@/components/analytics/DailyTrendChart.vue";
import SourceBreakdown from "@/components/analytics/SourceBreakdown.vue";
import UserBreakdown from "@/components/analytics/UserBreakdown.vue";
import ModelBreakdown from "@/components/analytics/ModelBreakdown.vue";
import ConversationList from "@/components/analytics/ConversationList.vue";
import ConversationDrillDown from "@/components/analytics/ConversationDrillDown.vue";
import CreditPurchaseModal from "@/components/settings/CreditPurchaseModal.vue";
import CreditsBand from "./CreditsBand.vue";
import { membersAtLimitLabel } from "./usageHelpers";
import { useAnalyticsData } from "@/composables/useAnalyticsData";
import { useBillingData } from "@/composables/useBillingData";
import { logger } from "@/utils/logger";
import { __ } from "@/utils/i18n";

const props = defineProps({
	range: { type: Number, default: 30 },
});

const emit = defineEmits(["drilling"]);

// AR clamps a page of members to 100, so one page gives a count or a lower bound ("3+").
const MEMBER_PAGE_SIZE = 100;

const route = useRoute();
const router = useRouter();
const userStore = useUserStore();
const { quotaInfo } = storeToRefs(userStore);

const {
	openCreditPurchase,
	handleCreditPurchase,
	showCreditPurchase,
	availableGateways,
	purchasingCredits,
	verificationMessage,
} = useBillingData();

const {
	loading,
	error,
	selectedRange,
	summary,
	daily,
	byUser,
	byModel,
	bySource,
	creditsTrend,
	requestsTrend,
	loadData,
	conversations,
	conversationsSummary,
	conversationsPagination,
	conversationsLoading,
	loadConversations,
	loadMoreConversations,
	selectedConversation,
	conversationMessages,
	messagesLoading,
	loadMessageCredits,
	clearDrillDown,
} = useAnalyticsData();

const membersAtLimit = ref(null);

function onConversationSelect(conversationId) {
	loadMessageCredits(conversationId);
}

watch(
	() => props.range,
	(days) => {
		selectedRange.value = days;
		loadData(days);
		loadConversations(days);
	},
	{ immediate: true },
);

watch(selectedConversation, (conversation) => emit("drilling", Boolean(conversation)));

async function loadMembersAtLimit() {
	try {
		const result = await api.users.list("Active", MEMBER_PAGE_SIZE, 0);
		membersAtLimit.value = membersAtLimitLabel(result);
	} catch (err) {
		logger.error("Failed to load members at limit:", err);
		membersAtLimit.value = null;
	}
}

// A link such as /analytics?buy=1 opens the purchase modal. Drop the param
// first so a refresh does not reopen it.
async function openPurchaseFromLink() {
	if (!route.query.buy) return;
	await router.replace({ query: { ...route.query, buy: undefined } });
	await openCreditPurchase();
}

onMounted(() => {
	// Boot may have seeded quotaInfo, but it can be stale; always refresh.
	userStore.loadQuota();
	// Members never reach this page, but do not spend the call if one does.
	if (userStore.isAdmin) loadMembersAtLimit();
	openPurchaseFromLink();
});
</script>

<style scoped>
.section {
	margin-bottom: 1.5rem;
}

.section-title {
	font-size: 0.9rem;
	font-weight: 600;
	color: var(--ql-text);
	margin-bottom: 0.75rem;
}

.breakdown-grid {
	display: grid;
	grid-template-columns: repeat(auto-fit, minmax(min(320px, 100%), 1fr));
	gap: 1.5rem;
	margin-bottom: 1.5rem;
}

/* A grid child sizes to its content by default, so a wide row would push the page sideways. */
.breakdown-grid > .section {
	min-width: 0;
}

/* States */
.analytics-state {
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	padding: 4rem 2rem;
	text-align: center;
	color: var(--ql-text-secondary);
}

.analytics-state p {
	font-size: 0.875rem;
	color: var(--ql-text-muted);
}

.state-icon {
	width: 48px;
	height: 48px;
	color: var(--ql-text-muted);
	margin-bottom: 1rem;
}

.loading-spinner {
	width: 32px;
	height: 32px;
	border: 3px solid var(--ql-border);
	border-top-color: var(--ql-accent);
	border-radius: 50%;
	animation: spin 0.8s linear infinite;
	margin-bottom: 1rem;
}

@keyframes spin {
	to {
		transform: rotate(360deg);
	}
}

.retry-btn {
	margin-top: 1rem;
	padding: 0.5rem 1rem;
	font-size: 0.875rem;
	color: var(--ql-accent);
	background: transparent;
	border: 1px solid var(--ql-accent);
	border-radius: 0.375rem;
	cursor: pointer;
}

.retry-btn:hover {
	background: var(--ql-accent-soft);
}

.purchase-message {
	margin: -0.75rem 0 1.5rem;
	font-size: 0.8rem;
	color: var(--ql-danger);
}
</style>
