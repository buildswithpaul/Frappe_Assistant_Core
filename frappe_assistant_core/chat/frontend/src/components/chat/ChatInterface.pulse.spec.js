import { mount } from "@vue/test-utils";
import { nextTick } from "vue";
import { describe, it, expect, beforeEach, vi } from "vitest";
import { setActivePinia, createPinia } from "pinia";

vi.mock("@/api/client", () => ({
	api: {
		feedback: {
			pulseState: vi.fn().mockResolvedValue({ due: true }),
			markPulseShown: vi.fn().mockResolvedValue({ ok: true }),
			dismissPulse: vi.fn(),
			submitPulse: vi.fn(),
		},
		documents: {},
	},
}));

import { api } from "@/api/client";
import { useUserStore } from "@/stores/userStore";
import ChatInterface from "./ChatInterface.vue";
import PulseCard from "./feedback/PulseCard.vue";

describe("ChatInterface pulse", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
		vi.clearAllMocks();
		// production: the capabilities endpoint passes through AR's feedback_v2 block.
		useUserStore().capabilities = { feedback_v2: true };
	});

	it("asks when the stream stops, not while it runs", async () => {
		const stubs = { MessageBubble: true, DocumentPreviewPanel: true };
		const w = mount(ChatInterface, { props: { messages: [], isStreaming: true }, global: { stubs } });
		await nextTick();
		expect(api.feedback.pulseState).not.toHaveBeenCalled();
		await w.setProps({ isStreaming: false });
		await vi.waitFor(() => expect(w.findComponent(PulseCard).exists()).toBe(true));
		expect(api.feedback.markPulseShown).toHaveBeenCalledTimes(1);
	});
});
