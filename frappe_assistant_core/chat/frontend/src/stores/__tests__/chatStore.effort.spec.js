import { describe, it, expect, vi, beforeEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useChatStore } from "@/stores/chatStore";
import { useComposerModesStore } from "@/stores/composerModesStore";
import { api } from "@/api/client";

vi.mock("@/api/client", () => ({
	api: {
		chat: {
			getMessages: vi.fn(),
			cancelStream: vi.fn().mockResolvedValue({}),
			send: vi.fn().mockResolvedValue({}),
		},
	},
}));
vi.mock("frappe-ui", () => ({ call: vi.fn().mockResolvedValue({}) }));

describe("chatStore send — thinking level", () => {
	let store;
	beforeEach(() => {
		setActivePinia(createPinia());
		localStorage.clear();
		store = useChatStore();
		store.currentSessionId = "s1";
		vi.clearAllMocks();
	});

	const sentOptions = () => api.chat.send.mock.calls[0][7];

	it("sends the level and the legacy boolean when a level is chosen", async () => {
		useComposerModesStore().setEffort("s1", "medium");
		await store.sendMessage("hi", [], null, "m1");
		expect(sentOptions()).toMatchObject({ reasoning_effort: "medium", thinking_enabled: true });
	});

	it("sends thinking_enabled false when off", async () => {
		useComposerModesStore().setEffort("s1", "off");
		await store.sendMessage("hi", [], null, "m1");
		expect(sentOptions()).toMatchObject({ reasoning_effort: "off", thinking_enabled: false });
	});
});
