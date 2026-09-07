<template>
	<div class="app-layout">
		<!-- Navigation Sidebar -->
		<NavigationSidebar
			:collapsed="sidebarCollapsed"
			@open-settings="router.push('/settings')"
			@toggle-sidebar="sidebarCollapsed = !sidebarCollapsed"
		/>

		<!-- Main Content Area -->
		<main class="main-content">
			<!-- Top Bar -->
			<header class="top-bar">
				<div class="top-bar-content">
					<div class="top-bar-left">
						<button
							@click="onHamburger(() => (sidebarCollapsed = !sidebarCollapsed))"
							class="sidebar-toggle-btn"
							aria-label="Toggle navigation"
						>
							<svg
								class="w-5 h-5"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
							>
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									stroke-width="2"
									d="M4 6h16M4 12h16M4 18h16"
								/>
							</svg>
						</button>
						<div class="page-title">Usage</div>
					</div>
					<div class="top-bar-actions" v-if="!selectedConversation">
						<div class="range-selector">
							<button
								v-for="r in ranges"
								:key="r"
								class="range-btn"
								:class="{ active: selectedRange === r }"
								@click="setRange(r)"
							>
								{{ r }}D
							</button>
						</div>
					</div>
				</div>
			</header>

			<!-- Content -->
			<div class="analytics-content">
				<!-- Loading State -->
				<div v-if="loading" class="analytics-state">
					<div class="loading-spinner"></div>
					<p>Loading usage data...</p>
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
					<button class="retry-btn" @click="loadData()">Retry</button>
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
						:quota="quotaInfo"
						mode="admin"
						:conversation-count="conversationsSummary.total_conversations"
						:credits-trend="creditsTrend"
						:requests-trend="requestsTrend"
					/>

					<!-- Daily Trend Chart -->
					<div class="section">
						<h3 class="section-title">Daily Usage Trend</h3>
						<DailyTrendChart :daily="daily" :by-source="bySource" />
					</div>

					<div class="breakdown-grid">
						<div class="section">
							<h3 class="section-title">Usage by Source</h3>
							<SourceBreakdown :sources="bySource" />
						</div>
						<div class="section">
							<h3 class="section-title">Usage by User</h3>
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
						<h3 class="section-title">Usage by Model</h3>
						<ModelBreakdown
							:models="byModel"
							:total-credits="summary.credits_consumed"
						/>
					</div>

					<!-- Conversation List -->
					<div class="section">
						<h3 class="section-title">Conversations</h3>
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
			</div>
		</main>
	</div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { useRouter } from "vue-router";
import { storeToRefs } from "pinia";
import { useUserStore } from "@/stores/userStore";
import NavigationSidebar from "@/components/layout/NavigationSidebar.vue";
import SummaryCards from "@/components/analytics/SummaryCards.vue";
import DailyTrendChart from "@/components/analytics/DailyTrendChart.vue";
import SourceBreakdown from "@/components/analytics/SourceBreakdown.vue";
import UserBreakdown from "@/components/analytics/UserBreakdown.vue";
import ModelBreakdown from "@/components/analytics/ModelBreakdown.vue";
import ConversationList from "@/components/analytics/ConversationList.vue";
import ConversationDrillDown from "@/components/analytics/ConversationDrillDown.vue";
import { useAnalyticsData } from "@/composables/useAnalyticsData";
import { useNavToggle } from "@/composables/useNavToggle";

const router = useRouter();
const userStore = useUserStore();
const { quotaInfo } = storeToRefs(userStore);

const sidebarCollapsed = ref(false);
const { onHamburger } = useNavToggle();

const ranges = [7, 30, 90];

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
	setRange,
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

function onConversationSelect(conversationId) {
	loadMessageCredits(conversationId);
}

onMounted(() => {
	loadData();
	loadConversations();
	if (!quotaInfo.value) {
		userStore.loadQuota();
	}
});
</script>

<style scoped>
.app-layout {
	display: flex;
	height: 100%;
	min-height: 0;
	overflow: hidden;
}

.main-content {
	flex: 1;
	display: flex;
	flex-direction: column;
	overflow: hidden;
	min-height: 0;
}

.top-bar {
	height: var(--ql-topbar-height, 56px);
	border-bottom: 1px solid var(--ql-border);
	background: var(--ql-surface);
	padding: 0 1.5rem;
	display: flex;
	align-items: center;
	flex-shrink: 0;
}

.top-bar-content {
	display: flex;
	justify-content: space-between;
	align-items: center;
	width: 100%;
}

.top-bar-left {
	display: flex;
	align-items: center;
	gap: 1rem;
}

.sidebar-toggle-btn {
	flex-shrink: 0;
	padding: 0.5rem;
	color: var(--ql-text-muted);
	background: transparent;
	border: none;
	border-radius: 0.5rem;
	cursor: pointer;
	transition: all 0.15s ease;
}

.sidebar-toggle-btn:hover {
	background-color: var(--ql-subtle);
	color: var(--ql-text);
}

.page-title {
	font-size: 1.125rem;
	font-weight: 700;
	color: var(--ql-text);
}

.top-bar-actions {
	display: flex;
	gap: 0.5rem;
}

/* Date Range Selector */
.range-selector {
	display: flex;
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	overflow: hidden;
}

.range-btn {
	padding: 0.375rem 0.75rem;
	font-size: 0.8rem;
	font-weight: 600;
	color: var(--ql-text-secondary);
	background: transparent;
	border: none;
	cursor: pointer;
	transition: all 0.15s ease;
}

.range-btn:hover {
	color: var(--ql-text);
	background: var(--ql-subtle);
}

.range-btn.active {
	color: white;
	background: var(--ql-accent);
}

/* Analytics Content */
.analytics-content {
	flex: 1;
	overflow-y: auto;
	padding: 1.5rem;
}

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
	grid-template-columns: 1fr 1fr;
	gap: 1.5rem;
	margin-bottom: 1.5rem;
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

/* Responsive */
@media (max-width: 768px) {
	.analytics-content {
		padding: 1rem;
	}

	.breakdown-grid {
		grid-template-columns: 1fr;
	}
}
</style>
