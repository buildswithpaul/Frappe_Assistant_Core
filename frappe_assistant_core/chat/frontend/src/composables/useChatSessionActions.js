import { api } from "@/api/client";
import { logger } from "@/utils/logger";

/**
 * Session lifecycle handlers for ChatView — select, delete, continue-archived.
 *
 * `handleNewChat` is passed in (not owned here) because the parent has its own
 * reactive dependencies on createSession + routing and we deliberately avoid
 * re-entrant coupling flagged by D5b. This composable only wraps the three safe
 * per-session actions that have no such recursion.
 *
 * @param {object} deps - { chatStore, router, handleNewChat }
 */
export function useChatSessionActions({ chatStore, router, handleNewChat }) {
	async function handleSessionSelect(sessionId) {
		router.push(`/chat/${sessionId}`);
		// Drawer dismisses via NavigationSidebar's route watcher. Do not
		// collapse the desktop rail here — on phones that hid Chat / labels
		// and the recent-chats list inside the off-canvas drawer.
	}

	async function handleDeleteSession(sessionId) {
		try {
			await api.chat.deleteSession(sessionId);
			chatStore.removeSession(sessionId);
			if (chatStore.currentSessionId && chatStore.currentSessionId !== sessionId) {
				router.push(`/chat/${chatStore.currentSessionId}`);
			} else if (chatStore.sessions.length > 0) {
				const nextSession = chatStore.sortedSessions[0];
				router.push(`/chat/${nextSession.session_id}`);
			} else {
				await handleNewChat();
			}
		} catch (err) {
			logger.error("Failed to delete session:", err);
		}
	}

	async function handleContinueArchived(oldSessionId) {
		try {
			const result = await api.chat.continueArchivedSession(oldSessionId);
			if (result && result.success) {
				chatStore.currentSessionId = result.new_session_id;
				chatStore.messages = [];
				chatStore.pendingContextAddendum = result.context_addendum;
				await chatStore.loadSessions();
				router.push(`/chat/${result.new_session_id}`);
			}
		} catch (err) {
			logger.error("Failed to continue archived session:", err);
		}
	}

	return { handleSessionSelect, handleDeleteSession, handleContinueArchived };
}
