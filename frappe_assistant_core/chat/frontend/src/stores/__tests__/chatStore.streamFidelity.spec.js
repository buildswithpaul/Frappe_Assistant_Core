import { describe, it, expect, vi, beforeEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useChatStore } from "@/stores/chatStore";
import { renderMarkdown } from "@/utils/markdown";

vi.mock("@/api/client", () => ({
	api: { chat: { getMessages: vi.fn(), cancelStream: vi.fn(), send: vi.fn().mockResolvedValue({}) } },
}));
vi.mock("frappe-ui", () => ({ call: vi.fn().mockResolvedValue({}) }));

// A live turn as the store holds it right after send.
function startTurn(store) {
	store.isStreaming = true;
	store.messages.push({ role: "assistant", content: "", blocks: [], isStreaming: true, _requestId: "r1" });
	return store.messages[store.messages.length - 1];
}

const textOf = (msg) => msg.blocks.filter((b) => b.type === "text").map((b) => b.content);

describe("streamed text is never rewritten", () => {
	let store;
	beforeEach(() => {
		setActivePinia(createPinia());
		store = useChatStore();
		store.currentSessionId = "s1";
	});

	// Chunk boundaries taken from the widget repro: the old widget inserted a
	// paragraph break whenever text ended in .!? and the next chunk began with
	// a character equal to its own uppercase form — digits included.
	it("keeps a numbered list split across token boundaries", () => {
		const msg = startTurn(store);
		for (const c of ["Steps:\n\n1", ".", " Open the Sales", " Invoice.", "\n2", ".", " Click Submit", "."]) {
			store.appendStreamChunk(c);
		}
		const html = renderMarkdown(textOf(msg).join(""));
		expect((html.match(/<li>/g) || []).length).toBe(2);
		expect(html).not.toMatch(/<p>1\.<\/p>/);
	});

	it("keeps decimals and abbreviations intact", () => {
		const msg = startTurn(store);
		for (const c of ["Total is 1", "2.", "5 units (e.g.", " Item A)."]) store.appendStreamChunk(c);
		expect(textOf(msg).join("")).toBe("Total is 12.5 units (e.g. Item A).");
	});

	it("starts a fresh text block after a tool call, so a table after it parses", () => {
		const msg = startTurn(store);
		store.appendStreamChunk("Let me check the invoices.");
		store.handleToolCallStart({ tool_id: "t1", tool_name: "list_documents", tool_input: {} });
		store.handleToolCallResult({ tool_id: "t1", status: "success", result: {} });
		store.appendStreamChunk("| Name | Amount |\n|---|---|\n| INV-1 | 100 |");
		const [, table] = textOf(msg);
		expect(renderMarkdown(table)).toMatch(/<table>/);
	});
});

describe("blocks keep arrival order", () => {
	it("thinking → tool → thinking → text", () => {
		setActivePinia(createPinia());
		const store = useChatStore();
		store.currentSessionId = "s1";
		const msg = startTurn(store);
		store.handleThinkingEvent({ content: "plan" });
		store.completeThinkingBlock();
		store.handleToolCallStart({ tool_id: "t1", tool_name: "list_documents", tool_input: {} });
		store.handleToolCallResult({ tool_id: "t1", status: "success", result: {} });
		store.handleThinkingEvent({ content: "group by customer" });
		store.completeThinkingBlock();
		store.appendStreamChunk("Here they are.");
		expect(msg.blocks.map((b) => b.type)).toEqual(["thinking", "tool_call", "thinking", "text"]);
	});
});
