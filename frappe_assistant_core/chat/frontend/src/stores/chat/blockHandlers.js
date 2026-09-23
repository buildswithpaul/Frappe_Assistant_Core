/**
 * Block-based message handlers for streaming events.
 *
 * Manages thinking blocks, tool call blocks,
 * and model fallback tracking during streaming responses.
 */

import { generateBlockId, findActiveMessage } from "./utils";

/**
 * Internal tools — housekeeping operations that should render as slim
 * inline indicators rather than full expandable tool call blocks.
 * These are things the agent does "behind the scenes" to prepare.
 */
export const INTERNAL_TOOLS = new Set([
	"get_skill",
	"workspace_read_file",
	"workspace_write_file",
	"workspace_list_files",
	"workspace_delete_file",
	"ask_user",
	"delegate",
]);

export function createBlockHandlers({
	messages,
	isStreaming,
	hasPendingInteraction,
	activeThinkingBlockId,
	activeToolCallId,
	streamRequestId,
}) {
	function getOrCreateStreamingMessage() {
		let lastMsg = findActiveMessage(messages.value);

		// Primary check: active streaming assistant message
		if (lastMsg && lastMsg.role === "assistant" && lastMsg.isStreaming) {
			if (!lastMsg.blocks) lastMsg.blocks = [];
			return lastMsg;
		}

		// Safety net 1: last message belongs to current request but streaming was interrupted
		// (e.g., by a socket disconnect). Re-activate it instead of creating a duplicate.
		if (
			lastMsg &&
			lastMsg.role === "assistant" &&
			streamRequestId.value &&
			lastMsg._requestId === streamRequestId.value
		) {
			lastMsg.isStreaming = true;
			isStreaming.value = true;
			if (!lastMsg.blocks) lastMsg.blocks = [];
			return lastMsg;
		}

		// Safety net 2: last assistant message is recent (within 90s) — likely an activity
		// timeout fired during a long tool call. Re-use instead of creating a duplicate bubble.
		if (lastMsg && lastMsg.role === "assistant" && !lastMsg.isStreaming) {
			const age = Date.now() - new Date(lastMsg.timestamp).getTime();
			if (age < 90000) {
				lastMsg.isStreaming = true;
				lastMsg.error = false;
				isStreaming.value = true;
				if (!lastMsg.blocks) lastMsg.blocks = [];
				return lastMsg;
			}
		}

		// No matching message — create new one
		lastMsg = {
			role: "assistant",
			content: "",
			blocks: [],
			timestamp: new Date().toISOString(),
			isStreaming: true,
			_requestId: streamRequestId.value,
		};
		messages.value.push(lastMsg);
		isStreaming.value = true;
		if (!lastMsg.blocks) lastMsg.blocks = [];
		return lastMsg;
	}

	function handlePlanEvent(data) {
		const plan = data?.plan;
		if (!plan || !Array.isArray(plan.tasks) || plan.tasks.length === 0) return;

		const msg = getOrCreateStreamingMessage();
		const block = {
			type: "plan",
			id: plan.id || generateBlockId("plan"),
			status: plan.status || "running",
			tasks: plan.tasks,
		};

		const existing = msg.blocks.find((b) => b.type === "plan");
		if (existing) {
			existing.status = block.status;
			existing.tasks = block.tasks;
		} else {
			msg.blocks.unshift(block);
		}
	}

	function handleWorkflowCreatedEvent(data) {
		if (!data || !data.docname) return;
		const msg = getOrCreateStreamingMessage();
		msg.blocks.push({
			type: "workflow_created",
			id: generateBlockId("workflow_created"),
			workflow_name: data.workflow_name,
			docname: data.docname,
			link: data.link,
			status: data.status,
			action: data.action,
		});
	}

	function handleModelSelected(data) {
		// The wire event is `model_selected`; there is no `model_fallback`.
		// The live receipt is `incomplete: true` — stream_complete supersedes
		// it with the same object plus what the turn actually cost.
		if (!data?.routing) return;

		const lastMsg = findActiveMessage(messages.value);
		if (lastMsg && lastMsg.role === "assistant") {
			lastMsg.routing = data.routing;
		}
	}

	function handleThinkingEvent(data) {
		const msg = getOrCreateStreamingMessage();

		if (activeThinkingBlockId.value) {
			const block = msg.blocks.find((b) => b.id === activeThinkingBlockId.value);
			if (block) {
				block.content += data.content || "";
				return;
			}
		}

		const thinkingId = generateBlockId("thinking");
		activeThinkingBlockId.value = thinkingId;

		msg.blocks.push({
			type: "thinking",
			id: thinkingId,
			content: data.content || "",
			isExpanded: false,
			isStreaming: true,
			startTime: new Date().toISOString(),
		});
	}

	function completeThinkingBlock() {
		if (!activeThinkingBlockId.value) return;

		const lastMsg = findActiveMessage(messages.value);
		if (lastMsg && lastMsg.blocks) {
			const block = lastMsg.blocks.find((b) => b.id === activeThinkingBlockId.value);
			if (block) {
				block.isStreaming = false;
				block.isExpanded = false;
				block.endTime = new Date().toISOString();
			}
		}
		activeThinkingBlockId.value = null;
	}

	function handleToolCallStart(data) {
		if (activeThinkingBlockId.value) {
			completeThinkingBlock();
		}

		const msg = getOrCreateStreamingMessage();
		const toolId = data.tool_id || generateBlockId("tool");
		activeToolCallId.value = toolId;

		const toolName = data.tool_name || "Unknown Tool";

		msg.blocks.push({
			type: "tool_call",
			id: toolId,
			tool_name: toolName,
			input: data.input || {},
			status: "running",
			result: null,
			isExpanded: false,
			isInternal: INTERNAL_TOOLS.has(toolName),
			startTime: new Date().toISOString(),
			endTime: null,
		});
	}

	function handleToolCallResult(data) {
		const lastMsg = findActiveMessage(messages.value);
		if (!lastMsg || !lastMsg.blocks) return;

		const toolId = data.tool_id || activeToolCallId.value;
		const block = lastMsg.blocks.find((b) => b.type === "tool_call" && b.id === toolId);

		if (block) {
			block.status = data.status || "success";
			block.result = data.result;
			block.endTime = new Date().toISOString();
		}

		if (toolId === activeToolCallId.value) {
			activeToolCallId.value = null;
		}

		// Side effect: when the generate_document tool succeeds, surface the
		// PDF in a dedicated footer block so the user can find it alongside
		// RAG sources. We do this in the result handler rather than via a
		// separate stream event so the existing tool plumbing stays the only
		// contract between AR and the UI — one source of truth for the file.
		_maybeAttachGeneratedDocument(data, lastMsg);
	}

	function _maybeAttachGeneratedDocument(data, lastMsg) {
		if (data.tool_name !== "generate_document") return;
		const result = data.result;
		if (!result || typeof result !== "object") return;
		if (result.success !== true) return;
		if (!result.file_url) return;
		if (!Array.isArray(lastMsg.blocks)) lastMsg.blocks = [];
		let block = lastMsg.blocks.find((b) => b.type === "generated_documents");
		if (!block) {
			block = {
				type: "generated_documents",
				id: generateBlockId("generated_documents"),
				items: [],
			};
			lastMsg.blocks.push(block);
		}
		if (!block.items.some((existing) => existing.file_url === result.file_url)) {
			block.items.push({
				file_url: result.file_url,
				file_name: result.file_name,
				file_size_display: result.file_size_display || "",
				document_type: "PDF",
			});
		}
	}

	function handleToolCancelled(data) {
		const lastMsg = findActiveMessage(messages.value);
		if (!lastMsg || !lastMsg.blocks) return;

		const toolId = data.tool_id || activeToolCallId.value;
		let block = lastMsg.blocks.find((b) => b.type === "tool_call" && b.id === toolId);

		if (!block && data.tool_name) {
			block = lastMsg.blocks.find(
				(b) =>
					b.type === "tool_call" &&
					b.tool_name === data.tool_name &&
					b.status === "running"
			);
		}

		if (block) {
			block.status = "cancelled";
			block.result = { message: data.message || "Tool execution was cancelled" };
			block.endTime = new Date().toISOString();
		}

		activeToolCallId.value = null;
	}

	function handleApprovalRequired(data) {
		// Idempotency guard: if a pending interaction block with the same
		// tool_id already exists on any recent message, refresh its
		// interrupts and return. Prevents duplicate cards when:
		//   - hydrate runs after the live socket event already rendered the card
		//   - socket reconnect re-hydrates a still-visible card
		//   - a stale tab (>90s) would otherwise let getOrCreateStreamingMessage
		//     create a fresh empty bubble that the guard couldn't see
		const toolId = data.tool_id;
		if (toolId) {
			const msgs = messages.value;
			for (let i = msgs.length - 1; i >= 0; i--) {
				const blocks = msgs[i]?.blocks;
				if (!blocks) continue;
				const existing = blocks.find(
					(b) => b.type === "interaction" && b.id === toolId && b.status === "pending"
				);
				if (existing) {
					if (Array.isArray(data.interrupts)) {
						existing.interrupts = data.interrupts;
					}
					return;
				}
			}
		}

		// No existing pending card for this tool — proceed with the normal path.
		const msg = getOrCreateStreamingMessage();

		const interrupts = data.interrupts || [];
		const firstInterrupt = interrupts[0] || {};
		const reason = firstInterrupt.reason || {};

		// Determine interaction type from the interrupt reason
		const interactionType = reason.type || "approval";

		msg.blocks.push({
			type: "interaction",
			id: data.tool_id || generateBlockId("interaction"),
			interactionType,
			// Approval-specific
			tool_name: data.tool_name || "Unknown Action",
			input: data.input || {},
			// Question-specific
			question:
				reason.question || reason.action || `${data.tool_name || "Action"} requires input`,
			options: reason.options || [],
			placeholder: reason.placeholder,
			description: reason.description,
			// Common
			interrupts: interrupts,
			action: reason.action || reason.question || "",
			status: "pending",
			isExpanded: true,
			startTime: new Date().toISOString(),
			endTime: null,
		});

		// Lock input while waiting for user response
		hasPendingInteraction.value = true;
	}

	function resolveInteraction(blockId, resolution, userResponse = null) {
		const lastMsg = findActiveMessage(messages.value);
		if (!lastMsg || !lastMsg.blocks) return;

		const block = lastMsg.blocks.find((b) => b.type === "interaction" && b.id === blockId);
		if (block) {
			block.status = resolution; // 'approved', 'rejected', 'trusted', 'answered'
			block.userResponse = userResponse;
			block.endTime = new Date().toISOString();
			block.isExpanded = false;
		}

		// Unlock input only if no other interaction blocks are still pending on
		// this turn. With parallel tool calls the model can raise N interrupts
		// at once and the user decides each card independently; keep the lock
		// held until the last decision lands.
		const stillPending = (lastMsg.blocks || []).some(
			(b) => b.type === "interaction" && b.status === "pending"
		);
		if (!stillPending) {
			hasPendingInteraction.value = false;
		}
	}

	/**
	 * Record a per-card decision without resolving the block yet.
	 *
	 * Strands' resume contract is "one resume call carries responses for all
	 * pending interrupts in this turn". With parallel tool calls the agent
	 * emits multiple approval cards; firing a separate `resume_interrupt` per
	 * click races against Strands' per-agent threading lock (Bug AR-PA-01) and
	 * also corrupts the saved tool_use/tool_result pairing in AR Message
	 * history. So we record decisions locally and let chatStore flush them as
	 * a single batched call once every card has a decision.
	 */
	function recordInteractionDecision(blockId, resolution, userResponse, response) {
		const lastMsg = findActiveMessage(messages.value);
		if (!lastMsg || !lastMsg.blocks) return null;

		const block = lastMsg.blocks.find((b) => b.type === "interaction" && b.id === blockId);
		if (!block || block.decision) return null;

		// Map the per-card decision onto each pending interrupt the card owns.
		// AR emits one interrupt per parallel tool, but we keep the same shape
		// here so question-type interactions (which often have a single
		// interrupt) flow through the same path.
		const interrupts = block.interrupts || [];
		const responses = interrupts.map((i) => ({ interruptId: i.id, response }));

		block.decision = { resolution, userResponse, response, responses };
		// Visually mark the card as decided but keep status = "pending" so the
		// flush step can flip it to the final resolution after the network call
		// succeeds (or revert it on failure).
		block.isExpanded = false;

		return collectPendingInteractionBatch();
	}

	/**
	 * If every pending interaction block on the streaming message has a
	 * recorded decision, return the consolidated interrupt_response array
	 * (and the block IDs to mark resolved on success). Otherwise null.
	 */
	function collectPendingInteractionBatch() {
		const lastMsg = findActiveMessage(messages.value);
		if (!lastMsg || !lastMsg.blocks) return null;

		const pendingBlocks = lastMsg.blocks.filter(
			(b) => b.type === "interaction" && b.status === "pending"
		);
		if (pendingBlocks.length === 0) return null;
		if (pendingBlocks.some((b) => !b.decision)) return null;

		const responses = pendingBlocks.flatMap((b) => b.decision.responses);
		return { blocks: pendingBlocks, responses };
	}

	/**
	 * Apply the recorded decisions to their blocks (call after the network
	 * resume_interrupt call succeeds). The resume stream will then deliver
	 * tool_call_result / further events.
	 */
	function applyInteractionDecisions(blocks) {
		const lastMsg = findActiveMessage(messages.value);
		if (!lastMsg || !lastMsg.blocks) return;

		for (const block of blocks) {
			if (!block.decision) continue;
			block.status = block.decision.resolution;
			block.userResponse = block.decision.userResponse;
			block.endTime = new Date().toISOString();
		}

		const stillPending = (lastMsg.blocks || []).some(
			(b) => b.type === "interaction" && b.status === "pending"
		);
		if (!stillPending) {
			hasPendingInteraction.value = false;
		}
	}

	/**
	 * Revert recorded decisions (call when the network resume_interrupt call
	 * fails — the user can retry by clicking the buttons again).
	 */
	function revertInteractionDecisions(blocks) {
		for (const block of blocks) {
			block.decision = null;
		}
	}

	/**
	 * A pause is per session and ar_interrupt_event carries no interrupt id,
	 * so expiry and resolution apply to every card the pause produced, not
	 * only the newest. Returns true if any block changed.
	 */
	function flipPendingInteractions(status) {
		const msgs = messages.value;
		let changed = false;
		for (const msg of msgs) {
			if (!msg.blocks) continue;
			for (const block of msg.blocks) {
				if (block.type === "interaction" && block.status === "pending") {
					block.status = status;
					block.endTime = new Date().toISOString();
					changed = true;
				}
			}
		}
		if (changed) hasPendingInteraction.value = false; // unlock input
		return changed;
	}

	function markInterruptExpired() {
		return flipPendingInteractions("expired");
	}

	function dismissResolvedInterrupt() {
		// Multi-tab case: another tab resolved this pause. Hide our
		// duplicate pending cards.
		return flipPendingInteractions("resolved_elsewhere");
	}

	function toggleBlockExpansion(messageIndex, blockId) {
		const msg = messages.value[messageIndex];
		if (!msg || !msg.blocks) return;

		const block = msg.blocks.find((b) => b.id === blockId);
		if (block) {
			block.isExpanded = !block.isExpanded;
		}
	}

	return {
		handlePlanEvent,
		handleWorkflowCreatedEvent,
		handleModelSelected,
		handleThinkingEvent,
		completeThinkingBlock,
		handleToolCallStart,
		handleToolCallResult,
		handleToolCancelled,
		handleApprovalRequired,
		markInterruptExpired,
		dismissResolvedInterrupt,
		resolveInteraction,
		recordInteractionDecision,
		collectPendingInteractionBatch,
		applyInteractionDecisions,
		revertInteractionDecisions,
		toggleBlockExpansion,
	};
}
