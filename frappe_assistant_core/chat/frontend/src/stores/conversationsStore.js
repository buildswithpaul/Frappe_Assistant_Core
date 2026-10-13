import { defineStore } from "pinia";
import { ref } from "vue";
import { api } from "@/api/client";
import { useChatStore } from "@/stores/chatStore";
import { logger } from "@/utils/logger";

const SEARCH_DEBOUNCE_MS = 300;
const SEARCH_MIN_LENGTH = 2;
const SEARCH_LIMIT = 50;

/** Sidebar search plus rename / move for a conversation. The list itself lives in chatStore. */
export const useConversationsStore = defineStore("conversations", () => {
	const searchQuery = ref("");
	const searchResults = ref([]);
	const isSearching = ref(false);
	let timer = null;
	let latest = 0;

	function setSearch(query) {
		searchQuery.value = query;
		clearTimeout(timer);
		const term = (query || "").trim();
		if (term.length < SEARCH_MIN_LENGTH) {
			searchResults.value = [];
			isSearching.value = false;
			return;
		}
		isSearching.value = true;
		timer = setTimeout(() => runSearch(term), SEARCH_DEBOUNCE_MS);
	}

	async function runSearch(term) {
		const ticket = ++latest;
		try {
			const rows = (await api.chat.getSessions({ limit: SEARCH_LIMIT, search: term })) || [];
			if (ticket === latest) searchResults.value = rows;
		} catch (err) {
			logger.error("Conversation search failed:", err);
		} finally {
			if (ticket === latest) isSearching.value = false;
		}
	}

	function clearSearch() {
		setSearch("");
	}

	function patchEverywhere(sessionId, patch) {
		useChatStore().patchSession(sessionId, patch);
		searchResults.value = searchResults.value.map((s) =>
			s.session_id === sessionId ? { ...s, ...patch } : s
		);
	}

	async function renameSession(sessionId, title) {
		const chat = useChatStore();
		const before = chat.sessions.find((s) => s.session_id === sessionId);
		const rollback = before
			? { title: before.title, preview: before.preview, title_is_custom: before.title_is_custom }
			: null;
		patchEverywhere(sessionId, { title, preview: title });
		try {
			const result = await api.chat.renameSession(sessionId, title);
			patchEverywhere(sessionId, {
				title: result.title,
				preview: result.title,
				title_is_custom: result.title_is_custom,
			});
		} catch (err) {
			if (rollback) patchEverywhere(sessionId, rollback);
			throw err;
		}
	}

	async function moveSession(sessionId, projectId) {
		const result = await api.chat.moveSessionToProject(sessionId, projectId);
		patchEverywhere(sessionId, { project: result.project, project_title: result.project_title });
	}

	return { searchQuery, searchResults, isSearching, setSearch, clearSearch, renameSession, moveSession };
});
