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
import { usePulseStore } from "@/stores/pulseStore";
import { useChatStore } from "@/stores/chatStore";
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

	const stubs = { MessageBubble: true, DocumentPreviewPanel: true };

	// Caches pulse_state while no host is mounted, so a later maybeShow with a
	// host sets `visible` synchronously, before Vue can flush the card's render.
	async function warmDue() {
		await usePulseStore().maybeShow();
		expect(usePulseStore().visible).toBe(false);
	}

	async function unmountDuringAwait() {
		let release;
		api.feedback.pulseState.mockReturnValueOnce(new Promise((r) => (release = r)));
		const w = mount(ChatInterface, { props: { messages: [], isStreaming: true }, global: { stubs } });
		await w.setProps({ isStreaming: false });
		// production: New Chat / session switch unmounts the list while the fetch is in flight.
		w.unmount();
		release({ due: true });
		await vi.waitFor(() => expect(api.feedback.pulseState).toHaveBeenCalled());
		await nextTick();
		await nextTick();
	}

	it("does not start the clock when the interface unmounts during the await", async () => {
		await unmountDuringAwait();
		expect(api.feedback.markPulseShown).not.toHaveBeenCalled();
	});

	it("a card whose turn turns busy before it renders is not shown or marked", async () => {
		await warmDue();
		const w = mount(ChatInterface, { props: { messages: [], isStreaming: false }, global: { stubs } });
		usePulseStore().maybeShow();
		expect(usePulseStore().visible).toBe(true);
		// production: a queued message starts a stream in the same tick the flag flips.
		useChatStore().isStreaming = true;
		await nextTick();
		expect(w.findComponent(PulseCard).exists()).toBe(false);
		expect(api.feedback.markPulseShown).not.toHaveBeenCalled();
	});

	it("a card never rendered is gone when its host unmounts, and a remount shows nothing", async () => {
		await warmDue();
		const w = mount(ChatInterface, { props: { messages: [], isStreaming: false }, global: { stubs } });
		usePulseStore().maybeShow();
		expect(usePulseStore().visible).toBe(true);
		// production: New Chat unmounts the list before Vue flushed the card's render.
		w.unmount();
		expect(usePulseStore().visible).toBe(false);
		const again = mount(ChatInterface, { props: { messages: [], isStreaming: false }, global: { stubs } });
		await nextTick();
		expect(again.findComponent(PulseCard).exists()).toBe(false);
		expect(api.feedback.markPulseShown).not.toHaveBeenCalled();
	});

	it("a card the user has seen survives a new stream with the typed comment", async () => {
		await warmDue();
		const w = mount(ChatInterface, { props: { messages: [], isStreaming: false }, global: { stubs } });
		await usePulseStore().maybeShow();
		await nextTick();
		await w.find("[data-rating='3']").trigger("click");
		await w.find("[data-test=pulse-comment]").setValue("keep me");
		// production: the user sends another message while the card is open.
		useChatStore().isStreaming = true;
		await nextTick();
		expect(w.findComponent(PulseCard).exists()).toBe(true);
		expect(w.find("[data-test=pulse-comment]").element.value).toBe("keep me");
	});

	it("a rendered card survives a remount without a second mark", async () => {
		const w = mount(ChatInterface, { props: { messages: [], isStreaming: true }, global: { stubs } });
		await w.setProps({ isStreaming: false });
		await vi.waitFor(() => expect(w.findComponent(PulseCard).exists()).toBe(true));
		w.unmount();
		// production: ChatStagePicker / WidgetPanel swap ChatInterface on messages.length.
		const again = mount(ChatInterface, { props: { messages: [], isStreaming: false }, global: { stubs } });
		await nextTick();
		expect(again.findComponent(PulseCard).exists()).toBe(true);
		expect(api.feedback.markPulseShown).toHaveBeenCalledTimes(1);
	});
});
