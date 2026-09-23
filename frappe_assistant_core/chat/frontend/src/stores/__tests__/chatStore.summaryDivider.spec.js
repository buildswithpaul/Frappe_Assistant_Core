import { describe, it, expect, vi, beforeEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useChatStore } from "@/stores/chatStore";
import { call } from "frappe-ui";

// Live-bug repro: once a session summarizes, AR re-emits `context_summarized`
// AFTER the terminal stream event on every turn (streaming.py yields it right
// below terminal_event_name(), and SummarizingConversationManager never clears
// _summary_message). handleContextSummarized() pushes a `role: "divider"`
// pseudo-message onto the tail of `messages`, so findActiveMessage() — the one
// accessor every block mutation goes through — returned the divider instead of
// the assistant turn holding the pending approval card. Clicking Approve then
// died silently in recordInteractionDecision (`!lastMsg.blocks` -> null), which
// submitInterruptDecision reads as "other cards still pending": no HTTP call,
// no console error. A refresh dropped the client-only divider and the same
// click worked, which is exactly how the bug was reported.
vi.mock("@/api/client", () => ({
	api: {
		chat: {
			send: vi.fn().mockResolvedValue({}),
			cancelStream: vi.fn().mockResolvedValue({}),
		},
	},
}));
vi.mock("frappe-ui", () => ({ call: vi.fn().mockResolvedValue({}) }));

function approvalEvent(overrides = {}) {
	return {
		tool_id: "tool_1",
		tool_name: "create_document",
		input: { doctype: "Task", subject: "Ship it" },
		interrupts: [{ id: "int_1", reason: {} }],
		...overrides,
	};
}

function askUserEvent() {
	return {
		tool_id: "tool_2",
		tool_name: "ask_user",
		input: {},
		interrupts: [{ id: "int_2", reason: { type: "text_input", question: "Which company?" } }],
	};
}

describe("HITL cards after a context_summarized divider", () => {
	let store;

	beforeEach(() => {
		setActivePinia(createPinia());
		localStorage.clear();
		store = useChatStore();
		store.currentSessionId = "s1";
		store.messages = [
			{ role: "user", content: "create the task" },
			{
				role: "assistant",
				content: "",
				blocks: [],
				message_id: "msg_1",
				isStreaming: true,
				timestamp: new Date().toISOString(),
			},
		];
		vi.clearAllMocks();
	});

	it("still resumes when Approve is clicked after the divider lands", async () => {
		store.handleApprovalRequired(approvalEvent());
		store.completeStreaming("", { interrupted: true });
		store.handleContextSummarized();
		expect(store.messages[store.messages.length - 1].role).toBe("divider");

		await store.submitInterruptDecision({
			blockId: "tool_1",
			resolution: "approved",
			userResponse: "approve",
			response: "approve",
		});

		expect(call).toHaveBeenCalledWith(
			"frappe_assistant_core.chat.api.chat.resume_interrupt",
			expect.objectContaining({
				session_id: "s1",
				message_id: "msg_1",
				interrupt_response: JSON.stringify([
					{ interruptId: "int_1", response: "approve" },
				]),
			})
		);

		const card = store.messages[1].blocks.find((b) => b.type === "interaction");
		expect(card.status).toBe("approved");
		expect(store.hasPendingInteraction).toBe(false);
	});

	it("still resumes when an ask_user answer is submitted after the divider lands", async () => {
		store.handleApprovalRequired(askUserEvent());
		store.completeStreaming("", { interrupted: true });
		store.handleContextSummarized();

		const answered = await store.answerPendingQuestion("Acme Ltd");

		expect(answered).toBe(true);
		expect(call).toHaveBeenCalledWith(
			"frappe_assistant_core.chat.api.chat.resume_interrupt",
			expect.objectContaining({
				interrupt_response: JSON.stringify([
					{ interruptId: "int_2", response: "Acme Ltd" },
				]),
			})
		);
		expect(store.messages[1].blocks[0].status).toBe("answered");
	});

	it("routes a mid-turn approval onto the streaming turn, not a phantom bubble", async () => {
		// Summarization can also fire between tool calls within one turn. The
		// card must land on the turn already on screen.
		store.handleContextSummarized();
		store.handleApprovalRequired(approvalEvent());

		const assistantMsgs = store.messages.filter((m) => m.role === "assistant");
		expect(assistantMsgs).toHaveLength(1);
		expect(assistantMsgs[0].blocks.some((b) => b.type === "interaction")).toBe(true);
	});

	it("collapses a replayed event instead of stacking a second divider", () => {
		// AR now fires context_summarized only for a turn that actually
		// summarized, but a socket reconnect or a second tab can still replay
		// it. Two dividers in a row carry no extra information.
		store.handleContextSummarized();
		store.handleContextSummarized();

		expect(store.messages.filter((m) => m.role === "divider")).toHaveLength(1);
	});

	it("does NOT dedupe across turns — the per-turn gate has to stay server-side", () => {
		// Boundary marker, not a wish. The guard above only collapses
		// *consecutive* dividers; once a turn lands behind one, the tail is an
		// assistant message again and the guard can't fire. So "one divider per
		// turn forever" is prevented solely by AR's one-shot
		// consume_summarized_flag() — see test_resilient_summarizer.py. If that
		// gate is ever reverted to checking _summary_message, this count goes
		// back to one-per-turn and no client-side change will save it.
		for (let turn = 1; turn <= 3; turn++) {
			store.messages.push({ role: "user", content: `q${turn}` });
			store.messages.push({ role: "assistant", content: `a${turn}`, blocks: [] });
			store.handleContextSummarized();
		}

		expect(store.messages.filter((m) => m.role === "divider")).toHaveLength(3);
	});

	it("keeps streaming chunks on the assistant turn once a divider trails it", () => {
		store.appendStreamChunk("Summarizing the ");
		store.handleContextSummarized();
		store.appendStreamChunk("older messages.");

		const assistantMsgs = store.messages.filter((m) => m.role === "assistant");
		expect(assistantMsgs).toHaveLength(1);
		expect(assistantMsgs[0].content).toBe("Summarizing the older messages.");
	});
});
