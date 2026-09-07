/**
 * Streaming composable for FACO
 * Subscribes to frappe.realtime events for message streaming
 *
 * If frappe.realtime is not available (Vue SPA), we initialize our own
 * socket.io connection to receive the events.
 *
 * Includes connection state management for reliability:
 * - Tracks socket connection status
 * - Handles disconnection during streaming
 * - Reports connection errors to chatStore for UI feedback
 */
import { onMounted, onUnmounted, ref, watch } from "vue";
import { useChatStore } from "@/stores/chatStore";
import { useUserStore } from "@/stores/userStore";
import { logger } from "@/utils/logger";
import { writeHandoff } from "@/utils/sessionHandoff";
import { findActiveMessage } from "@/stores/chat/utils";
import { io } from "socket.io-client";

// Singleton socket connection for the SPA
let spaSocket = null;
let spaSocketInitialized = false;

/** Extract a cookie value by name (used for Frappe session ID). */
function getCookieValue(name) {
	const match = document.cookie.match(new RegExp("(?:^|; )" + name + "=([^;]*)"));
	return match ? decodeURIComponent(match[1]) : null;
}

/**
 * Same-origin navigation guard. Matches the server-side check in
 * browser_tools/navigate_to.py and the widget's widget_browser_tools.js.
 * Rejects javascript:/data:/protocol-relative/cross-origin URLs.
 */
function isSafeUrl(url) {
	if (!url) return false;
	if (url.startsWith("/") && !url.startsWith("//")) return true;
	try {
		const parsed = new URL(url, window.location.origin);
		return (
			(parsed.protocol === "http:" || parsed.protocol === "https:") &&
			parsed.origin === window.location.origin
		);
	} catch {
		return false;
	}
}

function initializeSpaSocket(chatStore) {
	if (spaSocketInitialized) return spaSocket;

	const host = window.location.hostname;
	const protocol = window.location.protocol;

	// Determine if we're in a local development environment
	const isLocalDev = host === "localhost" || host === "127.0.0.1";

	// Get site name - try multiple sources
	// For local dev, window.site_name is typically set by Frappe
	// For production, it's usually in frappe.boot.sitename
	let siteName = window.frappe?.boot?.sitename || window.site_name;

	// Fallback for site name
	if (!siteName) {
		if (isLocalDev) {
			// For local development, use common default
			siteName = "frappe.assistant";
		} else {
			// For Frappe Cloud/production, site name is typically the subdomain
			siteName = host.split(".")[0];
		}
	}

	// Build socket URL based on environment
	let socketUrl;
	if (isLocalDev) {
		// Local development: Use explicit port (socket server runs on separate port)
		const port = window.frappe?.boot?.socketio_port || window.socketio_port || 9000;
		socketUrl = `${protocol}//${host}:${port}/${siteName}`;
	} else {
		// Production (Frappe Cloud): Socket goes through nginx proxy on standard port
		// No explicit port needed - nginx routes /socket.io/* to internal socketio server
		socketUrl = `${protocol}//${host}/${siteName}`;
	}

	logger.debug("Connecting to socket:", socketUrl);

	spaSocket = io(socketUrl, {
		withCredentials: true,
		reconnection: true,
		reconnectionAttempts: 20,
		reconnectionDelay: 1000,
		reconnectionDelayMax: 5000,
		timeout: 60000,
		transports: ["websocket", "polling"],
		// Explicit path ensures nginx can route correctly in production
		path: "/socket.io",
	});

	// Connection established
	// Room joining is handled automatically by Frappe's socketio authentication middleware.
	// The sid HttpOnly cookie is sent during WebSocket handshake (withCredentials: true),
	// and frappe_handlers() in realtime/handlers.js does socket.join(user_room(socket.user)).
	spaSocket.on("connect", createSpaConnectHandler(chatStore, spaSocket));

	// A reconnect can land after missed notifications (outage cleared, new
	// promo, etc.) — refetch on every connect. Dynamic import keeps the
	// notification store out of this composable's static dependency graph.
	spaSocket.on("connect", () => {
		import("@/stores/notificationStore").then(({ useNotificationStore }) =>
			useNotificationStore().refresh()
		);
	});

	// Connection error
	spaSocket.on("connect_error", (err) => {
		logger.error("Socket connection error:", err.message);
		chatStore.handleSocketError(err.message);
	});

	// Disconnected
	spaSocket.on("disconnect", (reason) => {
		logger.warn("Socket disconnected:", reason);
		chatStore.handleSocketDisconnect(reason);
	});

	// Reconnection lifecycle. In socket.io-client v4 these are Manager-level
	// events — socket.on("reconnect") never fires (it would listen for a
	// server-emitted custom event of that name), so they must be registered
	// on spaSocket.io.
	spaSocket.io.on("reconnect_attempt", (attemptNumber) => {
		logger.debug("Reconnection attempt:", attemptNumber);
	});

	spaSocket.io.on("reconnect", (attemptNumber) => {
		logger.debug("Reconnected after", attemptNumber, "attempts");
	});

	spaSocket.io.on("reconnect_failed", () => {
		logger.error("Reconnection failed after max attempts");
		chatStore.handleSocketError("Unable to reconnect. Please refresh the page.");
	});

	document.addEventListener(
		"visibilitychange",
		createVisibilityHandler(chatStore, () => spaSocket)
	);

	spaSocketInitialized = true;
	return spaSocket;
}

/**
 * Re-join the session room and re-read the state that events may have carried
 * while this client wasn't listening. Server-side room membership is
 * per-connection and stream events are fire-and-forget with no replay buffer,
 * so re-reading what the relay persisted is the only recovery path.
 *
 * Exported for tests.
 */
export function recoverSession(chatStore, socket) {
	const sid = chatStore.currentSessionId;
	if (!sid) return;
	socket.emit("task_subscribe", sid);
	chatStore.hydratePendingInterrupt(sid);
	chatStore.reconcileFromServer(sid);
}

/**
 * Build the tab-foreground handler. Safari suspends timers and sockets in
 * background tabs; if automatic reconnection exhausts its attempts there,
 * nothing revives the socket when the user returns, so a dead socket is
 * nudged and recovery rides the "connect" handler.
 *
 * A throttled tab can also keep a socket that still reports connected while
 * having missed events. "connect" never fires for that one, so an in-flight
 * turn has to recover here instead — otherwise the answer that landed while
 * the tab was hidden is only found by the 3-minute watchdog.
 *
 * Exported for tests.
 */
export function createVisibilityHandler(chatStore, getSocket) {
	return () => {
		if (document.visibilityState !== "visible") return;
		const socket = getSocket();
		if (!socket) return;
		if (!socket.connected) {
			socket.connect();
			return;
		}
		if (chatStore.isStreaming) recoverSession(chatStore, socket);
	};
}

/**
 * Build the SPA socket "connect" handler. "connect" fires on the first
 * connection AND on every re-connection (automatic or via the retry button),
 * so post-reconnect recovery lives here. The first connection skips recovery
 * (initial hydration is useChatViewInit's job) unless a stream is already in
 * flight.
 *
 * Exported for tests.
 */
export function createSpaConnectHandler(chatStore, socket) {
	let hasConnectedBefore = false;
	return () => {
		logger.debug("Socket connected");
		chatStore.setSocketConnected(true);
		// The first connection normally skips recovery — unless a turn is
		// already in flight, meaning the send raced a socket that had never
		// connected and events may already have been missed.
		const needsRecovery = hasConnectedBefore || chatStore.isStreaming;
		hasConnectedBefore = true;
		if (!needsRecovery) return;
		recoverSession(chatStore, socket);
	};
}

export function useStreaming() {
	const chatStore = useChatStore();
	const userStore = useUserStore();
	const usingFrappeRealtime = ref(false);

	/**
	 * Handler for AR-emitted lifecycle events ("ar_interrupt_event").
	 * Distinct channel from `faco_message_stream` so AR doesn't have to
	 * know FAC's wire format. Payload: `{kind, session_id}`.
	 *
	 * Future-proof: ignore unknown `kind` values silently.
	 */
	function handleArInterruptEvent(data) {
		if (!data?.session_id) return;
		switch (data.kind) {
			case "expired":
				chatStore.markInterruptExpired(data.session_id);
				break;
			case "resolved":
				chatStore.dismissResolvedInterrupt(data.session_id);
				break;
			default:
				// Unknown kind — ignore silently to stay forward-compatible.
				break;
		}
	}

	function handleStreamEvent(data) {
		// Ignore events for other sessions
		if (data.session_id !== chatStore.currentSessionId) {
			return;
		}

		// Reset activity timeout on any stream event (indicates connection is alive)
		chatStore.resetActivityTimeout();

		switch (data.event) {
			case "stream_start":
				// App-level zero-retention flag rides on stream_start (capabilities
				// can't carry a per-app flag). Surface it read-only in PrivacySettings.
				if ("zero_retention" in data) {
					userStore.setZeroRetention(data.zero_retention);
				}
				// Store message_id from AR for linking with historical events
				if (data.message_id || data.model_id) {
					const lastMsg = findActiveMessage(chatStore.messages);
					if (lastMsg && lastMsg.role === "assistant") {
						if (data.message_id) {
							lastMsg.message_id = data.message_id;
							// Re-activate streaming on the existing message when resuming
							// from a HITL interrupt (approval/question). Without this,
							// subsequent stream_chunk events would create a new bubble;
							// it also closes the send-queue's resume-in-flight gate.
							if (data.resumed) {
								chatStore.handleStreamResumed();
							}
						}
						// Pinned up front so a turn that aborts or errors before
						// stream_complete still shows which model answered it.
						if (data.model_id) {
							lastMsg.model_id = data.model_id;
						}
					}
				}
				break;
			case "model_selected":
				// Auto mode resolved a concrete model (only when model_id="auto" was used)
				// Data: { mode, complexity, task_type, selected: "model-id", tier, shortlist_size }
				chatStore.handleModelFallback(data);
				break;
			case "stream_chunk":
				chatStore.appendStreamChunk(data.chunk);
				break;
			case "sources":
				chatStore.attachSources(data.sources || []);
				break;
			case "stream_complete":
				chatStore.completeThinkingBlock();
				userStore.applyQuotaFromStream(data);
				if (data.truncated) {
					// Response was truncated due to output token limits.
					// Show the partial response with a truncation notice.
					chatStore.completeStreaming(data.full_response, {
						credits_used: data.credits_used,
						model_id: data.model_id,
						truncated: true,
						blocks: data.blocks,
					});
				} else if (data.interrupted) {
					// HITL interrupt: stream paused, waiting for user approval.
					// Stop the streaming indicator but keep the message "alive"
					// so the approval card stays interactive.
					chatStore.completeStreaming(data.full_response, {
						credits_used: data.credits_used,
						model_id: data.model_id,
						interrupted: true,
						blocks: data.blocks,
					});
				} else {
					chatStore.completeStreaming(data.full_response, {
						credits_used: data.credits_used,
						model_id: data.model_id,
						blocks: data.blocks,
					});
				}
				break;
			case "context_summarized":
				chatStore.handleContextSummarized();
				break;
			case "stream_error":
				chatStore.handleStreamError(data.error, data.error_code, data);
				break;
			case "stream_cancel_requested":
				// Optimistic ack from cancel_stream endpoint. The local
				// abortStream() already flipped UI state; this event exists
				// for cases where Stop was issued from another device or
				// tab. No-op if we initiated it locally.
				break;
			case "stream_aborted":
				// Authoritative: relay closed the AR connection and persisted
				// aborted=1 on the FACO Message. Make sure UI agrees with the
				// server's view (covers the multi-device case + the rare race
				// where stream_complete fires concurrent with cancel).
				chatStore.completeThinkingBlock();
				chatStore.handleStreamAborted?.(data);
				break;

			// ============================================
			// Reasoning & Tool Execution Events
			// ============================================
			case "thinking":
				chatStore.resetActivityTimeout();
				chatStore.handleThinkingEvent(data);
				break;
			case "thinking_complete":
				chatStore.resetActivityTimeout();
				chatStore.completeThinkingBlock();
				break;
			case "tool_call_start":
				chatStore.resetActivityTimeout();
				chatStore.handleToolCallStart(data);

				// Handle browser navigation from SPA — server returns success
				// immediately (fire-and-forget), SPA does the actual navigation
				if (data.tool_name === "browser_navigate_to") {
					// Store session for widget to pick up on the target page.
					// Same-tab navigation only — sessionStorage scopes the hand-off
					// to this tab so other tabs don't inherit the session id, and
					// the stamped owner keeps it out of a different login.
					writeHandoff(
						"faco_widget_session",
						chatStore.currentSessionId,
						userStore.user
					);

					const url = data.input?.url;
					if (url) {
						setTimeout(() => {
							let targetUrl = url;
							if (url.startsWith("/")) {
								targetUrl = url;
							} else if (
								url.startsWith("app/") ||
								url.startsWith("Form/") ||
								url.startsWith("List/")
							) {
								targetUrl = "/" + url;
							} else if (!url.startsWith("http")) {
								targetUrl = "/app/" + url.toLowerCase().replace(/ /g, "-");
							}
							// SECURITY: Defense in depth — refuse non-same-origin targets
							// even if the server dispatched them.
							if (!isSafeUrl(targetUrl)) {
								logger.warn(
									"Streaming: refusing unsafe navigation target:",
									targetUrl
								);
								return;
							}
							window.location.href = targetUrl;
						}, 500);
					}
				}
				break;
			case "tool_call_result":
				chatStore.resetActivityTimeout();
				chatStore.handleToolCallResult(data);
				break;
			case "tool_cancelled":
				chatStore.resetActivityTimeout();
				chatStore.handleToolCancelled(data);
				break;

			case "approval_required":
				chatStore.resetActivityTimeout();
				chatStore.handleApprovalRequired(data);
				break;

			case "plan_created":
			case "task_updated":
			case "plan_complete":
				chatStore.resetActivityTimeout();
				chatStore.handlePlanEvent(data);
				break;

			case "workflow_created":
				chatStore.resetActivityTimeout();
				chatStore.handleWorkflowCreatedEvent(data);
				break;

			default:
				// Unknown event type - ignore silently
				break;
		}
	}

	// Subscribe/unsubscribe the active socket to a session-scoped room. The
	// server emits faco_message_stream into Frappe's `task_progress:<id>`
	// room (see _emit_socket_event in api/chat.py); joining via task_subscribe
	// is what scopes events to this tab only.
	function subscribeSession(sessionId) {
		if (!sessionId) return;
		if (usingFrappeRealtime.value && window.frappe?.realtime?.task_subscribe) {
			window.frappe.realtime.task_subscribe(sessionId);
		} else if (spaSocket) {
			spaSocket.emit("task_subscribe", sessionId);
		}
	}

	function unsubscribeSession(sessionId) {
		if (!sessionId) return;
		if (usingFrappeRealtime.value && window.frappe?.realtime?.task_unsubscribe) {
			window.frappe.realtime.task_unsubscribe(sessionId);
		} else if (spaSocket) {
			spaSocket.emit("task_unsubscribe", sessionId);
		}
	}

	let stopWatch = null;
	let frappeRealtimeConnectHandler = null;

	onMounted(() => {
		// Try Frappe's realtime first (works on normal Frappe pages)
		if (window.frappe?.realtime) {
			frappe.realtime.on("faco_message_stream", handleStreamEvent);
			frappe.realtime.on("ar_interrupt_event", handleArInterruptEvent);
			usingFrappeRealtime.value = true;
			// Frappe's realtime handles its own connection state
			chatStore.setSocketConnected(true);

			// Frappe's realtime auto-reconnects but does NOT re-emit
			// task_subscribe for our session room and gives no hook the SPA
			// socket's "reconnect" listener provides. Mirror the SPA path by
			// re-subscribing + hydrating on the "connect" event.
			frappeRealtimeConnectHandler = () => {
				const sid = chatStore.currentSessionId;
				if (sid) {
					subscribeSession(sid);
					chatStore.hydratePendingInterrupt(sid);
					chatStore.reconcileFromServer(sid);
				}
			};
			if (typeof frappe.realtime.on === "function") {
				frappe.realtime.on("connect", frappeRealtimeConnectHandler);
			}
		} else {
			// Fallback: Initialize our own socket.io connection for the Vue SPA
			const socket = initializeSpaSocket(chatStore);
			socket.on("faco_message_stream", handleStreamEvent);
			socket.on("ar_interrupt_event", handleArInterruptEvent);
		}

		// Subscribe to the current session room and track changes.
		// Post-reconnect recovery for the SPA socket lives in
		// createSpaConnectHandler (registered once on the singleton).
		subscribeSession(chatStore.currentSessionId);
		stopWatch = watch(
			() => chatStore.currentSessionId,
			(newId, oldId) => {
				if (oldId) unsubscribeSession(oldId);
				if (newId) subscribeSession(newId);
			}
		);
	});

	onUnmounted(() => {
		if (stopWatch) stopWatch();
		unsubscribeSession(chatStore.currentSessionId);

		if (usingFrappeRealtime.value && window.frappe?.realtime) {
			frappe.realtime.off("faco_message_stream", handleStreamEvent);
			frappe.realtime.off("ar_interrupt_event", handleArInterruptEvent);
			if (frappeRealtimeConnectHandler && typeof frappe.realtime.off === "function") {
				frappe.realtime.off("connect", frappeRealtimeConnectHandler);
			}
		} else if (spaSocket) {
			spaSocket.off("faco_message_stream", handleStreamEvent);
			spaSocket.off("ar_interrupt_event", handleArInterruptEvent);
		}
	});
}

/**
 * Force a fresh socket reconnection attempt.
 * Used by the retry button when all automatic reconnection attempts have failed.
 */
export function reconnectSocket() {
	if (spaSocket) {
		spaSocket.connect();
	}
}

/**
 * Get the SPA socket singleton for other composables that need Socket.IO events.
 * Returns the existing socket if already initialized, or null if not yet ready.
 * Callers should use this after useStreaming() has been mounted.
 */
export function getSpaSocket() {
	return spaSocket;
}
