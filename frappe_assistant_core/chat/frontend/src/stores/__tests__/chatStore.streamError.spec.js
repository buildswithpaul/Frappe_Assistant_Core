import { describe, it, expect, beforeEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useChatStore } from "../chatStore";

describe("chatStore.handleStreamError", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
	});

	it("keeps and finalizes the partial message when blocks were streamed", () => {
		const store = useChatStore();
		store.messages.push({
			role: "assistant",
			isStreaming: true,
			content: "",
			blocks: [{ type: "text", id: "b1", content: "partial answer" }],
		});

		const payload = {
			blocks: [{ type: "text", id: "b1", content: "partial answer" }],
			partial_response: "partial answer",
		};
		store.handleStreamError("Something broke", "UPSTREAM_ERROR", payload);

		const lastMsg = store.messages[store.messages.length - 1];
		expect(lastMsg.isStreaming).toBe(false);
		expect(lastMsg.errored).toBe(true);
		expect(lastMsg.blocks).toEqual(
			expect.arrayContaining([expect.objectContaining({ id: "b1", content: "partial answer" })])
		);
		const marker = lastMsg.blocks.find((b) => b._errorMarker);
		expect(marker).toBeTruthy();
		expect(marker.content).toBe("\n\n_(Interrupted by an error)_");
		expect(marker.type).toBe("text");
	});

	it("keeps the message using partial_response when there were no prior blocks", () => {
		const store = useChatStore();
		store.messages.push({
			role: "assistant",
			isStreaming: true,
			content: "",
			blocks: [],
		});

		store.handleStreamError("Something broke", "UPSTREAM_ERROR", {
			blocks: [],
			partial_response: "here is what I had so far",
		});

		const lastMsg = store.messages[store.messages.length - 1];
		expect(lastMsg.isStreaming).toBe(false);
		expect(lastMsg.errored).toBe(true);
		expect(lastMsg.content).toBe("here is what I had so far");
		expect(lastMsg.blocks.some((b) => b._errorMarker)).toBe(true);
	});

	it("flips pending interaction blocks to aborted", () => {
		const store = useChatStore();
		store.messages.push({
			role: "assistant",
			isStreaming: true,
			content: "",
			blocks: [{ type: "interaction", id: "i1", status: "pending" }],
		});

		store.handleStreamError("Something broke", "UPSTREAM_ERROR", {
			blocks: [{ type: "interaction", id: "i1", status: "pending" }],
			partial_response: "",
		});

		const lastMsg = store.messages[store.messages.length - 1];
		const interaction = lastMsg.blocks.find((b) => b.type === "interaction");
		expect(interaction.status).toBe("aborted");
	});

	it("pops the message when there is no content and no blocks (empty turn)", () => {
		const store = useChatStore();
		store.messages.push({
			role: "assistant",
			isStreaming: true,
			content: "",
			blocks: [],
		});
		const lengthBefore = store.messages.length;

		store.handleStreamError("Something broke", "UPSTREAM_ERROR", {
			blocks: [],
			partial_response: "",
		});

		expect(store.messages.length).toBe(lengthBefore - 1);
	});

	it("leaves INTERRUPT_ALREADY_RESOLVED handling unchanged", () => {
		const store = useChatStore();
		store.messages.push({
			role: "assistant",
			isStreaming: true,
			content: "",
			blocks: [{ type: "interaction", id: "i1", status: "pending" }],
		});

		store.handleStreamError("Already resolved", "INTERRUPT_ALREADY_RESOLVED", {
			blocks: [],
			partial_response: "",
		});

		const lastMsg = store.messages[store.messages.length - 1];
		expect(lastMsg.aborted).toBe(true);
		expect(lastMsg.isStreaming).toBe(false);
		const interaction = lastMsg.blocks.find((b) => b.type === "interaction");
		expect(interaction.status).toBe("aborted");
		expect(interaction.result).toEqual({ message: "Already resolved" });
		expect(lastMsg.errored).toBeUndefined();
	});
});
