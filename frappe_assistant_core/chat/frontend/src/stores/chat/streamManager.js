/**
 * Stream timeout and connection management.
 *
 * Factory function that receives shared reactive refs from the store
 * and returns timeout/connection methods.
 */

// Stream timeout configuration
// No absolute cap — deep analysis sessions can legitimately run for 10+ minutes
// with the agent actively calling tools. The activity timeout is the sole
// liveness check: if no SSE event arrives within this window, the stream is dead.
//
// Bumped from 120s → 180s after a one-off freeze during heavy analytics
// (matplotlib/pandas cold-start). The AR-side heartbeat fires every ~10s, so
// 180s tolerates ~18 missed heartbeats before declaring the stream dead.
const STREAM_ACTIVITY_TIMEOUT_MS = 180000; // 180 seconds - reset on each event (including heartbeats)

import { ref } from "vue";
import { api } from "@/api/client";
import { logger } from "@/utils/logger";
import { findActiveMessage } from "./utils";

export function createStreamManager({
	isStreaming,
	messages,
	streamingMessage,
	error,
	lastActivityTime,
	socketConnected,
	socketError,
	currentSessionId,
	reconcile,
}) {
	let activityTimeoutId = null;

	// Debounced visibility — only show UI after sustained disconnect (3s)
	const connectionVisible = ref(false);
	let connectionDebounceId = null;

	// A timed-out turn gets no server finalizer event, so any block still in
	// a "running" visual state would keep its spinner forever. Reconcile on
	// the next reconnect replaces these with the persisted truth.
	function finalizeRunningBlocks(msg) {
		if (!Array.isArray(msg.blocks)) return;
		for (const block of msg.blocks) {
			if (block.type === "tool_call" && block.status === "running") {
				block.status = "error";
				block.result = { message: "Timed out waiting for a response." };
				block.endTime = new Date().toISOString();
			} else if (block.type === "thinking" && block.isStreaming) {
				block.isStreaming = false;
				block.endTime = new Date().toISOString();
			}
		}
	}

	function handleStreamTimeout(message) {
		logger.error("Stream timeout:", message);
		clearStreamTimeouts();

		isStreaming.value = false;
		error.value = message;

		const lastMsg = findActiveMessage(messages.value);
		if (lastMsg && lastMsg.role === "assistant" && lastMsg.isStreaming) {
			lastMsg.isStreaming = false;
			finalizeRunningBlocks(lastMsg);
			if (lastMsg._continuing) {
				// A continue turn timed out. The prior answer is intact, just
				// still truncated — restore the Continue affordance so the user
				// can retry rather than stranding a cut-off answer with an error.
				lastMsg._continuing = false;
				lastMsg.truncated = true;
			} else {
				lastMsg.error = true;
				if (!lastMsg.content && (!lastMsg.blocks || lastMsg.blocks.length === 0)) {
					lastMsg.content = message;
				}
			}
		}

		streamingMessage.value = "";
	}

	function startStreamTimeout() {
		clearStreamTimeouts();
		resetActivityTimeout();
	}

	function resetActivityTimeout() {
		if (activityTimeoutId) {
			clearTimeout(activityTimeoutId);
		}

		lastActivityTime.value = Date.now();

		if (error.value && error.value.includes("No response received")) {
			error.value = null;
		}

		if (!isStreaming.value) {
			return;
		}

		activityTimeoutId = setTimeout(async () => {
			if (!isStreaming.value) return;
			// Silence here means "no events reached us", which is not the same
			// as "the turn failed" — the finalizer is fire-and-forget too. Ask
			// the server before blaming the connection; reconcile adopts a
			// finished turn and clears isStreaming.
			if (reconcile && currentSessionId?.value) {
				try {
					await reconcile(currentSessionId.value);
				} catch (err) {
					logger.warn("Pre-timeout reconcile failed:", err);
				}
				if (!isStreaming.value) return;
			}
			handleStreamTimeout(
				"No response received for 3 minutes. The connection may have been lost."
			);
		}, STREAM_ACTIVITY_TIMEOUT_MS);
	}

	function clearStreamTimeouts() {
		if (activityTimeoutId) {
			clearTimeout(activityTimeoutId);
			activityTimeoutId = null;
		}
	}

	function handleSocketDisconnect(reason) {
		socketConnected.value = false;
		logger.warn("Socket disconnected:", reason);

		// Only show UI indicator after 3s of sustained disconnect
		if (connectionDebounceId) clearTimeout(connectionDebounceId);
		connectionDebounceId = setTimeout(() => {
			if (!socketConnected.value) {
				connectionVisible.value = true;
			}
		}, 3000);

		// Do NOT immediately timeout the stream on socket disconnect.
		// The stream may still be running on the server (e.g., during long tool execution).
		// If we reconnect, events will resume into the same message (via streamRequestId).
		// The activity timeout (180s) is the canonical authority on whether the stream is dead.
	}

	function handleSocketError(errorMsg) {
		socketConnected.value = false;
		socketError.value = errorMsg;
		logger.error("Socket error:", errorMsg);

		// Let the activity timeout handle liveness detection, not socket errors.
		// Socket errors during long tool execution are transient — reconnection handles recovery.
	}

	function setSocketConnected(connected) {
		socketConnected.value = connected;
		if (connected) {
			socketError.value = null;
			connectionVisible.value = false;
			if (connectionDebounceId) {
				clearTimeout(connectionDebounceId);
				connectionDebounceId = null;
			}
		}
	}

	function clearSocketError() {
		socketError.value = null;
		connectionVisible.value = false;
	}

	async function abortStream() {
		if (!isStreaming.value) return;

		logger.debug("User aborted stream");

		// Optimistic UI: flip local state immediately so the Stop button
		// disappears and the input enables. The authoritative finalization
		// (persisted aborted=1 + final blocks) arrives via the
		// ``stream_aborted`` socket event the relay emits below.
		clearStreamTimeouts();
		isStreaming.value = false;
		error.value = null;

		const lastMsg = findActiveMessage(messages.value);
		const isAbortableAssistant =
			lastMsg && lastMsg.role === "assistant" && lastMsg.isStreaming;
		if (isAbortableAssistant) {
			lastMsg.isStreaming = false;
			lastMsg.aborted = true;
			// Keep the partial response as-is. Append the marker as a final
			// text block so it renders alongside whatever the model already
			// produced. If nothing was produced at all, show only the marker.
			const hasAnyContent =
				lastMsg.content || (Array.isArray(lastMsg.blocks) && lastMsg.blocks.length > 0);
			if (hasAnyContent) {
				if (Array.isArray(lastMsg.blocks)) {
					lastMsg.blocks.push({
						type: "text",
						id: `abort-marker-${Date.now()}`,
						content: "\n\n_(Stopped by user)_",
						_abortMarker: true,
					});
				}
				lastMsg.content = `${lastMsg.content || ""}\n\n_(Stopped by user)_`;
			} else {
				lastMsg.content = "_(Stopped by user)_";
				if (Array.isArray(lastMsg.blocks)) {
					lastMsg.blocks.push({
						type: "text",
						id: `abort-marker-${Date.now()}`,
						content: "_(Stopped by user)_",
						_abortMarker: true,
					});
				}
			}
		}

		streamingMessage.value = "";

		// Tell the server to actually stop processing. Without this the
		// agent keeps running, tools keep firing, and tokens keep getting
		// billed even though we've stopped showing the events.
		const sessionId = currentSessionId?.value;
		if (sessionId) {
			try {
				await api.chat.cancelStream(sessionId, lastMsg?._requestId || null);
			} catch (err) {
				// Don't block the UI on a failed cancel. The activity
				// timeout (180s) is still the canonical liveness check.
				logger.warn("cancel_stream call failed:", err);
			}
		}
	}

	return {
		connectionVisible,
		startStreamTimeout,
		resetActivityTimeout,
		clearStreamTimeouts,
		handleStreamTimeout,
		handleSocketDisconnect,
		handleSocketError,
		setSocketConnected,
		clearSocketError,
		abortStream,
	};
}
