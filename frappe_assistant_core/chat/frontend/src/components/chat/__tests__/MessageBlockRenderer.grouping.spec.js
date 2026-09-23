import { mount } from "@vue/test-utils";
import { describe, it, expect } from "vitest";
import MessageBlockRenderer from "@/components/chat/MessageBlockRenderer.vue";

// Live-bug repro: the model answered mid-turn and kept working, and the answer
// was pulled into the processing card by a lookahead that re-ran on every
// appended block. The prose rendered correctly outside the card while it
// streamed, then jumped inside the moment the next tool_call arrived — and
// vanished when the card auto-collapsed at the end of the turn.

const ProcessingCardStub = {
	name: "ProcessingCard",
	props: ["blocks", "isStreaming", "isExpanded", "messageIndex"],
	emits: ["toggle", "toggleBlock"],
	template: `<div class="card-stub" :data-expanded="String(isExpanded)" @click="$emit('toggle')" />`,
};

const InteractionCardStub = {
	name: "InteractionCard",
	props: ["block"],
	template: `<div class="interaction-stub" />`,
};

function mountRenderer(blocks, isStreaming = false) {
	return mount(MessageBlockRenderer, {
		props: { blocks, messageIndex: 0, isStreaming },
		global: {
			stubs: {
				ProcessingCard: ProcessingCardStub,
				InteractionCard: InteractionCardStub,
				ProcessingIndicator: true,
				SourcesBlock: true,
				GeneratedDocumentsBlock: true,
				WorkflowCreatedBlock: true,
			},
		},
	});
}

function cards(wrapper) {
	return wrapper.findAllComponents(ProcessingCardStub);
}

function tool(id, tool_name, doctype, status = "success") {
	return { id, type: "tool_call", tool_name, status, input: { doctype } };
}

const ANSWER = "The Sales Cycle is a chain of linked documents, each one a different commitment.";

describe("answer prose that is followed by more tool calls", () => {
	it("renders outside the card, and stays there when the next tool arrives", async () => {
		const blocks = [
			{ id: "th1", type: "thinking", content: "planning" },
			tool("c1", "search_link", "Territory"),
			{ id: "x1", type: "text", content: ANSWER },
		];
		const w = mountRenderer(blocks, true);

		const before = w.find(".text-block");
		expect(before.exists()).toBe(true);
		expect(before.text()).toContain("The Sales Cycle");
		const nodeBefore = before.element;

		// The very next SSE event: the model starts creating the Customer.
		await w.setProps({
			blocks: [...blocks, tool("c2", "create_document", "Customer", "running")],
		});

		const after = w.find(".text-block");
		expect(after.exists()).toBe(true);
		expect(after.text()).toContain("The Sales Cycle");
		// Not merely still present — the very same DOM node, never reflowed.
		expect(after.element).toBe(nodeBefore);
	});

	it("never puts a text block inside a processing card", () => {
		const w = mountRenderer([
			{ id: "th1", type: "thinking", content: "planning" },
			{ id: "x1", type: "text", content: ANSWER },
			tool("c1", "create_document", "Customer"),
			{ id: "x2", type: "text", content: "Customer created." },
		]);

		expect(cards(w).length).toBeGreaterThan(0);
		for (const card of cards(w)) {
			for (const block of card.props("blocks")) {
				expect(block.type).not.toBe("text");
			}
		}
	});
});

describe("grouping edge cases", () => {
	it("does not let a whitespace-only chunk split one card in two", () => {
		const w = mountRenderer([
			tool("c1", "search_link", "Territory"),
			{ id: "x1", type: "text", content: "\n\n" },
			tool("c2", "get_document", "Customer"),
		]);

		expect(cards(w)).toHaveLength(1);
		expect(w.findAll(".text-block")).toHaveLength(0);
	});

	it("gives every card its own expand state when an approval shares a tool id", async () => {
		// A resolved interaction carries the SAME id as the tool_call it gated
		// (blockHandlers: `id: data.tool_id`), so minting a group for it would
		// reuse `pg_<tool_id>` and make one chevron drive two cards.
		const w = mountRenderer([
			{ id: "x1", type: "text", content: "Creating the Customer now." },
			tool("X", "create_document", "Customer"),
			{ id: "x2", type: "text", content: "Waiting for your approval." },
			{ id: "X", type: "interaction", status: "approved", tool_name: "create_document" },
			tool("Y", "submit_document", "Customer"),
		]);

		const list = cards(w);
		expect(list).toHaveLength(2);

		await list[0].trigger("click");

		expect(cards(w)[0].props("isExpanded")).toBe(true);
		expect(cards(w)[1].props("isExpanded")).toBe(false);
	});

	it("keeps sibling approvals of one batch on the same card", () => {
		// AR gates parallel tool calls in a single batch, and
		// applyInteractionDecisions flips them all in one pass — so the receipts
		// arrive consecutively and all belong to the card that did the work.
		const w = mountRenderer([
			tool("A", "create_document", "Customer"),
			tool("B", "submit_document", "Customer"),
			{ id: "A", type: "interaction", status: "approved", tool_name: "create_document" },
			{ id: "B", type: "interaction", status: "approved", tool_name: "submit_document" },
		]);

		expect(cards(w)).toHaveLength(1);
		expect(w.find(".interaction-stub").exists()).toBe(false);
		expect(cards(w)[0].props("blocks").map((b) => b.type)).toEqual([
			"tool_call",
			"tool_call",
			"interaction",
			"interaction",
		]);
	});

	it("starts a new card for work that follows an approval", () => {
		const w = mountRenderer([
			tool("A", "create_document", "Customer"),
			{ id: "A", type: "interaction", status: "approved", tool_name: "create_document" },
			tool("B", "submit_document", "Customer"),
		]);

		expect(cards(w)).toHaveLength(2);
	});

	it("renders a resolved approval at top level rather than in a card of its own", () => {
		const w = mountRenderer([
			{ id: "x1", type: "text", content: "I need your approval." },
			{ id: "X", type: "interaction", status: "approved", tool_name: "create_document" },
			{ id: "x2", type: "text", content: "Thanks — created." },
		]);

		expect(cards(w)).toHaveLength(0);
		expect(w.find(".interaction-stub").exists()).toBe(true);
	});
});

describe("collapse preference for cards not yet minted", () => {
	const live = [tool("c1", "search_link", "Territory", "running")];

	function appendSecondCard(blocks) {
		return [
			...blocks,
			{ id: "x1", type: "text", content: "Now creating the record." },
			tool("c2", "create_document", "Customer", "running"),
		];
	}

	it("collapses later cards once the user collapses one mid-stream", async () => {
		const w = mountRenderer(live, true);
		expect(cards(w)[0].props("isExpanded")).toBe(true);

		// One click must actually collapse — an auto-expanded card has no entry,
		// so toggling the raw value would be a no-op the user sees as a dead click.
		await cards(w)[0].trigger("click");
		expect(cards(w)[0].props("isExpanded")).toBe(false);

		await w.setProps({ blocks: appendSecondCard(live) });
		expect(cards(w)[1].props("isExpanded")).toBe(false);
	});

	it("re-expanding restores auto-expand for later cards", async () => {
		const w = mountRenderer(live, true);
		await cards(w)[0].trigger("click");
		await cards(w)[0].trigger("click");
		expect(cards(w)[0].props("isExpanded")).toBe(true);

		await w.setProps({ blocks: appendSecondCard(live) });
		expect(cards(w)[1].props("isExpanded")).toBe(true);
	});

	it("does not treat reading finished history as a preference about live work", async () => {
		// Collapsing a card on a turn that already ended says nothing about the
		// cards a later resume (HITL approval, Continue, socket recovery) mints.
		const w = mountRenderer(live, false);
		await cards(w)[0].trigger("click");
		await cards(w)[0].trigger("click");

		await w.setProps({ isStreaming: true, blocks: appendSecondCard(live) });
		expect(cards(w)[1].props("isExpanded")).toBe(true);
	});
});
