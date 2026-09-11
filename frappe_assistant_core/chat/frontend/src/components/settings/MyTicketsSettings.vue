<template>
	<div class="my-tickets-settings">
		<header class="settings-header">
			<h2>Support</h2>
		</header>

		<div class="tabs">
			<button
				type="button"
				:class="['tab-btn', { active: activeTab === 'tickets' }]"
				@click="activeTab = 'tickets'"
			>
				Tickets
			</button>
			<button
				type="button"
				:class="['tab-btn', { active: activeTab === 'feedback' }]"
				@click="onOpenFeedbackTab"
			>
				Feedback
			</button>
		</div>

		<template v-if="activeTab === 'tickets'">
			<TicketDetail
				v-if="selectedId"
				:ticket="thread || { messages: [] }"
				:ticket-id="selectedId"
				:submitting="submitting"
				:refreshing="threadLoading"
				@back="onBack"
				@reply="onReply"
				@refresh="onRefresh"
				@navigate="router.push($event)"
			/>
			<TicketList
				v-else
				:tickets="tickets"
				:loading="loading"
				@select="onSelect"
				@filter="onFilter"
			/>
		</template>

		<FeedbackHistoryList
			v-else
			:items="feedback"
			:loading="feedbackLoading"
			:error="feedbackError"
			@open-ticket="onOpenTicketFromFeedback"
			@retry="loadFeedback"
		/>
	</div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { api } from "@/api/client";
import { useToast } from "@/composables/useToast";
import TicketList from "./tickets/TicketList.vue";
import TicketDetail from "./tickets/TicketDetail.vue";
import FeedbackHistoryList from "./tickets/FeedbackHistoryList.vue";

const route = useRoute();
const router = useRouter();
const { showError } = useToast();

const tickets = ref([]);
const loading = ref(false);
const selectedId = ref(null);
const thread = ref(null);
const threadLoading = ref(false);
const submitting = ref(false);
const statusFilter = ref("");

const activeTab = ref("tickets");
const feedback = ref([]);
const feedbackLoading = ref(false);
const feedbackLoaded = ref(false);
const feedbackError = ref(null);

async function loadList() {
	loading.value = true;
	try {
		tickets.value = await api.support.listMyTickets(statusFilter.value || null);
	} catch (e) {
		showError("Could not load your tickets. Please try again.");
	} finally {
		loading.value = false;
	}
}

async function loadThread(id) {
	threadLoading.value = true;
	try {
		thread.value = await api.support.getTicketThread(id);
	} catch (e) {
		showError("Could not load this ticket. Please try again.");
	} finally {
		threadLoading.value = false;
	}
}

function onFilter(status) {
	statusFilter.value = status;
	loadList();
}

function onSelect(id) {
	selectedId.value = id;
	loadThread(id);
}

function onBack() {
	selectedId.value = null;
	thread.value = null;
}

function onRefresh() {
	if (selectedId.value) loadThread(selectedId.value);
}

async function onReply(payload) {
	const text = typeof payload === "string" ? payload : payload.text;
	const attachmentIds = typeof payload === "string" ? [] : payload.attachmentIds;
	submitting.value = true;
	try {
		await api.support.replyToTicket(selectedId.value, text, attachmentIds);
		await loadThread(selectedId.value);
	} catch (e) {
		showError("Could not send your reply. Please try again.");
	} finally {
		submitting.value = false;
	}
}

async function loadFeedback() {
	feedbackLoading.value = true;
	feedbackError.value = null;
	try {
		feedback.value = await api.support.listMyFeedback();
		feedbackLoaded.value = true;
	} catch (e) {
		feedbackError.value = "Could not load your feedback. Please try again.";
		showError("Could not load your feedback. Please try again.");
	} finally {
		feedbackLoading.value = false;
	}
}

function onOpenFeedbackTab() {
	activeTab.value = "feedback";
	if (!feedbackLoaded.value && !feedbackLoading.value) {
		loadFeedback();
	}
}

function onOpenTicketFromFeedback(ticketId) {
	activeTab.value = "tickets";
	onSelect(ticketId);
}

onMounted(() => {
	loadList();
	const deepLinkId = route.query.ticket;
	if (deepLinkId) {
		selectedId.value = deepLinkId;
		loadThread(deepLinkId);
	}
});
</script>

<style scoped>
.my-tickets-settings {
	padding: 1rem;
	display: flex;
	flex-direction: column;
	gap: 1rem;
}

.settings-header h2 {
	margin: 0;
	font-size: 1.15rem;
	font-weight: 600;
	color: var(--ql-text, #1e293b);
}

.tabs {
	display: flex;
	gap: 0.125rem;
	border-bottom: 1px solid var(--ql-border, #e2e8f0);
}

.tab-btn {
	padding: 0.625rem 1rem;
	font-size: 0.8125rem;
	font-weight: 500;
	color: var(--ql-text-secondary, #64748b);
	background: none;
	border: none;
	border-bottom: 2px solid transparent;
	cursor: pointer;
	transition: all 0.15s ease;
	margin-bottom: -1px;
}

.tab-btn:hover {
	color: var(--ql-text, #1e293b);
}

.tab-btn.active {
	color: var(--ql-accent, #2563eb);
	border-bottom: 2px solid var(--ql-accent, #2563eb);
}
</style>
