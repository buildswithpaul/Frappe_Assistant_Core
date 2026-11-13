import { describe, expect, it, vi } from "vitest";
import { nextTick, reactive, ref } from "vue";
import { createPinia, setActivePinia } from "pinia";
import { useAskRequest } from "./useAskRequest";
import { useDiscoveryStore } from "@/stores/discoveryStore";

function setup({ sessionId = undefined, messages = [] } = {}) {
	setActivePinia(createPinia());
	const route = reactive({ params: { sessionId } });
	const list = ref(messages);
	const send = vi.fn();
	useAskRequest({ route, messages: list, send });
	return { route, list, send, store: useDiscoveryStore() };
}

describe("useAskRequest", () => {
	it("sends the waiting question once a new, empty chat shows, and only once", async () => {
		const { route, list, send, store } = setup({ sessionId: "s1", messages: [{ role: "user" }] });
		store.askRequested = { text: "Which items are below reorder level?" };
		await nextTick();
		expect(send).not.toHaveBeenCalled(); // still on an old chat
		route.params.sessionId = undefined;
		await nextTick();
		expect(send).not.toHaveBeenCalled(); // its messages are still showing
		list.value = [];
		await nextTick();
		expect(send).toHaveBeenCalledTimes(1);
	});

	it("sends it as soon as the new chat is empty", async () => {
		const { send, store } = setup();
		store.askRequested = { text: "Who owes us the most?" };
		await nextTick();
		expect(send).toHaveBeenCalledWith("Who owes us the most?");
		expect(store.askRequested).toBeNull();
		await nextTick();
		expect(send).toHaveBeenCalledTimes(1);
	});
});
