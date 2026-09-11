import { beforeEach, describe, expect, it, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";

const listMyTickets = vi.fn();
const listMyFeedback = vi.fn();
const getTicketThread = vi.fn();

vi.mock("@/api/client", () => ({
	api: {
		support: {
			listMyTickets: (...args) => listMyTickets(...args),
			listMyFeedback: (...args) => listMyFeedback(...args),
			getTicketThread: (...args) => getTicketThread(...args),
			replyToTicket: vi.fn(),
		},
	},
}));
vi.mock("@/composables/useToast", () => ({
	useToast: () => ({ showError: vi.fn(), showSuccess: vi.fn() }),
}));
const push = vi.fn();
vi.mock("vue-router", () => ({
	useRoute: () => ({ query: {} }),
	useRouter: () => ({ push }),
}));

import MyTicketsSettings from "@/components/settings/MyTicketsSettings.vue";

function mountSettings() {
	return mount(MyTicketsSettings, {
		global: { stubs: { TicketList: true, TicketStatusPill: true, AttachmentPicker: true } },
	});
}

function findTab(w, label) {
	return w.findAll(".tab-btn").find((b) => b.text() === label);
}

describe("MyTicketsSettings feedback tab", () => {
	beforeEach(() => {
		listMyTickets.mockReset().mockResolvedValue([]);
		listMyFeedback.mockReset();
		getTicketThread.mockReset().mockResolvedValue({ messages: [] });
	});

	it("does not call listMyFeedback on mount", async () => {
		mountSettings();
		await flushPromises();
		expect(listMyFeedback).not.toHaveBeenCalled();
	});

	it("calls listMyFeedback on first Feedback-tab click and not again after a successful load", async () => {
		listMyFeedback.mockResolvedValue([]);
		const w = mountSettings();
		await flushPromises();

		const feedbackTab = findTab(w, "Feedback");
		await feedbackTab.trigger("click");
		await flushPromises();
		expect(listMyFeedback).toHaveBeenCalledTimes(1);

		await feedbackTab.trigger("click");
		await flushPromises();
		expect(listMyFeedback).toHaveBeenCalledTimes(1);
	});

	it("hands off to the ticket thread: flips back to Tickets and renders that ticket's detail", async () => {
		listMyFeedback.mockResolvedValue([
			{
				name: "FB-1",
				rating: null,
				status: "We followed up",
				comment: "please help",
				category: "Product",
				submitted_at: "2026-08-01T00:00:00Z",
				escalated_ticket: "HD-0007",
			},
		]);
		const w = mountSettings();
		await flushPromises();

		await findTab(w, "Feedback").trigger("click");
		await flushPromises();

		await w.find(".view-ticket-btn").trigger("click");
		await flushPromises();

		expect(getTicketThread).toHaveBeenCalledWith("HD-0007");
		expect(w.find(".ticket-detail").exists()).toBe(true);
		expect(findTab(w, "Tickets").classes()).toContain("active");
		expect(findTab(w, "Feedback").classes()).not.toContain("active");
	});

	it("retries listMyFeedback on a second tab click after a failed first load", async () => {
		listMyFeedback.mockRejectedValueOnce(new Error("network blip"));
		listMyFeedback.mockResolvedValueOnce([]);
		const w = mountSettings();
		await flushPromises();

		const feedbackTab = findTab(w, "Feedback");
		await feedbackTab.trigger("click");
		await flushPromises();
		expect(listMyFeedback).toHaveBeenCalledTimes(1);
		expect(w.text()).toContain("Could not load your feedback");

		await feedbackTab.trigger("click");
		await flushPromises();
		expect(listMyFeedback).toHaveBeenCalledTimes(2);
	});
});

describe("MyTicketsSettings conversation hand-off", () => {
	it("routes to the chat when the ticket detail asks to open its conversation", async () => {
		push.mockClear();
		listMyTickets.mockResolvedValue([{ name: "1", subject: "S", status: "Open" }]);
		getTicketThread.mockResolvedValue({
			subject: "S", status: "Open", creation: "2026-09-09",
			conversation_id: "sess-42", messages: [],
		});
		const w = mountSettings();
		await flushPromises();

		w.findComponent({ name: "TicketList" }).vm.$emit("select", "1");
		await flushPromises();

		w.findComponent({ name: "TicketDetail" }).vm.$emit("navigate", "/chat/sess-42");
		expect(push).toHaveBeenCalledWith("/chat/sess-42");
	});
});
