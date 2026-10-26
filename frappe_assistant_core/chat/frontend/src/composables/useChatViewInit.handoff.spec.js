import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import { defineComponent, reactive, ref } from "vue";

import { useChatViewInit } from "./useChatViewInit";

// Open Full Assistant stores the conversation for this tab; the chat app opens it and takes over a
// turn the widget was running, so that turn's browser calls come here (#34535).
function mountReady({ handoff }) {
	if (handoff) sessionStorage.setItem("faco_active_session", JSON.stringify({ id: handoff, user: "avery@x" }));
	const chatStore = {
		currentSessionId: null,
		hydrateSessions: vi.fn(),
		loadSessions: vi.fn(),
		loadMessages: vi.fn(),
		hydratePendingInterrupt: vi.fn(),
		takeFirstMessage: vi.fn(() => null),
		claimLiveTurn: vi.fn(async () => true),
	};
	const router = { push: vi.fn() };
	mount(
		defineComponent({
			setup() {
				useChatViewInit(
					{
						chatStore,
						userStore: { user: "avery@x", getAndClearInitialSessions: () => [] },
						modelStore: { loadModels: vi.fn() },
						suggestionStore: { loadSuggestions: vi.fn() },
					},
					{ route: reactive({ params: {}, query: {} }), router },
					{ registrationStatus: ref("ready"), isUserSetupComplete: ref(true) }
				);
				return () => null;
			},
		})
	);
	return { chatStore, router };
}

afterEach(() => sessionStorage.clear());

describe("useChatViewInit widget hand-off", () => {
	it("opens the handed-over conversation and claims its running turn", async () => {
		const { chatStore, router } = mountReady({ handoff: "s1" });
		await flushPromises();
		expect(router.push).toHaveBeenCalledWith("/chat/s1");
		expect(chatStore.claimLiveTurn).toHaveBeenCalledWith("s1");
	});

	it("claims nothing when nothing was handed over", async () => {
		const { chatStore } = mountReady({ handoff: null });
		await flushPromises();
		expect(chatStore.claimLiveTurn).not.toHaveBeenCalled();
	});
});
