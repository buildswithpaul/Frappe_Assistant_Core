// Frappe Assistant Copilot - Powered by FAC Cloud - Widget Streaming Module
// Handles Socket.IO streaming, processing indicators, and tool indicators for the FACO widget

/**
 * Widget Streaming Module
 * Responsible for real-time streaming, processing indicators, and tool indicators
 */
window.FACOWidgetStreaming = {
	// Timeout configuration (matching Vue frontend)
	STREAM_TIMEOUT_MS: 5 * 60 * 1000, // 5 minutes max stream time
	ACTIVITY_TIMEOUT_MS: 120 * 1000, // 120 seconds inactivity timeout (includes heartbeats)

	// Timeout tracking
	_streamTimeoutId: null,
	_activityTimeoutId: null,

	// Connection recovery state
	_recoveryBound: false,
	_hasConnected: false,
	_visibilityHandler: null,
	_reconcileInFlight: false,

	// Processing indicator state (per-widget, stored on widget instance)
	PROCESSING_TIPS: [
		"Tip: Use Shift+Enter for multi-line messages",
		"Tip: You can attach files for context-aware assistance",
		"Tip: Click the expand button to open in a larger window",
		'"The best way to predict the future is to create it." — Alan Kay',
		'"Simplicity is the ultimate sophistication." — Leonardo da Vinci',
		'"First, solve the problem. Then, write the code." — John Johnson',
		'"Any fool can write code that a computer can understand. Good programmers write code that humans can understand." — Martin Fowler',
	],

	/**
	 * Subscribe the socket to the session's realtime room.
	 * Frappe's `task_subscribe` joins `task_progress:<id>`; the server emits
	 * faco_message_stream into that same room (see _emit_socket_event in
	 * api/chat.py). This is what scopes events to this tab only.
	 */
	subscribe_session(session_id) {
		if (session_id && frappe.realtime && frappe.realtime.task_subscribe) {
			frappe.realtime.task_subscribe(session_id);
		}
	},

	unsubscribe_session(session_id) {
		if (session_id && frappe.realtime && frappe.realtime.task_unsubscribe) {
			frappe.realtime.task_unsubscribe(session_id);
		}
	},

	/**
	 * Run `fn` once frappe.realtime.socket exists. Both `realtime.on()` and
	 * `realtime.emit()` are silent no-ops while the socket is undefined, and
	 * the socket can lag script load — binding blind loses every event for the
	 * page. Mirrors the poll in widget_browser_tools.js (10s ceiling).
	 */
	_when_socket_ready(fn, attempt) {
		if (typeof frappe !== "undefined" && frappe.realtime && frappe.realtime.socket) {
			fn();
			return;
		}
		const next = (attempt || 0) + 1;
		if (next > 100) {
			FACOLogger.warn("frappe.realtime.socket unavailable — streaming disabled");
			return;
		}
		setTimeout(() => this._when_socket_ready(fn, next), 100);
	},

	/**
	 * Set up Socket.IO listeners for streaming responses
	 * @param {Object} widget - Widget instance reference
	 */
	setup_socket_listeners(widget) {
		this._when_socket_ready(() => this._bind_socket_listeners(widget));
	},

	_bind_socket_listeners(widget) {
		this.subscribe_session(widget.session_id);
		this.setup_connection_recovery(widget);
		frappe.realtime.on("faco_message_stream", (data) => {
			// Only process events for this session (defence-in-depth — the
			// task_progress room scoping is the primary filter)
			if (data.session_id !== widget.session_id) {
				return;
			}

			// Reset activity timeout on any event
			this.reset_activity_timeout(widget);

			switch (data.event) {
				case "stream_start":
					if (data.message_id) {
						widget.current_message_id = data.message_id;
						this.note_seen_message(widget, data.message_id);
					}
					widget._activePlan = null;
					if (data.resumed) {
						// Reuse the existing streaming message from the interrupted stream
						// so the resumed response continues in the same bubble.
						const $existing = widget.$widget.find(".faco-message-streaming");
						if ($existing.length) {
							// Element already exists and has the streaming class — just
							// make sure the text container is visible and add cursor back
							const $content = $existing.find(".faco-message-text");
							$content.show();
							if (!$content.find(".faco-streaming-cursor").length) {
								$content.append('<span class="faco-streaming-cursor">▋</span>');
							}
						} else {
							// No existing element (e.g. page was refreshed) — create new
							this.add_streaming_message(widget);
						}
					}
					break;

				case "model_selected":
					if (data.selected) {
						FACOLogger.debug("Auto mode selected model:", data.selected);
					}
					// The live receipt for the turn in flight; the chip is drawn
					// when the message lands. widget.js hardcodes model_id "auto",
					// so this fires on every widget turn.
					if (data.routing) {
						widget._pending_routing = data.routing;
					}
					break;

				case "stream_chunk":
					this.update_streaming_message(widget, data.chunk);
					break;

				case "thinking":
					this.show_thinking_indicator(widget, data.content);
					break;

				case "thinking_complete":
					this.hide_thinking_indicator(widget);
					break;

				case "tool_call_start":
					this.show_tool_indicator(widget, data.tool_name, data.tool_id);
					break;

				case "tool_call_result":
				case "tool_result":
					this.hide_tool_indicator(widget, data.tool_id);
					break;

				case "tool_cancelled":
					this.hide_tool_indicator(widget, data.tool_id, true);
					break;

				case "plan_created":
				case "task_updated":
					this.render_plan(widget, data.plan);
					break;

				case "plan_complete":
					this.collapse_plan(widget, data.plan);
					break;

				case "approval_required":
					this.show_interaction_card(widget, data);
					break;

				case "stream_complete":
					this.clear_timeouts();
					if (data.interrupted) {
						// HITL interrupt — stream paused, waiting for user response.
						// Don't finalize; keep the interaction card visible. The
						// watchdog is re-armed when the resume is submitted.
						widget._isStreaming = false;
						this.stop_processing_indicator(widget);
						widget.$widget.find(".faco-thinking-indicator").remove();
						widget.$widget.find(".faco-tool-indicator").remove();
						break;
					}
					// Stream finished cleanly — drop any stale pending-interrupt
					// state so the next turn starts fresh.
					widget._pendingInterrupts = [];
					widget._isSubmittingInterrupts = false;
					this.clear_approval_attention(widget);
					this.finalize_streaming_message(
						widget,
						data.full_response,
						data.tokens_used,
						data.quota_remaining
					);
					break;

				case "stream_error":
					this.clear_timeouts();
					this.handle_stream_error(widget, data);
					break;
			}
		});

		// AR-emitted lifecycle events ("ar_interrupt_event") — distinct channel
		// from `faco_message_stream` so AR doesn't have to know FAC's wire format.
		// Payload: {kind: "expired"|"resolved", session_id: str}.
		frappe.realtime.on("ar_interrupt_event", (data) => {
			if (!data || !data.session_id) return;
			if (data.session_id !== widget.session_id) return; // wrong session — ignore
			if (data.kind === "expired") {
				this.mark_interaction_expired(widget);
			} else if (data.kind === "resolved") {
				this.dismiss_resolved_interaction(widget);
			}
			// Unknown kinds: ignore silently for forward-compat.
		});
	},

	/**
	 * Start stream timeouts (called when sending a message)
	 * @param {Object} widget - Widget instance
	 */
	start_stream_timeout(widget) {
		this.clear_timeouts();
		widget._isStreaming = true;

		// Max stream time (5 minutes)
		this._streamTimeoutId = setTimeout(() => {
			this.handle_stream_timeout(widget, __("Request exceeded maximum time (5 minutes)"));
		}, this.STREAM_TIMEOUT_MS);

		// Activity timeout (60 seconds without events)
		this._activityTimeoutId = setTimeout(() => {
			this.handle_stream_timeout(widget, __("No response received. Please try again."), {
				allowRetry: true,
			});
		}, this.ACTIVITY_TIMEOUT_MS);
	},

	/**
	 * Reset activity timeout (called on each received event)
	 * @param {Object} widget - Widget instance
	 */
	reset_activity_timeout(widget) {
		if (this._activityTimeoutId) {
			clearTimeout(this._activityTimeoutId);
			this._activityTimeoutId = setTimeout(() => {
				this.handle_stream_timeout(
					widget,
					__("Connection appears to have stalled. Please try again."),
					{ allowRetry: true }
				);
			}, this.ACTIVITY_TIMEOUT_MS);
		}
	},

	/**
	 * Clear all timeouts
	 */
	clear_timeouts() {
		if (this._streamTimeoutId) {
			clearTimeout(this._streamTimeoutId);
			this._streamTimeoutId = null;
		}
		if (this._activityTimeoutId) {
			clearTimeout(this._activityTimeoutId);
			this._activityTimeoutId = null;
		}
	},

	/**
	 * Handle stream timeout.
	 *
	 * Silence is not proof of failure: a dropped socket loses every remaining
	 * event for the turn (room membership is per-connection and emits are
	 * fire-and-forget), while the relay keeps running and persists the answer.
	 * So check the server before declaring failure, and give a socket that is
	 * actually down one more window to come back.
	 *
	 * @param {Object} widget - Widget instance
	 * @param {string} message - Timeout message
	 * @param {Object} [options] - {allowRetry: bool} — grant the grace window
	 */
	async handle_stream_timeout(widget, message, options) {
		this.clear_timeouts();

		if (await this.reconcile_from_server(widget)) {
			return;
		}

		if (options && options.allowRetry && !this._socket_connected()) {
			this._nudge_socket();
			this.update_processing_status(widget, __("Connection lost — reconnecting..."));
			this._activityTimeoutId = setTimeout(() => {
				this.handle_stream_timeout(widget, message);
			}, this.ACTIVITY_TIMEOUT_MS);
			return;
		}

		this._fail_turn(widget, message);
	},

	/**
	 * Close out the in-flight turn with a notice instead of an answer.
	 * @param {string} [icon] - Leading glyph; defaults to the timeout clock.
	 */
	_fail_turn(widget, message, icon) {
		widget._isStreaming = false;
		this.stop_processing_indicator(widget);

		widget.$widget.find(".faco-message-streaming").remove();
		widget.$widget.find(".faco-thinking-indicator").remove();
		widget.$widget.find(".faco-tool-indicator").remove();

		const prefix = icon === undefined ? "⏱️" : icon;
		widget.add_message_to_ui("assistant", prefix ? `${prefix} ${message}` : message, true);
		this._release_composer(widget);
		this.clear_approval_attention(widget);
	},

	// --- Connection Recovery ---

	/**
	 * Wire post-reconnect recovery.
	 *
	 * Frappe's realtime client auto-reconnects but never re-emits
	 * `task_subscribe` (see socketio_client.js), so the fresh connection is no
	 * longer in `task_progress:<session_id>` — every remaining event for the
	 * turn in flight is lost. It also caps at `reconnectionAttempts: 3`, after
	 * which nothing revives the socket on its own. "connect" fires on the
	 * first connection AND on every reconnection, which is the only hook the
	 * client offers; the SPA recovers the same way (useStreaming.js).
	 */
	setup_connection_recovery(widget) {
		if (this._recoveryBound) return;
		// frappe.realtime.on() is a silent no-op while the socket is undefined.
		if (typeof frappe === "undefined" || !frappe.realtime || !frappe.realtime.socket) {
			return;
		}

		this._hasConnected = !!frappe.realtime.socket.connected;

		frappe.realtime.on("connect", () => this._on_socket_connect(widget));
		frappe.realtime.on("disconnect", () => this._on_socket_disconnect(widget));

		this._visibilityHandler = () => this._on_tab_visible(widget);
		document.addEventListener("visibilitychange", this._visibilityHandler);

		this._recoveryBound = true;
	},

	_on_socket_connect(widget) {
		const first = !this._hasConnected;
		this._hasConnected = true;
		// The first connection is init's job — unless a turn is already in
		// flight, meaning the send raced a socket that had never connected.
		if (first && !widget._isStreaming) return;
		this.recover_session(widget);
	},

	_on_socket_disconnect(widget) {
		if (widget && widget._isStreaming) {
			this.update_processing_status(widget, __("Connection lost — reconnecting..."));
		}
	},

	/**
	 * A backgrounded tab can have its socket suspended and its reconnection
	 * attempts exhausted, leaving a dead socket that nothing revives when the
	 * user returns. A throttled tab can also keep a socket that still reports
	 * connected while having missed events — "connect" never fires for that
	 * one, so an in-flight turn has to recover here instead.
	 */
	_on_tab_visible(widget) {
		if (document.visibilityState !== "visible") return;
		if (!this._socket_connected()) {
			this._nudge_socket();
			return; // recovery rides the "connect" handler
		}
		if (widget && widget._isStreaming) this.recover_session(widget);
	},

	/**
	 * Re-join the session room and re-read what events may have carried while
	 * this client wasn't listening.
	 */
	recover_session(widget) {
		if (!widget || !widget.session_id) return;
		this.subscribe_session(widget.session_id);
		this.hydrate_pending_interrupt(widget);
		if (widget._isStreaming) {
			this.update_processing_status(widget, __("Processing your request..."));
			this.reconcile_from_server(widget);
		}
	},

	_socket_connected() {
		const socket = typeof frappe !== "undefined" && frappe.realtime && frappe.realtime.socket;
		return !!(socket && socket.connected);
	},

	_nudge_socket() {
		const socket = typeof frappe !== "undefined" && frappe.realtime && frappe.realtime.socket;
		if (socket && !socket.connected && typeof socket.connect === "function") {
			socket.connect();
		}
	},

	/**
	 * Remember an assistant turn we have already rendered, so a recovery read
	 * can tell a new answer from one that is already on screen.
	 */
	note_seen_message(widget, messageId) {
		if (!widget || !messageId) return;
		if (!widget._seenMessageIds) widget._seenMessageIds = new Set();
		widget._seenMessageIds.add(messageId);
	},

	/**
	 * Whether a persisted assistant row represents a finished turn. Streaming
	 * persists an empty shell row at stream_start and backfills it on
	 * completion, so "has content, blocks, or a terminal flag" is what
	 * separates a turn that landed from one still in flight. Mirrors the SPA's
	 * isFinalizedRow (stores/chat/utils.js), except `blocks` arrives here as
	 * the raw JSON string the server stored.
	 */
	_is_finalized_row(row) {
		if (!row || row.role !== "assistant") return false;
		if (row.errored || row.aborted) return true;
		if (row.content) return true;

		let blocks = row.blocks;
		if (typeof blocks === "string") {
			try {
				blocks = JSON.parse(blocks);
			} catch (e) {
				return false;
			}
		}
		return Array.isArray(blocks) && blocks.length > 0;
	},

	/**
	 * Pick the server row that finishes the turn we are still waiting on, or
	 * null if there is nothing to adopt yet.
	 *
	 * Matching on the turn's message_id is exact. Without one — the socket
	 * dropped before stream_start — the trailing row is the only candidate,
	 * and it is adopted only when it carries an id we have never rendered.
	 * Anything looser would replay the previous answer as if it were this one
	 * (e.g. under GDPR processing restriction, where nothing is persisted).
	 */
	_pick_recovery_row(rows, messageId, seenIds) {
		if (!Array.isArray(rows) || !rows.length) return null;

		if (messageId) {
			const match = rows.filter((m) => m.message_id === messageId)[0];
			return match && this._is_finalized_row(match) ? match : null;
		}

		const last = rows[rows.length - 1];
		if (!this._is_finalized_row(last) || !last.message_id) return null;
		if (seenIds && seenIds.has(last.message_id)) return null;
		return last;
	},

	_fetch_session_messages(session_id) {
		return new Promise((resolve, reject) => {
			frappe.call({
				method: "frappe_assistant_core.chat.api.chat.sessions.get_session_history",
				type: "GET",
				args: { session_id: session_id },
				callback: (r) => {
					const payload = r && r.message;
					if (Array.isArray(payload)) return resolve(payload);
					resolve(payload && Array.isArray(payload.messages) ? payload.messages : []);
				},
				error: (err) => reject(err),
			});
		});
	},

	/**
	 * Re-read the persisted turn and adopt it if the answer landed while we
	 * weren't listening. Stream events have no server-side replay buffer, so
	 * the persisted row is the only recovery path.
	 *
	 * @returns {Promise<boolean>} whether an answer was adopted
	 */
	async reconcile_from_server(widget) {
		if (!widget || !widget.session_id) return false;
		if (this._reconcileInFlight) return false;

		this._reconcileInFlight = true;
		const sessionId = widget.session_id;
		try {
			const rows = await this._fetch_session_messages(sessionId);
			// The user may have switched conversations during the await, or the
			// real stream_complete may have landed and finalized the turn — in
			// which case adopting now would render the answer twice.
			if (widget.session_id !== sessionId || !widget._isStreaming) return false;

			const row = this._pick_recovery_row(
				rows,
				widget.current_message_id,
				widget._seenMessageIds
			);
			if (!row) return false;

			this._adopt_server_answer(widget, row);
			return true;
		} catch (err) {
			FACOLogger.error("Failed to reconcile session from server:", err);
			return false;
		} finally {
			this._reconcileInFlight = false;
		}
	},

	/**
	 * Render a persisted answer into the turn the user is still watching.
	 */
	_adopt_server_answer(widget, row) {
		this.clear_timeouts();
		this.note_seen_message(widget, row.message_id);

		// A row can be terminal without text (blocks-only, or a stop/error flag).
		// The widget renders text, so that becomes a plain notice.
		if (!row.content) {
			this._fail_turn(
				widget,
				row.aborted
					? __("Response stopped.")
					: __("The response ended unexpectedly. Please try again."),
				""
			);
			return;
		}

		widget._isStreaming = false;
		const $streaming = widget.$widget.find(".faco-message-streaming");
		if ($streaming.length) {
			// finalize_streaming_message prefers the locally streamed text; the
			// server row is the complete one, so it wins.
			$streaming.find(".faco-message-text").data("raw-markdown", row.content);
			this.finalize_streaming_message(widget, row.content, 0, null);
		} else {
			// The turn was already given up on (timeout wiped the bubble) —
			// append the answer rather than losing it.
			widget.add_message_to_ui("assistant", row.content);
			widget.messages.push({ role: "assistant", content: row.content });
		}
		this._release_composer(widget);
	},

	// --- Processing Indicator ---

	/**
	 * Start the processing indicator timers for tips display
	 * @param {Object} widget - Widget instance
	 */
	start_processing_indicator(widget) {
		this.stop_processing_indicator(widget);

		widget._processing_tip_index = Math.floor(Math.random() * this.PROCESSING_TIPS.length);

		widget._processing_tip_timer = setTimeout(() => {
			this.show_processing_tip(widget);

			widget._processing_tip_rotation = setInterval(() => {
				widget._processing_tip_index =
					(widget._processing_tip_index + 1) % this.PROCESSING_TIPS.length;
				this.show_processing_tip(widget);
			}, 8000);
		}, 5000);
	},

	/**
	 * Display the current processing tip
	 * @param {Object} widget - Widget instance
	 */
	show_processing_tip(widget) {
		const $tip = widget.$widget.find(".faco-processing-tip");
		if ($tip.length > 0) {
			$tip.css("display", "block").text(this.PROCESSING_TIPS[widget._processing_tip_index]);
		}
	},

	/**
	 * Clear processing indicator timers
	 * @param {Object} widget - Widget instance
	 */
	stop_processing_indicator(widget) {
		if (widget._processing_tip_timer) {
			clearTimeout(widget._processing_tip_timer);
			widget._processing_tip_timer = null;
		}
		if (widget._processing_tip_rotation) {
			clearInterval(widget._processing_tip_rotation);
			widget._processing_tip_rotation = null;
		}
	},

	/**
	 * Update the processing status message
	 * @param {Object} widget - Widget instance
	 * @param {string} status - Status text
	 */
	update_processing_status(widget, status) {
		const $text = widget.$widget.find(".faco-processing-text");
		if ($text.length > 0) {
			$text.text(status);
		}
	},

	// --- HITL Interaction Cards ---

	/**
	 * Flip the most recent pending interaction card to "expired" state.
	 * Called when AR emits ar_interrupt_event{kind:"expired"}.
	 */
	mark_interaction_expired(widget) {
		const $card = widget.$widget
			.find(".faco-interaction-card")
			.not(".faco-interaction-decided")
			.last();
		if (!$card.length) return;
		$card.addClass("faco-interaction-decided faco-interaction-expired");
		$card.find("button, input").prop("disabled", true);
		// Replace card body with a warning banner. Match the SPA's amber tone
		// (#f59e0b, the codebase's `--faco-warning`).
		$card.html(
			`<div class="faco-interaction-expired-banner" style="padding:8px 12px;
        border:1px solid #f59e0b;border-radius:6px;background:#fffbeb;
        color:#92400e;font-size:13px;">${__("Approval expired — resend to continue")}</div>`
		);
		// The banner says "resend", so the composer has to accept one. It was
		// disabled when the card rendered and only resolve_interaction re-enables
		// it — which never runs for a card that expired.
		this._release_composer(widget);
		this.clear_approval_attention(widget);
	},

	/**
	 * Dismiss a pending card because another tab resolved the pause.
	 * Subtle gray styling — the action is done; no input needed.
	 */
	dismiss_resolved_interaction(widget) {
		const $card = widget.$widget
			.find(".faco-interaction-card")
			.not(".faco-interaction-decided")
			.last();
		if (!$card.length) return;
		$card
			.addClass("faco-interaction-decided faco-interaction-resolved-elsewhere")
			.css({ opacity: 0.5 })
			.html(
				`<div style="padding:8px 12px;color:#6b7280;font-style:italic;
            font-size:13px;">${__("Resolved in another tab")}</div>`
			);
		this._release_composer(widget);
		this.clear_approval_attention(widget);
	},

	/**
	 * Best-effort: call AR (via FAC proxy) to check for a pending HITL
	 * pause on this session. If one is present, render the InteractionCard
	 * via the existing show_interaction_card path (which is now idempotent).
	 * Used on widget init() and after socket reconnect.
	 */
	hydrate_pending_interrupt(widget) {
		if (!widget.session_id) return;
		frappe.call({
			method: "frappe_assistant_core.chat.api.chat.get_pending_interrupt",
			args: { session_id: widget.session_id },
			type: "GET",
			callback: (r) => {
				const data = r && r.message;
				if (!data || !data.pending || !data.event) return;
				// Reuse the existing card-render path. The guard in
				// show_interaction_card prevents duplicates.
				this.show_interaction_card(widget, data.event);
				this._schedule_local_expiry(widget, data.expires_at);
			},
		});
	},

	/**
	 * Safety net for the expiry flip. The authoritative `ar_interrupt_event`
	 * is published on AR's own realtime, which a split deployment's browsers
	 * never see, so without a local timer an expired card stays interactive
	 * and its composer stays locked until a page reload.
	 */
	_schedule_local_expiry(widget, expiresAt) {
		if (widget._expiryTimer) {
			clearTimeout(widget._expiryTimer);
			widget._expiryTimer = null;
		}
		if (!expiresAt) return;

		const ms = new Date(expiresAt).getTime() - Date.now();
		if (!(ms > 0 && ms < 24 * 60 * 60 * 1000)) return;

		const sessionId = widget.session_id;
		widget._expiryTimer = setTimeout(() => {
			widget._expiryTimer = null;
			// The user may have switched conversations while it ran.
			if (widget.session_id !== sessionId) return;
			this.mark_interaction_expired(widget);
		}, ms);
	},

	/**
	 * Show an interaction card (approval or question) in the chat
	 * @param {Object} widget - Widget instance
	 * @param {Object} data - Interaction data from approval_required event
	 */
	show_interaction_card(widget, data) {
		this.stop_processing_indicator(widget);
		widget.$widget.find(".faco-thinking-indicator").remove();
		widget.$widget.find(".faco-tool-indicator").remove();
		widget.$widget.find(".faco-processing-indicator").hide();

		// Idempotency guard: hydration on page-mount or after socket reconnect
		// can call this with the same tool_id as a live socket event. Don't
		// render a duplicate card.
		const toolId = data.tool_id;
		if (toolId) {
			const existing = widget.$widget
				.find(`.faco-interaction-card[data-tool-id='${toolId}']`)
				.not(".faco-interaction-decided");
			if (existing.length) {
				return;
			}
		}

		// HTML-escape once; reused in every card root's data-tool-id attribute.
		const safeToolIdAttr = data.tool_id ? frappe.utils.escape_html(data.tool_id) : "";

		// Show text content if any was streamed before the interrupt
		const $streamingMsg = widget.$widget.find(".faco-message-streaming");
		if ($streamingMsg.length) {
			const $content = $streamingMsg.find(".faco-message-text");
			if ($content.data("raw-markdown")) {
				$content.show();
			}
		}

		const interrupts = data.interrupts || [];
		const firstInterrupt = interrupts[0] || {};
		const reason = firstInterrupt.reason || {};
		const interactionType = reason.type || "approval";

		let cardHtml = "";

		if (interactionType === "approval") {
			const toolName = data.tool_name || "";
			const titleMap = {
				create_document: "Create Document",
				update_document: "Update Document",
				delete_document: "Delete Document",
				submit_document: "Submit Document",
			};
			const title = titleMap[toolName] || toolName.replace(/_/g, " ");
			const action = reason.action || title;
			const input = data.input || {};
			const detailsHtml = Object.entries(input)
				.filter(([, v]) => typeof v !== "object")
				.slice(0, 5)
				.map(
					([k, v]) =>
						`<span class="faco-interaction-detail">${k.replace(
							/_/g,
							" "
						)}: <b>${v}</b></span>`
				)
				.join(" · ");

			cardHtml = `
				<div class="faco-interaction-card faco-interaction-approval" data-tool-id="${safeToolIdAttr}">
					<div class="faco-interaction-header">
						<span class="faco-interaction-title">${__("Approval Required")}: ${action}</span>
					</div>
					${detailsHtml ? `<div class="faco-interaction-details">${detailsHtml}</div>` : ""}
					<div class="faco-interaction-actions">
						<button class="faco-interaction-btn faco-btn-reject" data-response="rejected">${__(
							"Reject"
						)}</button>
						<button class="faco-interaction-btn faco-btn-approve" data-response="approve">${__(
							"Approve"
						)}</button>
						<button class="faco-interaction-btn faco-btn-trust" data-response="trust">${__(
							"Always Allow"
						)}</button>
					</div>
				</div>`;
		} else if (interactionType === "single_select") {
			const options = reason.options || [];
			const pillsHtml = options
				.map(
					(opt) =>
						`<button class="faco-pill" data-value="${frappe.utils.escape_html(
							opt
						)}">${frappe.utils.escape_html(opt)}</button>`
				)
				.join("");

			cardHtml = `
				<div class="faco-interaction-card faco-interaction-question" data-tool-id="${safeToolIdAttr}">
					<div class="faco-interaction-question-text">${frappe.utils.escape_html(
						reason.question || ""
					)}</div>
					${
						reason.description
							? `<div class="faco-interaction-description">${frappe.utils.escape_html(
									reason.description
							  )}</div>`
							: ""
					}
					<div class="faco-interaction-pills">${pillsHtml}</div>
				</div>`;
		} else if (interactionType === "confirm") {
			cardHtml = `
				<div class="faco-interaction-card faco-interaction-question" data-tool-id="${safeToolIdAttr}">
					<div class="faco-interaction-question-text">${frappe.utils.escape_html(
						reason.question || ""
					)}</div>
					${
						reason.description
							? `<div class="faco-interaction-description">${frappe.utils.escape_html(
									reason.description
							  )}</div>`
							: ""
					}
					<div class="faco-interaction-actions">
						<button class="faco-interaction-btn faco-btn-reject" data-response="no">${__("No")}</button>
						<button class="faco-interaction-btn faco-btn-approve" data-response="yes">${__("Yes")}</button>
					</div>
				</div>`;
		} else if (interactionType === "multi_select") {
			const options = reason.options || [];
			const checksHtml = options
				.map(
					(opt) =>
						`<label class="faco-multi-option">
					<input type="checkbox" value="${frappe.utils.escape_html(opt)}" />
					<span>${frappe.utils.escape_html(opt)}</span>
				</label>`
				)
				.join("");

			cardHtml = `
				<div class="faco-interaction-card faco-interaction-question" data-tool-id="${safeToolIdAttr}">
					<div class="faco-interaction-question-text">${frappe.utils.escape_html(
						reason.question || ""
					)}</div>
					<div class="faco-interaction-multi">${checksHtml}</div>
					<button class="faco-interaction-btn faco-btn-approve faco-multi-submit" disabled>${__(
						"Submit"
					)}</button>
				</div>`;
		} else if (interactionType === "text_input") {
			cardHtml = `
				<div class="faco-interaction-card faco-interaction-question" data-tool-id="${safeToolIdAttr}">
					<div class="faco-interaction-question-text">${frappe.utils.escape_html(
						reason.question || ""
					)}</div>
					<div class="faco-interaction-text-input">
						<input type="text" class="faco-text-field" placeholder="${frappe.utils.escape_html(
							reason.placeholder || __("Type your answer...")
						)}" />
						<button class="faco-interaction-btn faco-btn-approve faco-text-submit" disabled>${__(
							"Send"
						)}</button>
					</div>
				</div>`;
		}

		const $messages = widget.$widget.find(".faco-messages");
		const $card = $(cardHtml);
		$messages.append($card);
		widget.scroll_to_bottom();

		// Disable input while interaction is pending
		widget.$widget.find(".faco-input-area textarea").prop("disabled", true);
		widget.$widget.find(".faco-send-btn").prop("disabled", true);

		// Register this card in the per-widget pending-interrupts batch. When
		// the model emits N parallel tool_use blocks that need approval, AR
		// streams N separate approval_required events and we render N cards.
		// Strands' resume contract requires a single resume call carrying
		// responses for every pending interrupt — firing one resume per card
		// races against Strands' per-agent threading lock and corrupts the
		// saved AR Message history. Batching here is the same fix used by
		// the Vue SPA in chatStore.submitInterruptDecision.
		if (!widget._pendingInterrupts) widget._pendingInterrupts = [];
		widget._pendingInterrupts.push({
			$card,
			interrupts,
			decision: null,
		});

		// Bind interaction card events (pass interrupts directly, not via DOM attribute)
		this.bind_interaction_events(widget, $card, interrupts);

		// Refresh the "Waiting for N more decisions" hint on any earlier card
		// that's already been decided.
		this._update_batch_hints(widget);

		this.raise_approval_attention(widget, data);
		this._schedule_local_expiry(widget, data.expires_at);
	},

	/**
	 * Make a pending approval impossible to miss.
	 *
	 * A card rendered into a closed widget lands in hidden DOM: the launcher
	 * carries no badge and autofade dims it to ~15% exactly when a decision is
	 * needed. So pop the widget open (same reasoning as the browser-tool
	 * prompt in widget_browser_tools.js), and raise signals that survive the
	 * user closing it again or working in another tab.
	 */
	raise_approval_attention(widget, data) {
		if (!widget.$widget) return;

		// Drives the launcher badge and suppresses autofade.
		widget.$widget.addClass("faco-awaiting-approval");

		if (!widget.is_open && typeof widget.open === "function") {
			try {
				widget.open();
			} catch (e) {
				/* best-effort — badge and toast still stand in */
			}
		}

		const toolName = data && data.tool_name;
		if (frappe.show_alert) {
			frappe.show_alert(
				{
					message: toolName
						? __("Approval needed: {0}", [toolName])
						: __("The assistant needs your approval"),
					indicator: "orange",
				},
				10
			);
		}

		this._start_title_flash();
	},

	/**
	 * Drop every attention signal. Safe to call when none is active.
	 */
	clear_approval_attention(widget) {
		if (widget && widget.$widget) {
			widget.$widget.removeClass("faco-awaiting-approval");
		}
		this._stop_title_flash();
	},

	// Alternates the tab title so a backgrounded tab still shows the ask.
	_start_title_flash() {
		if (this._titleFlashTimer) return;
		this._titleFlashOriginal = document.title;
		let showing = false;
		this._titleFlashTimer = setInterval(() => {
			showing = !showing;
			document.title = showing ? __("● Approval needed") : this._titleFlashOriginal;
		}, 1200);
	},

	_stop_title_flash() {
		if (!this._titleFlashTimer) return;
		clearInterval(this._titleFlashTimer);
		this._titleFlashTimer = null;
		if (this._titleFlashOriginal) document.title = this._titleFlashOriginal;
	},

	// Rendering an interaction card disables the composer; every path that
	// retires a card has to hand it back.
	_release_composer(widget) {
		if (!widget || !widget.$widget) return;
		widget.$widget.find(".faco-input-area textarea").prop("disabled", false);
		widget.$widget.find(".faco-send-btn").prop("disabled", false);
	},

	/**
	 * Bind click/input events on an interaction card
	 * @param {Object} widget - Widget instance
	 * @param {jQuery} $card - The interaction card element
	 * @param {Array} interrupts - Interrupt objects with id
	 */
	bind_interaction_events(widget, $card, interrupts) {
		const self = this;

		// Approval/confirm buttons
		$card.on("click", ".faco-interaction-btn[data-response]", function () {
			const response = $(this).data("response");
			self.resolve_interaction(widget, $card, interrupts, response);
		});

		// Single select pills
		$card.on("click", ".faco-pill", function () {
			const value = $(this).data("value");
			self.resolve_interaction(widget, $card, interrupts, value);
		});

		// Multi-select checkbox toggle
		$card.on("change", ".faco-multi-option input", function () {
			const checked = $card.find(".faco-multi-option input:checked").length;
			$card
				.find(".faco-multi-submit")
				.prop("disabled", checked === 0)
				.text(checked ? `${__("Submit")} (${checked})` : __("Submit"));
		});

		// Multi-select submit
		$card.on("click", ".faco-multi-submit", function () {
			const selected = [];
			$card.find(".faco-multi-option input:checked").each(function () {
				selected.push($(this).val());
			});
			if (selected.length) {
				self.resolve_interaction(widget, $card, interrupts, selected);
			}
		});

		// Text input
		$card.on("input", ".faco-text-field", function () {
			$card.find(".faco-text-submit").prop("disabled", !$(this).val().trim());
		});

		$card.on("click", ".faco-text-submit", function () {
			const val = $card.find(".faco-text-field").val().trim();
			if (val) self.resolve_interaction(widget, $card, interrupts, val);
		});

		$card.on("keydown", ".faco-text-field", function (e) {
			if (e.key === "Enter") {
				const val = $(this).val().trim();
				if (val) self.resolve_interaction(widget, $card, interrupts, val);
			}
		});
	},

	/**
	 * Record a user's decision on one HITL card, then flush all pending
	 * decisions in a single resume_interrupt call once every card has been
	 * decided. See the comment in show_interaction_card for why batching
	 * is required.
	 *
	 * @param {Object} widget - Widget instance
	 * @param {jQuery} $card - The interaction card element
	 * @param {Array} interrupts - Interrupt objects with id (this card's slice)
	 * @param {*} response - User's response value
	 */
	resolve_interaction(widget, $card, interrupts, response) {
		const entry = (widget._pendingInterrupts || []).find((e) => e.$card.is($card));
		if (!entry || entry.decision || widget._isSubmittingInterrupts) return;

		const displayResponse = Array.isArray(response) ? response.join(", ") : String(response);
		const isPositive = !["rejected", "no"].includes(response);
		entry.decision = { response, displayResponse, isPositive };

		// Visually mark this card as decided but keep it in place — the
		// resolved indicator only replaces it after the network call succeeds.
		$card.addClass("faco-interaction-decided");
		$card
			.find(
				".faco-interaction-actions, .faco-interaction-pills, .faco-interaction-multi, .faco-interaction-text-input"
			)
			.find("button, input")
			.prop("disabled", true);

		this._update_batch_hints(widget);

		// Flush only when every visible card has a decision.
		const allDecided = widget._pendingInterrupts.every((e) => e.decision);
		if (allDecided) {
			this._flush_pending_interrupts(widget);
		}
	},

	/**
	 * Render the "Waiting for N more decisions" hint on every decided card
	 * whenever a new card is added or another decision lands. Called from
	 * both show_interaction_card and resolve_interaction.
	 */
	_update_batch_hints(widget) {
		const pending = widget._pendingInterrupts || [];
		const undecided = pending.filter((e) => !e.decision).length;
		const hint =
			undecided === 0
				? ""
				: undecided === 1
				? __("Waiting for 1 more decision")
				: __("Waiting for {0} more decisions", [undecided]);

		pending.forEach((entry) => {
			if (!entry.decision) return;
			let $banner = entry.$card.find(".faco-interaction-batch-hint");
			if (!$banner.length) {
				$banner = $('<div class="faco-interaction-batch-hint"></div>');
				entry.$card.append($banner);
			}
			const label = entry.decision.isPositive ? __("Decided") : __("Decided");
			$banner.text(hint ? `${label} · ${hint}` : __("Submitting…"));
		});
	},

	/**
	 * Fire one resume_interrupt covering every decided card's response.
	 * On success, replace each card with its resolved indicator and clear
	 * the pending batch. On error, revert decisions so the user can retry.
	 */
	_flush_pending_interrupts(widget) {
		const pending = widget._pendingInterrupts || [];
		if (!pending.length || widget._isSubmittingInterrupts) return;

		const interruptResponses = [];
		pending.forEach((entry) => {
			entry.interrupts.forEach((i) => {
				interruptResponses.push({ interruptId: i.id, response: entry.decision.response });
			});
		});

		widget._isSubmittingInterrupts = true;
		pending.forEach((entry) => {
			const $banner = entry.$card.find(".faco-interaction-batch-hint");
			$banner.text(__("Submitting…"));
		});

		const self = this;
		frappe.call({
			method: "frappe_assistant_core.chat.api.chat.messages.resume_interrupt",
			args: {
				session_id: widget.session_id,
				interrupt_response: JSON.stringify(interruptResponses),
				message_id: widget.current_message_id || null,
				// Omitting this defaults AR to "spa", which flips client_type
				// mid-turn and rebuilds the agent holding the pause.
				client_type: "widget",
			},
			callback: () => {
				// Replace each card with its resolved indicator.
				pending.forEach((entry) => {
					const icon = entry.decision.isPositive ? "✓" : "✕";
					entry.$card.replaceWith(
						`<div class="faco-interaction-resolved">${icon} ${frappe.utils.escape_html(
							entry.decision.displayResponse
						)}</div>`
					);
				});
				widget._pendingInterrupts = [];
				widget._isSubmittingInterrupts = false;
				// The turn is live again — re-arm the watchdog the interrupt
				// cleared, or a drop after resume hangs the spinner forever.
				self.start_stream_timeout(widget);
				// Re-enable input — streaming resumes via Socket.IO.
				self._release_composer(widget);
				self.clear_approval_attention(widget);
			},
			error: (err) => {
				FACOLogger.error("Failed to resume interrupt:", err);
				// Revert: re-enable buttons on each card so the user can try again.
				pending.forEach((entry) => {
					entry.decision = null;
					entry.$card.removeClass("faco-interaction-decided");
					entry.$card.find("button, input").prop("disabled", false);
					entry.$card.find(".faco-interaction-batch-hint").remove();
				});
				widget._isSubmittingInterrupts = false;
			},
		});
	},

	// --- Streaming Messages ---

	/**
	 * Add a placeholder message with processing indicator
	 * @param {Object} widget - Widget instance
	 * @returns {jQuery} Message element
	 */
	add_streaming_message(widget) {
		const $messages = widget.$widget.find(".faco-messages");

		const $message = $(`
			<div class="faco-message faco-message-assistant faco-message-streaming">
				<div class="faco-message-avatar">
					${FACOCore.get_assistant_avatar()}
				</div>
				<div class="faco-message-content">
					<div class="faco-processing-indicator">
						<div class="faco-processing-status">
							<span class="faco-processing-dot"></span>
							<span class="faco-processing-text">${__("Processing your request...")}</span>
						</div>
						<div class="faco-processing-tip"></div>
					</div>
					<div class="faco-message-text" style="display: none;">
						<span class="faco-streaming-cursor">▋</span>
					</div>
				</div>
			</div>
		`);

		$messages.append($message);
		widget.scroll_to_bottom();

		this.start_processing_indicator(widget);
		this.set_robot_mood(widget, "thinking");

		return $message;
	},

	/**
	 * Set the mood data attribute on every robot avatar inside the widget.
	 * Mirrors the SPA's robotMoodStore behaviour without a real reactive
	 * store — the widget only needs idle/thinking/delighted/concerned
	 * transitions, which CSS handles via [data-mood].
	 *
	 * @param {Object} widget - Widget instance
	 * @param {string} mood - One of idle|attentive|thinking|delighted|concerned|excited|sleepy
	 */
	set_robot_mood(widget, mood) {
		const $robots = widget.$widget.find(".faco-robot");
		if (mood && mood !== "idle") {
			$robots.attr("data-mood", mood);
		} else {
			$robots.removeAttr("data-mood");
		}
	},

	/**
	 * Briefly set a transient mood, then revert to idle.
	 * Used for delighted/excited pulses after a successful completion.
	 *
	 * @param {Object} widget - Widget instance
	 * @param {string} mood - Transient mood
	 * @param {number} ms - Hold duration
	 */
	pulse_robot_mood(widget, mood, ms = 1500) {
		this.set_robot_mood(widget, mood);
		setTimeout(() => {
			// Only reset if the current mood is still the one we set —
			// avoids overwriting a newer mood (e.g. user fired off
			// another message during the pulse window).
			const $robots = widget.$widget.find(".faco-robot");
			if ($robots.attr("data-mood") === mood) {
				this.set_robot_mood(widget, "idle");
			}
		}, ms);
	},

	/**
	 * Update the streaming message with new chunk
	 * @param {Object} widget - Widget instance
	 * @param {string} chunk - New text chunk
	 */
	update_streaming_message(widget, chunk) {
		const $streamingMsg = widget.$widget.find(".faco-message-streaming");

		if ($streamingMsg.length > 0) {
			const $content = $streamingMsg.find(".faco-message-text");
			const $processingIndicator = $streamingMsg.find(".faco-processing-indicator");

			// On first chunk, hide processing indicator and show text container
			if ($processingIndicator.is(":visible")) {
				$processingIndicator.hide();
				$content.show();
				this.stop_processing_indicator(widget);
			}

			let rawText = $content.data("raw-markdown") || "";

			// Smart spacing: add paragraph break between distinct thoughts
			// BUT NOT inside markdown tables
			if (rawText.length > 0 && chunk.trim().length > 0) {
				const lines = rawText.split("\n");
				let inTable = false;

				for (let i = lines.length - 1; i >= Math.max(0, lines.length - 5); i--) {
					const line = lines[i].trim();
					if (line.startsWith("|") && line.endsWith("|")) {
						inTable = true;
						break;
					}
					if (line === "") {
						break;
					}
				}

				const chunkStartsTable =
					chunk.trim().startsWith("|") && chunk.trim().includes("|");

				if (!inTable && !chunkStartsTable) {
					const lastChar = rawText.trim().slice(-1);
					const firstChar = chunk.trim()[0];

					if (
						[".", "!", "?"].includes(lastChar) &&
						(firstChar === firstChar.toUpperCase() || chunk.startsWith("\n"))
					) {
						rawText += "\n\n";
					}
				}
			}

			rawText += chunk;
			$content.data("raw-markdown", rawText);
			$content.html(
				FACOCore.format_message(rawText, "assistant") +
					'<span class="faco-streaming-cursor">▋</span>'
			);
			widget.scroll_to_bottom();
		}
	},

	/**
	 * Finalize the streaming message
	 * @param {Object} widget - Widget instance
	 * @param {string} fullResponse - Complete response text
	 * @param {number} tokensUsed - Tokens consumed
	 * @param {number} quotaRemaining - Remaining quota
	 */
	finalize_streaming_message(widget, fullResponse, tokensUsed, quotaRemaining) {
		widget._isStreaming = false;
		this.stop_processing_indicator(widget);
		this.pulse_robot_mood(widget, "delighted");

		const $streamingMsg = widget.$widget.find(".faco-message-streaming");

		// Remove any remaining indicators
		widget.$widget.find(".faco-thinking-indicator").remove();
		widget.$widget.find(".faco-tool-indicator").remove();

		if ($streamingMsg.length > 0) {
			const $content = $streamingMsg.find(".faco-message-text");

			// Ensure text container is visible and processing indicator is hidden
			$streamingMsg.find(".faco-processing-indicator").hide();
			$content.show();

			let finalText = $content.data("raw-markdown") || fullResponse;
			$content.html(FACOCore.format_message(finalText, "assistant"));
			$content.removeData("raw-markdown");

			const $timestamp = $(
				`<div class="faco-message-time">${FACOCore.format_time(new Date())}</div>`
			);
			$streamingMsg.find(".faco-message-content").append($timestamp);

			$streamingMsg.removeClass("faco-message-streaming");

			widget.preferences.quota_used += tokensUsed;
			widget.update_quota_display();

			// The live turn's landing point — a THIRD place that kept only
			// {role, content}. It goes through the same field list as the two
			// history readers, and draws the chip now rather than leaving it to
			// appear only when the user comes back to the conversation.
			const landed = widget._toWidgetMessage({
				role: "assistant",
				content: fullResponse,
				routing: widget._pending_routing,
			});
			widget.messages.push(landed);
			widget.render_routing_chip(landed, $streamingMsg);
		}

		// One receipt per turn — never let it leak into the next one.
		widget._pending_routing = null;

		// Re-enable send button
		widget.$widget.find(".faco-send-btn").prop("disabled", false);
	},

	/**
	 * Handle streaming error
	 * @param {Object} widget - Widget instance
	 * @param {Object} data - Error data
	 */
	handle_stream_error(widget, data) {
		widget._isStreaming = false;
		this.stop_processing_indicator(widget);
		this.pulse_robot_mood(widget, "concerned", 2500);

		const $streamingMsg = widget.$widget.find(".faco-message-streaming");
		$streamingMsg.remove();

		widget.$widget.find(".faco-thinking-indicator").remove();
		widget.$widget.find(".faco-tool-indicator").remove();
		widget.$widget.find(".faco-send-btn").prop("disabled", false);

		if (data.action_required === "re_authorize") {
			frappe.msgprint({
				title: __("Re-authorization Required"),
				indicator: "orange",
				message: __(
					"Your FACO session has expired. Please contact your administrator to re-authorize the connection."
				),
				primary_action: {
					label: __("Go to Settings"),
					action: () => {
						frappe.set_route("Form", "FAC Chat Settings");
					},
				},
			});
		} else if (data.action_required === "register") {
			frappe.msgprint(__("FACO is not registered. Please contact your administrator."));
		} else {
			widget.add_message_to_ui("assistant", `Error: ${data.error}`, true);
		}
	},

	// --- Thinking Indicator ---

	/**
	 * Show thinking/reasoning indicator
	 * @param {Object} widget - Widget instance
	 * @param {string} content - Thinking content
	 */
	show_thinking_indicator(widget, content) {
		// When a plan is active, fold thinking into the running task's sub-slot.
		if (widget._activePlan) {
			const $slot = this._running_subactivity_slot(widget);
			if ($slot && $slot.length) {
				$slot.html('<span class="faco-plan-sub-spinner" style="animation: faco-pulse 1.5s ease-in-out infinite;">💭</span> ' + window.FACOPlanStrip._escape(__("Thinking...")));
				return;
			}
		}
		const $streamingMsg = widget.$widget.find(".faco-message-streaming");
		if ($streamingMsg.length > 0) {
			let $indicator = $streamingMsg.find(".faco-thinking-indicator");
			if ($indicator.length === 0) {
				$indicator = $(`
					<div class="faco-thinking-indicator" style="
						font-size: 12px;
						color: var(--faco-text-muted, #9ca3af);
						padding: 4px 8px;
						margin-bottom: 8px;
						background: var(--faco-bg-secondary, #f9fafb);
						border-radius: 4px;
						display: flex;
						align-items: center;
						gap: 6px;
					">
						<span class="faco-thinking-spinner" style="animation: faco-pulse 1.5s ease-in-out infinite;">💭</span>
						<span class="faco-thinking-text">${__("Thinking...")}</span>
					</div>
				`);
				$streamingMsg.find(".faco-message-content").prepend($indicator);
			}
		}
	},

	/**
	 * Hide thinking indicator
	 * @param {Object} widget - Widget instance
	 */
	hide_thinking_indicator(widget) {
		// Plan-active: thinking lives in the running task's sub-slot; clear it.
		if (widget._activePlan) {
			widget.$widget.find(".faco-plan-subactivity").empty();
			return;
		}
		widget.$widget.find(".faco-thinking-indicator").remove();
	},

	// --- Tool Indicators ---

	/**
	 * Show tool execution indicator
	 * @param {Object} widget - Widget instance
	 * @param {string} tool_name - Name of the tool
	 * @param {string} tool_id - Optional tool ID for tracking
	 */
	show_tool_indicator(widget, tool_name, tool_id = null) {
		// When a plan is active, fold the tool indicator into the running task's sub-slot.
		if (widget._activePlan) {
			const $slot = this._running_subactivity_slot(widget);
			if ($slot && $slot.length) {
				$slot.attr("data-active-tool-id", tool_id || "");
				$slot.html('<span class="faco-plan-sub-spinner" style="animation: faco-spin 1s linear infinite;">⚙️</span> ' + window.FACOPlanStrip._escape(`${__("Executing")}: ${tool_name}`));
				return;
			}
		}
		const $streamingMsg = widget.$widget.find(".faco-message-streaming");
		if ($streamingMsg.length > 0) {
			let $indicator = $streamingMsg.find(".faco-tool-indicator");
			if ($indicator.length === 0) {
				$indicator = $(`
					<div class="faco-tool-indicator" style="
						font-size: 12px;
						color: var(--faco-text-muted, #9ca3af);
						padding: 4px 8px;
						margin-top: 8px;
						background: var(--faco-bg-secondary, #f9fafb);
						border-radius: 4px;
						display: inline-flex;
						align-items: center;
						gap: 6px;
					">
						<span class="faco-tool-spinner" style="animation: faco-spin 1s linear infinite;">⚙️</span>
						<span class="faco-tool-name"></span>
					</div>
				`);
				$streamingMsg.find(".faco-message-content").append($indicator);
			}
			if (tool_id) {
				$indicator.attr("data-tool-id", tool_id);
			}
			$indicator.find(".faco-tool-name").text(`${__("Executing")}: ${tool_name}`);
		}
	},

	/**
	 * Hide tool execution indicator
	 * @param {Object} widget - Widget instance
	 * @param {string} tool_id - Optional tool ID to target specific indicator
	 * @param {boolean} cancelled - Whether the tool was cancelled
	 */
	hide_tool_indicator(widget, tool_id = null, cancelled = false) {
		// Plan-active: tool activity lives in the running task's sub-slot; clear it.
		if (widget._activePlan) {
			widget.$widget.find(".faco-plan-subactivity").empty();
			return;
		}
		if (tool_id) {
			widget.$widget.find(`.faco-tool-indicator[data-tool-id="${tool_id}"]`).remove();
		} else {
			widget.$widget.find(".faco-tool-indicator").remove();
		}
	},

	// --- Task plan strip ---

	/** Render/replace the live plan strip in the active streaming bubble. */
	render_plan(widget, plan) {
		const $streamingMsg = widget.$widget.find(".faco-message-streaming");
		if ($streamingMsg.length === 0) return;
		if (!plan || !plan.tasks || plan.tasks.length === 0) return;
		if (!window.FACOPlanStrip) return;

		// A plan is now active for this turn — Task 4's folding reads this.
		widget._activePlan = plan;

		// The generic spinner is redundant once we show real tasks.
		$streamingMsg.find(".faco-processing-indicator").hide();

		const $content = $streamingMsg.find(".faco-message-content");
		const html = window.FACOPlanStrip.stripHtml(plan);
		const $strip = $content.find(".faco-plan-strip");
		if ($strip.length) {
			$strip.replaceWith(html);
		} else {
			// Plan leads the bubble, above thinking/text.
			$content.prepend(html);
		}
	},

	/** Collapse the live strip to a one-line summary at plan_complete. */
	collapse_plan(widget, plan) {
		const $streamingMsg = widget.$widget.find(".faco-message-streaming");
		const finalPlan = plan || widget._activePlan;
		widget._activePlan = null;
		if (!finalPlan || !finalPlan.tasks || finalPlan.tasks.length === 0) return;
		if (!window.FACOPlanStrip) return;
		const $strip = $streamingMsg.find(".faco-plan-strip");
		if ($strip.length) {
			$strip.replaceWith(window.FACOPlanStrip.collapsedHtml(finalPlan));
		}
	},

	/** Find the sub-activity slot under the currently-running task, if any. */
	_running_subactivity_slot(widget) {
		const $streamingMsg = widget.$widget.find(".faco-message-streaming");
		return $streamingMsg.find(".faco-plan-row.faco-plan-running .faco-plan-subactivity").first();
	},
};
