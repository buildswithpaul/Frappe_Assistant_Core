import { api } from "@/api/client";
import { logger } from "@/utils/logger";
import { useConversationsStore } from "@/stores/conversationsStore";

/**
 * Session lifecycle handlers for ChatView — select, delete, continue-archived.
 *
 * `handleNewChat` is passed in (not owned here) because the parent has its own
 * reactive dependencies on createSession + routing and we deliberately avoid
 * re-entrant coupling flagged by D5b. This composable only wraps the three safe
 * per-session actions that have no such recursion.
 *
 * @param {object} deps - { chatStore, route, router, handleNewChat }
 */
export function useChatSessionActions({ chatStore, route, router, handleNewChat }) {
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
			useConversationsStore().dropResult(sessionId);
			// Only the chat on screen needs a replacement; archiving any other
			// one (from a project page or home) keeps the user where they are.
			if (route.params.sessionId !== sessionId) return;
			const nextSession = chatStore.sortedSessions[0];
			if (nextSession) {
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
				chatStore.setPendingProject(result.new_session_id, result.project);
				await chatStore.loadSessions();
				router.push(`/chat/${result.new_session_id}`);
			}
		} catch (err) {
			logger.error("Failed to continue archived session:", err);
		}
	}

	return { handleSessionSelect, handleDeleteSession, handleContinueArchived };
}
