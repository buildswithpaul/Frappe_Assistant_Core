import { describe, it, expect, vi, beforeEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { reactive } from "vue";

vi.mock("vue-router", () => ({
	useRoute: () => reactive({ params: {}, query: {}, name: "chat" }),
	useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));
vi.mock("@/composables/useStreaming", () => ({ useStreaming: vi.fn(), reconnectSocket: vi.fn() }));
vi.mock("@/composables/useChatViewInit", () => ({ useChatViewInit: vi.fn() }));
vi.mock("@/api/client", () => ({
	api: { chat: { send: vi.fn() }, users: { getMyCreditStatus: vi.fn().mockResolvedValue(null) } },
}));
vi.mock("@/components/templates/TemplateBrowserModal.vue", () => ({ default: {} }));
vi.mock("@/components/templates/ParameterModal.vue", () => ({ default: {} }));

import ChatView from "../ChatView.vue";
import ChatStagePicker from "@/components/chat/ChatStagePicker.vue";
import { useChatStore } from "@/stores/chatStore";
import { useModelStore } from "@/stores/modelStore";

describe("ChatView Continue after the turn credit limit", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
	});

	it("Continue sends a new message on the model a typed message would use", async () => {
		const chatStore = useChatStore();
		chatStore.sendMessage = vi.fn().mockResolvedValue();
		useModelStore().selectedModel = "claude-sonnet-4-6";

		const wrapper = shallowMount(ChatView);
		wrapper.findComponent(ChatStagePicker).vm.$emit("continue-turn");
		await flushPromises();

		expect(chatStore.sendMessage).toHaveBeenCalledTimes(1);
		const [message, , , modelId] = chatStore.sendMessage.mock.calls[0];
		expect(message).toBe("Continue");
		expect(modelId).toBe("claude-sonnet-4-6");
	});
});
