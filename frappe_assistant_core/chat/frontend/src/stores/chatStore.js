import { defineStore } from "pinia";
import { ref, computed } from "vue";
import { api } from "@/api/client";
import { logger } from "@/utils/logger";
import { generateBlockId, findActiveMessage, isFinalizedRow } from "./chat/utils";
import { createErrorState } from "./chat/errorState";
import { createStreamManager } from "./chat/streamManager";
import { createBlockHandlers } from "./chat/blockHandlers";
import { createSendQueue } from "./chat/sendQueue";
import { isApprovalInteraction } from "./chat/interactionRegime";
import { useComposerModesStore } from "./composerModesStore";
import { useModelStore } from "./modelStore";

// Every JSON column a message row can carry. Both parse loops below drive
// from this, so the next JSON column is added in one place — model_breakdown
// was written by the server but parsed by neither loop, arriving as an
// object live and a string on reload.
const JSON_MESSAGE_FIELDS = ["blocks", "model_breakdown", "routing"];

function parseJsonFields(msg) {
	for (const field of JSON_MESSAGE_FIELDS) {
		if (typeof msg[field] === "string") {
			try {
				msg[field] = JSON.parse(msg[field]);
			} catch {
				msg[field] = null;
			}
		}
	}
	return msg;
}

export const useChatStore = defineStore("chat", () => {
	// State
	const sessions = ref([]);
	const currentSessionId = ref(null);
	const messages = ref([]);
	const isLoading = ref(false);
	const isStreaming = ref(false);
	const hasPendingInteraction = ref(false);
	// True while a batched resume_interrupt call is in flight. Used by the
	// approval UI to disable buttons so a second click can't race the first.
	const isSubmittingInterrupts = ref(false);
	const streamingMessage = ref("");
	const { error, errorCode: errorCodeRef, setError, clearError } = createErrorState();

	// Block-based streaming state
	const activeThinkingBlockId = ref(null);
	const activeToolCallId = ref(null);

	// Socket connection state (managed by useStreaming, exposed for UI)
	const socketConnected = ref(true); // Optimistically true
	const socketError = ref(null);

	// Activity time tracking (for UI indicators like ProcessingIndicator)
	const lastActivityTime = ref(Date.now());

	// Auto mode: tracks the model selected when using model_id="auto"

	// Archived conversations
	const archivedSessions = ref([]);

	// Context addendum from continuing an archived conversation (consumed once)
	const pendingContextAddendum = ref(null);

	// Request-scoped identity to prevent duplicate message bubbles on disconnect/reconnect
	const streamRequestId = ref(null);

	// Client-side safety timer for HITL expiry (belt-and-suspenders; server is authoritative).
	// Scoped to a specific session so navigation can't flip the wrong conversation's card.
	const expiryTimerId = ref(null);
	const expiryTimerSessionId = ref(null);

	function clearExpiryTimer() {
		if (expiryTimerId.value !== null) {
			clearTimeout(expiryTimerId.value);
			expiryTimerId.value = null;
			expiryTimerSessionId.value = null;
		}
	}

	// Getters
	const currentSession = computed(() =>
		sessions.value.find((s) => s.session_id === currentSessionId.value)
	);

	const sortedSessions = computed(() => {
		return [...sessions.value].sort(
			(a, b) =>
				new Date(b.last_activity || b.modified) - new Date(a.last_activity || a.modified)
		);
	});

	// Latest assistant message's unresolved interaction, with the routing
	// regime: any pending approval forces "approval" for the whole turn.
	const pendingInteractionBlock = computed(() => {
		for (let i = messages.value.length - 1; i >= 0; i--) {
			const m = messages.value[i];
			if (m.role !== "assistant" || !Array.isArray(m.blocks)) continue;
			const pending = m.blocks.filter(
				(b) => b.type === "interaction" && b.status === "pending"
			);
			if (pending.length === 0) continue;
			const hasApproval = pending.some((b) => isApprovalInteraction(b.interactionType));
			return {
				block: pending[pending.length - 1],
				regime: hasApproval ? "approval" : "question",
			};
		}
		return null;
	});

	// Compose helpers with shared refs
	const sharedRefs = {
		isStreaming,
		hasPendingInteraction,
		messages,
		streamingMessage,
		error,
		lastActivityTime,
		socketConnected,
		socketError,
		activeThinkingBlockId,
		activeToolCallId,
		streamRequestId,
		currentSessionId,
	};

	const stream = createStreamManager({
		...sharedRefs,
		reconcile: (sessionId) => reconcileFromServer(sessionId),
	});
	const blocks = createBlockHandlers(sharedRefs);
	const sendQueue = createSendQueue({
		messages,
		currentSessionId,
		isStreaming,
		hasPendingInteraction,
		isSubmittingInterrupts,
		dispatch: (item) =>
			sendMessage(item.message, item.files, item.context, item.modelId, null, {
				skipQueue: true,
			}),
	});

	// ============================================
	// Session CRUD
	// ============================================

	async function loadSessions() {
		try {
			isLoading.value = true;
			const result = await api.chat.getSessions();
			sessions.value = result || [];
		} catch (err) {
			setError(err.message);
			logger.error("Failed to load sessions:", err);
		} finally {
			isLoading.value = false;
		}
	}

	/**
	 * Hydrate sessions from pre-fetched data (avoids a separate API call).
	 * Used by ChatView when initialize_spa already returned sessions.
	 */
	function hydrateSessions(sessionsData) {
		sessions.value = sessionsData || [];
	}

	async function loadMessages(sessionId) {
		try {
			isLoading.value = true;
			clearExpiryTimer();
			currentSessionId.value = sessionId;
			// An event for sessionId passes the stream guard the moment the id is
			// set; leaving the previous conversation's rows in place would let it
			// append to them, since block targeting is positional.
			messages.value = [];
			const result = await api.chat.getMessages(sessionId);
			if (currentSessionId.value !== sessionId) return;
			messages.value = Array.isArray(result) ? result : result?.messages || [];

			// Parse every JSON column and provide legacy fallback
			for (const msg of messages.value) {
				parseJsonFields(msg);
				// Legacy: messages without blocks get a text block from content
				if (msg.role === "assistant" && !msg.blocks && msg.content) {
					msg.blocks = [
						{ type: "text", id: generateBlockId("text"), content: msg.content },
					];
				}
			}
		} catch (err) {
			setError(err.message);
			logger.error("Failed to load messages:", err);
		} finally {
			isLoading.value = false;
		}
	}

	/**
	 * Re-read persisted blocks after a socket reconnect and merge them in,
	 * WITHOUT clobbering an actively-streaming bubble. Events emitted while
	 * the socket was down (task_updated / plan_complete / tool results) are
	 * fire-and-forget pub/sub with no server replay buffer, so the only way
	 * to recover them is to re-read what the relay already persisted.
	 */
	async function reconcileFromServer(sessionId) {
		if (!sessionId || sessionId !== currentSessionId.value) return;
		let serverMessages;
		try {
			// Loads the same recent-window as loadMessages (server caps at the
			// last 30 messages); reconcile intentionally mirrors that behavior.
			const result = await api.chat.getMessages(sessionId);
			serverMessages = Array.isArray(result) ? result : result?.messages || [];
		} catch (err) {
			logger.error("reconcileFromServer failed:", err);
			return;
		}
		// Session may have changed during the await.
		if (sessionId !== currentSessionId.value) return;

		for (const msg of serverMessages) {
			parseJsonFields(msg);
			if (msg.role === "assistant" && !msg.blocks && msg.content) {
				msg.blocks = [{ type: "text", id: generateBlockId("text"), content: msg.content }];
			}
		}

		// Capture client-only state from the pre-merge messages. Server rows
		// don't carry `truncated` (drives the Continue button on a max_tokens
		// turn), so re-apply it by message_id after the merge.
		const prevMessages = messages.value;
		const truncatedIds = new Set(
			prevMessages.filter((m) => m.truncated && m.message_id).map((m) => m.message_id)
		);

		// Preserve the live streaming bubble (not yet persisted) by re-appending
		// it after the authoritative server tail. The server persists a row for
		// the live turn on stream_start (same message_id), so drop that server
		// copy before re-appending to avoid rendering two bubbles for one turn.
		const streaming = prevMessages.filter((m) => m.isStreaming);

		// A turn that finished while the socket was down has a finished row on
		// the server and a still-spinning bubble here. Adopting the server copy
		// is the only way that answer ever appears: without it the spinner
		// survives until the activity watchdog reports a timeout for a turn
		// that actually succeeded. Blocks reach the server only at terminal
		// boundaries — mid-stream the row is the empty stream_start shell — so
		// a row with content means that turn landed.
		const finalizedById = new Map(
			serverMessages
				.filter((m) => m.message_id && isFinalizedRow(m))
				.map((m) => [m.message_id, m])
		);
		let stillLive = streaming.filter((m) => {
			const row = m.message_id && finalizedById.get(m.message_id);
			if (!row) return true;
			// A continue turn streams into the bubble of an already-finished
			// answer, so its server row holds the PRE-continue content. Adopt
			// only once the server has more than the user can already see.
			if (m._continuing) return (row.content || "").length <= (m.content || "").length;
			return false;
		});

		// Disconnecting before stream_start leaves the bubble without a
		// message_id, so it can't be matched by id. A terminal trailing row we
		// have never seen is that turn — adopt it instead of rendering both.
		const orphans = stillLive.filter((m) => !m.message_id);
		if (orphans.length === 1) {
			const knownIds = new Set(prevMessages.map((m) => m.message_id).filter(Boolean));
			const lastRow = serverMessages[serverMessages.length - 1];
			if (lastRow && isFinalizedRow(lastRow) && !knownIds.has(lastRow.message_id)) {
				stillLive = stillLive.filter((m) => m !== orphans[0]);
			}
		}

		const adopted = streaming.length - stillLive.length;
		const liveIds = new Set(stillLive.map((m) => m.message_id).filter(Boolean));
		const tail = liveIds.size
			? serverMessages.filter((m) => !liveIds.has(m.message_id))
			: serverMessages;

		// A still-generating turn is persisted as an empty shell row at
		// stream_start (content "" and no blocks). After a local timeout the
		// bubble is no longer isStreaming, so without this guard the shell
		// would replace partial content the user can already see.
		const localByMsgId = new Map(
			prevMessages.filter((m) => m.message_id).map((m) => [m.message_id, m])
		);
		const merged = tail.map((m) => {
			if (m.role !== "assistant" || isFinalizedRow(m)) return m;
			const local = localByMsgId.get(m.message_id);
			const localHasContent =
				local &&
				(local.content || (Array.isArray(local.blocks) && local.blocks.length > 0));
			return localHasContent ? local : m;
		});
		messages.value = stillLive.length ? [...merged, ...stillLive] : merged;

		if (truncatedIds.size) {
			for (const m of messages.value) {
				if (truncatedIds.has(m.message_id)) m.truncated = true;
			}
		}

		// Nothing is in flight any more, so release the send lock and disarm the
		// watchdog — otherwise it fires on a turn we just finished adopting.
		if (adopted && !stillLive.length && isStreaming.value) {
			stream.clearStreamTimeouts();
			isStreaming.value = false;
			streamingMessage.value = "";
		}
	}

	async function createSession() {
		try {
			const result = await api.chat.createSession();
			if (result && result.session_id) {
				clearExpiryTimer();
				currentSessionId.value = result.session_id;
				messages.value = [];
				await loadSessions();
				return result.session_id;
			}
		} catch (err) {
			setError(err.message);
			logger.error("Failed to create session:", err);
		}
		return null;
	}

	// ============================================
	// Message sending and streaming
	// ============================================

	async function sendMessage(
		message,
		uploadedFiles = [],
		context = null,
		modelId = null,
		systemPromptAddendum = null,
		{ skipQueue = false } = {}
	) {
		// isStreaming stays true for the whole HITL-pause window (Task 7), and
		// abortPendingInteraction() doesn't clear it either — only the eventual
		// stream finalization does. So a caller resuming after an abandoned card
		// (abort-then-send) must pass skipQueue explicitly; ambient state alone
		// can't tell that case apart from a plain queue candidate.
		if (!skipQueue && isStreaming.value) {
			sendQueue.queueMessage(message, uploadedFiles, context, modelId);
			return;
		}
		// Consume pending context from archived conversation continuation (one-time)
		if (pendingContextAddendum.value && !systemPromptAddendum) {
			systemPromptAddendum = pendingContextAddendum.value;
			pendingContextAddendum.value = null;
		}
		if (!currentSessionId.value) {
			await createSession();
			useComposerModesStore().adoptPendingSession(currentSessionId.value);
		}

		const userMessage = {
			role: "user",
			content: message,
			files: uploadedFiles.map((f) => ({ name: f.file_name, url: f.file_url })),
			timestamp: new Date().toISOString(),
		};
		messages.value.push(userMessage);

		try {
			// Extract file URLs for text extraction (all files)
			const fileUrls = uploadedFiles.filter((f) => f.file_url).map((f) => f.file_url);

			// Build vision attachments for images with base64 data
			const attachments = uploadedFiles
				.filter((f) => f.base64_data && f.type === "image")
				.map((f) => ({
					type: "image",
					format: f.format || "png",
					data: f.base64_data,
					name: f.file_name,
					file_url: f.file_url,
				}));

			isStreaming.value = true;
			streamingMessage.value = "";
			streamRequestId.value = crypto.randomUUID();

			stream.startStreamTimeout();

			const assistantMessage = {
				role: "assistant",
				content: "",
				blocks: [],
				timestamp: new Date().toISOString(),
				isStreaming: true,
				_requestId: streamRequestId.value,
			};
			messages.value.push(assistantMessage);

			const modes = useComposerModesStore().modesFor(currentSessionId.value);
			await api.chat.send(
				currentSessionId.value,
				message,
				fileUrls,
				context,
				modelId,
				systemPromptAddendum,
				attachments,
				{ web_search: modes.webSearch, thinking_enabled: modes.thinking }
			);
		} catch (err) {
			stream.clearStreamTimeouts();
			isStreaming.value = false;
			setError(err.message);
			logger.error("Failed to send message:", err);
			messages.value.pop();
		}
	}

	/**
	 * Resume a truncated (max_tokens) assistant turn. Only valid on the
	 * latest assistant message. Seeds streamingMessage with the bubble's
	 * existing content so continuation-only deltas concatenate onto the
	 * visible text; stream_complete's combined full_response then overwrites
	 * content once — no double-up.
	 */
	async function continueMessage(messageId) {
		const lastMsg = findActiveMessage(messages.value);
		if (!lastMsg || lastMsg.role !== "assistant" || lastMsg.message_id !== messageId) {
			return;
		}

		isStreaming.value = true;
		streamingMessage.value = lastMsg.content || "";
		streamRequestId.value = crypto.randomUUID();

		lastMsg.isStreaming = true;
		lastMsg.truncated = false;
		// Remember this turn is mid-continue so an error/timeout restores the
		// truncated affordance (Continue button) instead of dead-ending the
		// half-answer with an error marker.
		lastMsg._continuing = true;
		lastMsg._requestId = streamRequestId.value;

		stream.startStreamTimeout();

		try {
			// A continuation is the same turn finishing — it has to run under the
			// toggles the turn was sent with, not AR's absence defaults.
			const modes = useComposerModesStore().modesFor(currentSessionId.value);
			await api.chat.continueResponse(currentSessionId.value, messageId, {
				web_search: modes.webSearch,
				thinking_enabled: modes.thinking,
			});
		} catch (err) {
			stream.clearStreamTimeouts();
			isStreaming.value = false;
			lastMsg.isStreaming = false;
			lastMsg._continuing = false;
			// The request never streamed — leave the prior answer continuable.
			lastMsg.truncated = true;
			setError(err.message);
			logger.error("Failed to continue message:", err);
		}
	}

	function appendStreamChunk(chunk) {
		stream.resetActivityTimeout();

		// Global accumulator for legacy content (flat message.content)
		streamingMessage.value += chunk;

		const lastMsg = findActiveMessage(messages.value);
		if (lastMsg && lastMsg.role === "assistant" && lastMsg.isStreaming) {
			lastMsg.content = streamingMessage.value;

			if (lastMsg.blocks) {
				const lastBlock = lastMsg.blocks[lastMsg.blocks.length - 1];
				if (lastBlock && lastBlock.type === "text") {
					// Append to existing text block (per-segment, not global)
					lastBlock.content += chunk;
				} else {
					// Create a new text block with just this chunk
					lastMsg.blocks.push({
						type: "text",
						id: generateBlockId("text"),
						content: chunk,
					});
				}
			}
		}
	}

	function attachSources(sources) {
		// Attach (or replace) the RAG citation sources block on the streaming
		// assistant message. Idempotent — a second event for the same turn
		// replaces the existing footer rather than duplicating it.
		const lastMsg = findActiveMessage(messages.value);
		if (!lastMsg || lastMsg.role !== "assistant" || !lastMsg.isStreaming) return;
		if (!Array.isArray(lastMsg.blocks)) lastMsg.blocks = [];
		lastMsg.blocks = lastMsg.blocks.filter((b) => b.type !== "sources");
		if (!sources || sources.length === 0) return;
		lastMsg.blocks.push({
			type: "sources",
			id: generateBlockId("sources"),
			items: sources,
		});
	}

	function completeStreaming(finalContent, meta = {}) {
		stream.clearStreamTimeouts();
		isStreaming.value = false;
		const lastMsg = findActiveMessage(messages.value);
		if (lastMsg && lastMsg.role === "assistant") {
			// Store the full flat response for copy/export
			lastMsg.content = finalContent || streamingMessage.value;
			lastMsg.isStreaming = false;
			lastMsg._continuing = false;
			// Store credits metadata
			if (meta.credits_used) lastMsg.credits_used = meta.credits_used;
			if (meta.model_id) lastMsg.model_id = meta.model_id;
			if (meta.truncated) lastMsg.truncated = true;
			// The receipt: routing.credits.actual supersedes the live estimate
			// once the canonical stream_complete receipt has arrived.
			if (meta.routing) lastMsg.routing = meta.routing;
			// Replace live blocks with canonical server snapshot (if provided)
			if (meta.blocks && Array.isArray(meta.blocks)) {
				lastMsg.blocks = meta.blocks;
			}
		}
		streamingMessage.value = "";
	}

	// The resume stream's first event has arrived — closes the
	// isSubmittingInterrupts window opened in submitInterruptDecision.
	function handleStreamResumed() {
		const lastMsg = findActiveMessage(messages.value);
		if (lastMsg && lastMsg.role === "assistant") {
			lastMsg.isStreaming = true;
		}
		isStreaming.value = true;
		isSubmittingInterrupts.value = false;
	}

	/**
	 * Record a user's decision on one HITL approval / question card and, if
	 * every pending interaction block on this turn now has a decision, fire
	 * a single batched resume_interrupt call covering all of them.
	 *
	 * Rationale: when the model emits N parallel tool_use blocks that each
	 * need approval, AR streams N separate `approval_required` events and the
	 * UI renders N cards. Strands' resume contract requires a single resume
	 * call carrying responses for every pending interrupt — firing one HTTP
	 * call per card races against Strands' per-agent threading lock and also
	 * corrupts AR Message history (orphaned tool_result blocks on follow-up
	 * turns). Batching here keeps parallel tool calls fast for read-only
	 * cases while making the approval flow correct.
	 */
	async function submitInterruptDecision({ blockId, resolution, userResponse, response }) {
		if (isSubmittingInterrupts.value) return;

		const batch = blocks.recordInteractionDecision(
			blockId,
			resolution,
			userResponse,
			response
		);
		// Some cards still pending — wait for the user to decide on the rest.
		if (!batch) return;

		const lastMsg = findActiveMessage(messages.value);
		const resumeMessageId =
			lastMsg && lastMsg.role === "assistant" ? lastMsg.message_id : null;
		const sessionId = currentSessionId.value;

		isSubmittingInterrupts.value = true;
		try {
			const { call } = await import("frappe-ui");
			// A resume continues the very turn the user approved, so it must
			// carry that turn's toggles. Omitting them reaches AR as absence,
			// which AR reads as "search available" — silently re-enabling web
			// search against a pill the user has switched off.
			const modes = useComposerModesStore().modesFor(sessionId);
			const payload = {
				session_id: sessionId,
				interrupt_response: JSON.stringify(batch.responses),
				message_id: resumeMessageId,
				web_search: modes.webSearch,
				thinking_enabled: modes.thinking,
			};
			// Same reasoning for the model — except "auto" can never travel: a
			// resume skips classification, so only a concrete id is a model.
			// Test the resolved value, not isAutoModeSelected: that flag reads
			// selectedModel, while currentModelId falls back to the tenant
			// default, which AR is allowed to set to "auto" itself.
			const models = useModelStore();
			const resumeModelId = models.currentModelId;
			if (resumeModelId && resumeModelId !== "auto") {
				payload.model_id = resumeModelId;
			}
			await call("frappe_assistant_core.chat.api.chat.resume_interrupt", payload);
			// Resume stream will deliver tool_call_result + further events via
			// Socket.IO; flip the local card status now so the UI matches.
			clearExpiryTimer();
			blocks.applyInteractionDecisions(batch.blocks);
			// Deliberately NOT cleared here. This HTTP call only acknowledges
			// that the resume was queued server-side (a bounded thread pool
			// picks it up); the agent hasn't produced a single event yet.
			// applyInteractionDecisions() just cleared hasPendingInteraction,
			// so if isSubmittingInterrupts cleared too, isStreaming and
			// hasPendingInteraction would both read false for the whole
			// backend round-trip until the resume's first event arrives —
			// exactly the window the send queue would dispatch into.
			// handleStreamResumed() clears it once that first event lands;
			// handleStreamError/handleStreamAborted clear it if the resume
			// never gets that far.
		} catch (err) {
			logger.error("Failed to resume interrupt:", err);
			blocks.revertInteractionDecisions(batch.blocks);
			isSubmittingInterrupts.value = false;
		}
	}

	async function answerPendingQuestion(text) {
		const pending = pendingInteractionBlock.value;
		if (!pending || pending.regime !== "question") return false;
		await submitInterruptDecision({
			blockId: pending.block.id,
			resolution: "answered",
			userResponse: text,
			response: text,
		});
		return true;
	}

	async function abortPendingInteraction() {
		const sid = currentSessionId.value;
		if (!sid) return;
		try {
			await api.chat.cancelStream(sid, null);
		} catch (err) {
			logger.warn("cancel before send failed:", err);
		}
		hasPendingInteraction.value = false;
	}

	async function hydratePendingInterrupt(sessionId) {
		if (!sessionId) return;
		try {
			// Force GET — the endpoint is declared methods=["GET"] (idempotent
			// read). api.get hits /api/method/...?session_id=... directly, which
			// works in the standalone SPA where window.frappe is absent (the old
			// window.frappe.call path threw and left the card unhydrated).
			const data = await api.get(
				"frappe_assistant_core.chat.api.chat.get_pending_interrupt",
				{ session_id: sessionId }
			);
			// Session may have changed during the await.
			if (sessionId !== currentSessionId.value) return;
			if (!data?.pending || !data?.event) return;

			// Reuse the existing live-socket path. The idempotency guard
			// added in blockHandlers.js prevents duplicates if a card is
			// already on screen.
			blocks.handleApprovalRequired(data.event);

			// Belt-and-suspenders: schedule a local expiry flip in case the
			// server's ar_interrupt_event arrives while we're disconnected.
			// The server-side delete + emit is the primary path; this is a
			// safety net for the disconnect race.
			// Cancel any prior timer; schedule a new one scoped to this session
			// so navigation to a different conversation can't fire against the
			// wrong block list.
			clearExpiryTimer();
			const expiresAt = data.expires_at;
			if (expiresAt) {
				const ms = new Date(expiresAt).getTime() - Date.now();
				if (ms > 0 && ms < 24 * 60 * 60 * 1000) {  // sanity bounds
					const capturedSessionId = sessionId;
					expiryTimerSessionId.value = capturedSessionId;
					expiryTimerId.value = setTimeout(() => {
						expiryTimerId.value = null;
						expiryTimerSessionId.value = null;
						// Gate on current session — user may have navigated away.
						if (currentSessionId.value !== capturedSessionId) return;
						blocks.markInterruptExpired();
					}, ms);
				}
			}
		} catch (err) {
			// Hydration is best-effort. Log but never throw — the user can
			// still type a new message even if hydration fails.
			logger.warn("[chatStore] hydratePendingInterrupt failed", err);
		}
	}

	function markInterruptExpired(sessionId) {
		// Guard: an event for a session the user has navigated away from
		// shouldn't mutate the currently-visible session's blocks.
		if (sessionId && sessionId !== currentSessionId.value) return;
		clearExpiryTimer();
		blocks.markInterruptExpired();
	}

	function dismissResolvedInterrupt(sessionId) {
		if (sessionId && sessionId !== currentSessionId.value) return;
		clearExpiryTimer();
		blocks.dismissResolvedInterrupt();
	}

	function handleContextSummarized() {
		// AR only fires this for a turn that actually summarized. This guard is
		// the second layer: a socket reconnect or a second tab can replay the
		// event, and two dividers in a row say nothing the first didn't.
		const last = messages.value[messages.value.length - 1];
		if (last?.role === "divider") return;
		messages.value.push({
			role: "divider",
			content: "Earlier messages were summarized to stay within context limits",
			timestamp: new Date().toISOString(),
		});
	}

	function removeSession(sessionId) {
		sessions.value = sessions.value.filter((s) => s.session_id !== sessionId);
		if (currentSessionId.value === sessionId) {
			messages.value = [];
			clearExpiryTimer();
			currentSessionId.value =
				sessions.value.length > 0 ? sessions.value[0].session_id : null;
		}
	}

	async function loadArchivedSessions() {
		try {
			const result = await api.chat.getArchivedSessions();
			archivedSessions.value = result || [];
		} catch (err) {
			logger.error("Failed to load archived sessions:", err);
		}
	}

	function clearSessions() {
		sessions.value = [];
		messages.value = [];
		clearExpiryTimer();
		currentSessionId.value = null;
	}

	function handleStreamError(errorMessage, errorCode, payload) {
		stream.clearStreamTimeouts();
		isStreaming.value = false;
		// Safety net: a resume that fails before producing any event (e.g.
		// the background relay job throws outright) never reaches
		// handleStreamResumed, so this flag must be cleared here too.
		isSubmittingInterrupts.value = false;
		setError(errorMessage || "Stream error occurred", errorCode || null);

		// INTERRUPT_ALREADY_RESOLVED: a stale approval card was clicked
		// (commonly because Stop was pressed in another tab, or the previous
		// stream finished without the SPA hearing about it). The server's
		// state is authoritative — mark the pending cards on the last message
		// as aborted so they stop offering Approve/Reject buttons. The error
		// banner messaging from useStreaming() already explains it.
		if (errorCode === "INTERRUPT_ALREADY_RESOLVED") {
			const last = findActiveMessage(messages.value);
			if (last && Array.isArray(last.blocks)) {
				for (const b of last.blocks) {
					if (b.type === "interaction" && b.status === "pending") {
						b.status = "aborted";
						b.result = { message: "Already resolved" };
					}
				}
				last.aborted = true;
				last.isStreaming = false;
			}
			streamingMessage.value = "";
			return;
		}

		const lastMsg = findActiveMessage(messages.value);
		if (lastMsg && lastMsg.role === "assistant" && lastMsg.isStreaming) {
			lastMsg.isStreaming = false;
			if (Array.isArray(payload?.blocks) && payload.blocks.length > 0) {
				lastMsg.blocks = payload.blocks;
			}
			if (payload?.partial_response && !lastMsg.content) {
				lastMsg.content = payload.partial_response;
			}
			for (const b of lastMsg.blocks || []) {
				if (b.type === "interaction" && b.status === "pending") {
					b.status = "aborted";
				}
			}
			const hasContent = (lastMsg.blocks || []).length > 0 || lastMsg.content;
			if (lastMsg._continuing) {
				// A continue turn failed mid-stream. The prior answer is intact,
				// just still truncated — restore the Continue affordance so the
				// user can retry rather than stranding a cut-off answer.
				lastMsg._continuing = false;
				lastMsg.truncated = true;
			} else if (!hasContent) {
				// Nothing was produced — an empty errored bubble is noise.
				messages.value.pop();
			} else {
				lastMsg.errored = true;
				lastMsg.blocks = lastMsg.blocks || [];
				lastMsg.blocks.push({
					type: "text",
					id: `error-marker-${Date.now()}`,
					content: "\n\n_(Interrupted by an error)_",
					_errorMarker: true,
				});
			}
		}
		streamingMessage.value = "";
	}

	function handleStreamAborted(data) {
		// Authoritative finalization from the server. abortStream() in the
		// streamManager already did the optimistic UI work — this is the
		// safety net for cases where the abort was initiated elsewhere or
		// the relay's partial differs from what the SPA had received.
		stream.clearStreamTimeouts();
		isStreaming.value = false;
		// Safety net: same reasoning as handleStreamError — a resume
		// cancelled before it produces any event never reaches
		// handleStreamResumed.
		isSubmittingInterrupts.value = false;

		const lastMsg = findActiveMessage(messages.value);
		if (!lastMsg || lastMsg.role !== "assistant") return;

		lastMsg.isStreaming = false;
		lastMsg.aborted = true;

		// Trust the server's blocks snapshot — it includes the persisted
		// partial plus any tool results we may have missed in transit. Check
		// THIS snapshot for the marker, not the local blocks it's replacing:
		// server-side abort finalizers (cancel.py's HITL-pause path in
		// particular, which never goes through abortStream()'s optimistic
		// append) already add it via the idempotent append_abort_marker.
		// Checking the stale local array instead double-appended a second
		// marker on top of the server's.
		if (Array.isArray(data?.blocks) && data.blocks.length > 0) {
			lastMsg.blocks = data.blocks;
			const hasMarker = lastMsg.blocks.some((b) => b._abortMarker);
			if (!hasMarker) {
				lastMsg.blocks.push({
					type: "text",
					id: `abort-marker-${Date.now()}`,
					content: "\n\n_(Stopped by user)_",
					_abortMarker: true,
				});
			}
		}
		if (data?.partial_response && !lastMsg.content) {
			lastMsg.content = `${data.partial_response}\n\n_(Stopped by user)_`;
		}

		streamingMessage.value = "";
	}

	return {
		// State
		sessions,
		currentSessionId,
		messages,
		isLoading,
		isStreaming,
		streamingMessage,
		error,
		errorCode: errorCodeRef,
		activeThinkingBlockId,
		activeToolCallId,
		hasPendingInteraction,
		isSubmittingInterrupts,
		socketConnected,
		socketError,
		connectionVisible: stream.connectionVisible,
		lastActivityTime,
		// Getters
		currentSession,
		sortedSessions,
		pendingInteractionBlock,
		// Session actions
		loadSessions,
		hydrateSessions,
		loadMessages,
		reconcileFromServer,
		createSession,
		removeSession,
		clearSessions,
		archivedSessions,
		loadArchivedSessions,
		pendingContextAddendum,
		// Message actions
		sendMessage,
		queuedMessages: sendQueue.queuedMessages,
		unqueueMessage: sendQueue.unqueueMessage,
		continueMessage,
		appendStreamChunk,
		attachSources,
		completeStreaming,
		handleStreamResumed,
		clearError,
		handleStreamError,
		handleStreamAborted,
		handleContextSummarized,
		// Stream timeout and connection management (delegated)
		resetActivityTimeout: stream.resetActivityTimeout,
		handleStreamTimeout: stream.handleStreamTimeout,
		abortStream: stream.abortStream,
		handleSocketDisconnect: stream.handleSocketDisconnect,
		handleSocketError: stream.handleSocketError,
		setSocketConnected: stream.setSocketConnected,
		clearSocketError: stream.clearSocketError,
		// Block-based message actions (delegated)
		handlePlanEvent: blocks.handlePlanEvent,
		handleWorkflowCreatedEvent: blocks.handleWorkflowCreatedEvent,
		handleModelSelected: blocks.handleModelSelected,
		handleThinkingEvent: blocks.handleThinkingEvent,
		completeThinkingBlock: blocks.completeThinkingBlock,
		handleToolCallStart: blocks.handleToolCallStart,
		handleToolCallResult: blocks.handleToolCallResult,
		handleToolCancelled: blocks.handleToolCancelled,
		handleApprovalRequired: blocks.handleApprovalRequired,
		resolveInteraction: blocks.resolveInteraction,
		submitInterruptDecision,
		answerPendingQuestion,
		abortPendingInteraction,
		hydratePendingInterrupt,
		markInterruptExpired,
		dismissResolvedInterrupt,
		clearExpiryTimer,
		toggleBlockExpansion: blocks.toggleBlockExpansion,
	};
});
