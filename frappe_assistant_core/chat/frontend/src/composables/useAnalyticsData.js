import { ref, computed } from "vue";
import { api } from "@/api/client";

export function useAnalyticsData() {
	// --- Aggregate analytics state ---
	const loading = ref(true);
	const error = ref(null);
	const data = ref(null);
	const selectedRange = ref(30);
	const isAdmin = ref(false);

	const summary = computed(
		() =>
			data.value?.summary || {
				tokens_input: 0,
				tokens_output: 0,
				tokens_actual: 0,
				request_count: 0,
				active_users: 0,
				credits_consumed: 0,
			}
	);
	const daily = computed(() => data.value?.daily || []);
	const byUser = computed(() => data.value?.by_user || []);
	const byModel = computed(() => data.value?.by_model || []);
	const bySource = computed(() => data.value?.by_source || []);
	const period = computed(() => data.value?.period || {});

	// --- Period deltas ---------------------------------------------------
	// Split the current daily series in half and compare second-half vs
	// first-half to surface a "trend within period" signal without a second
	// API call. This answers "is usage accelerating or decelerating?" — a
	// true period-over-period (previous 30d vs current 30d) would need a
	// backend tweak to accept a date offset.
	//
	// Noise guard: when the prior half is tiny (new user, just onboarded,
	// brief dev testing spike at the end) the percentage explodes — "24
	// credits vs 5,122" renders as +21,000% which is technically true and
	// completely useless. We fall back to a "new" badge when the prior
	// baseline is below a minimum threshold, passed in by the caller.
	//
	// Returns an object with:
	//   recent    – sum over the second half
	//   prior     – sum over the first half
	//   percent   – signed integer percentage change, null when we chose
	//               not to compute one (no data, or prior below threshold)
	//   direction – 'up' | 'down' | 'flat' | 'new'
	function trendSplit(values, minBaseline = 0) {
		if (!values.length) return { recent: 0, prior: 0, percent: null, direction: "flat" };
		const mid = Math.floor(values.length / 2);
		const prior = values.slice(0, mid).reduce((a, b) => a + b, 0);
		const recent = values.slice(mid).reduce((a, b) => a + b, 0);
		if (prior === 0 && recent === 0) {
			return { recent: 0, prior: 0, percent: null, direction: "flat" };
		}
		// Prior is effectively zero (absolute) or tiny compared to recent —
		// percentage change is mathematically huge but meaningless. Render
		// as "new" so the user sees signal without a misleading number.
		if (prior < minBaseline) {
			return { recent, prior, percent: null, direction: "new" };
		}
		const pct = Math.round(((recent - prior) / prior) * 100);
		const direction = pct > 2 ? "up" : pct < -2 ? "down" : "flat";
		return { recent, prior, percent: pct, direction };
	}

	// Thresholds tuned to everyday FACO usage. 100 credits ≈ one non-trivial
	// chat turn with tools, so a prior half below that is genuinely "no
	// meaningful baseline". 10 requests is one light session.
	const CREDITS_BASELINE_MIN = 100;
	const REQUESTS_BASELINE_MIN = 10;

	const creditsTrend = computed(() =>
		trendSplit(
			daily.value.map((d) => d.credits_consumed || 0),
			CREDITS_BASELINE_MIN
		)
	);
	const requestsTrend = computed(() =>
		trendSplit(
			daily.value.map((d) => d.request_count || 0),
			REQUESTS_BASELINE_MIN
		)
	);

	async function loadData(days = null) {
		const range = days ?? selectedRange.value;
		loading.value = true;
		error.value = null;
		try {
			const result = await api.analytics.getData(range);
			if (result?.error) {
				error.value = result.error;
			} else {
				data.value = result;
				isAdmin.value = !!result.is_admin;
			}
		} catch (e) {
			error.value = e.message || "Failed to load analytics data";
		} finally {
			loading.value = false;
		}
	}

	function setRange(days) {
		selectedRange.value = days;
		loadData(days);
		loadConversations(days);
	}

	// --- Conversation list state ---
	const conversations = ref([]);
	const conversationsSummary = ref({
		total_conversations: 0,
		total_credits: 0,
		total_messages: 0,
	});
	const conversationsPagination = ref({ total: 0, limit: 50, offset: 0, has_more: false });
	const conversationsLoading = ref(false);

	async function loadConversations(days = null, limit = 50, offset = 0) {
		const range = days ?? selectedRange.value;
		conversationsLoading.value = true;
		try {
			const result = await api.analytics.getConversations(range, limit, offset);
			if (result?.error) {
				error.value = result.error;
				return;
			}
			if (offset === 0) {
				conversations.value = result.conversations || [];
			} else {
				conversations.value = [...conversations.value, ...(result.conversations || [])];
			}
			conversationsSummary.value = result.summary || conversationsSummary.value;
			conversationsPagination.value = result.pagination || conversationsPagination.value;
		} catch (e) {
			error.value = e.message || "Failed to load conversations";
		} finally {
			conversationsLoading.value = false;
		}
	}

	function loadMoreConversations() {
		const p = conversationsPagination.value;
		if (p.has_more) {
			loadConversations(selectedRange.value, p.limit, p.offset + p.limit);
		}
	}

	// --- Conversation drill-down state ---
	const selectedConversation = ref(null);
	const conversationMessages = ref([]);
	const messagesLoading = ref(false);

	async function loadMessageCredits(conversationId) {
		messagesLoading.value = true;
		try {
			const result = await api.analytics.getMessageCredits(conversationId);
			if (result?.error) {
				error.value = result.error;
				return;
			}
			selectedConversation.value = {
				conversation_id: result.conversation_id,
				title: result.title,
				user_id: result.user_id,
				created_at: result.created_at,
				total_credits: result.total_credits,
				total_messages: result.total_messages,
			};
			conversationMessages.value = result.messages || [];
		} catch (e) {
			error.value = e.message || "Failed to load message credits";
		} finally {
			messagesLoading.value = false;
		}
	}

	function clearDrillDown() {
		selectedConversation.value = null;
		conversationMessages.value = [];
	}

	return {
		// Aggregate
		loading,
		error,
		data,
		selectedRange,
		isAdmin,
		summary,
		daily,
		byUser,
		byModel,
		bySource,
		period,
		creditsTrend,
		requestsTrend,
		loadData,
		setRange,
		// Conversations
		conversations,
		conversationsSummary,
		conversationsPagination,
		conversationsLoading,
		loadConversations,
		loadMoreConversations,
		// Drill-down
		selectedConversation,
		conversationMessages,
		messagesLoading,
		loadMessageCredits,
		clearDrillDown,
	};
}
