import { beforeEach, describe, expect, it, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";

const getEnvironment = vi.fn();
const submitFeedback = vi.fn();
const createTicket = vi.fn();
vi.mock("@/api/client", () => ({
	api: { support: { getEnvironment, createTicket, submitFeedback } },
}));
vi.mock("@/composables/useToast", () => ({
	useToast: () => ({ showError: vi.fn(), showSuccess: vi.fn() }),
}));
vi.mock("vue-router", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/stores/modelStore", () => ({
	useModelStore: () => ({ currentModelId: "claude-opus-5" }),
}));

const SERVER_ENV = {
	tenant_id: "T-123",
	fac_version: "3.0.0-beta.1",
	frappe_version: "16.15.0",
	bench_version: "5.24.1",
	installed_apps: "erpnext 16.14.0, frappe 16.15.0",
};

async function openModal({ mode = "issue", conversationId = null } = {}) {
	const { useSupportStore } = await import("@/stores/supportStore");
	const { default: SupportModal } = await import("@/components/support/SupportModal.vue");
	const store = useSupportStore();
	store.open({ mode, conversationId });

	const w = mount(SupportModal, {
		global: { stubs: { IssueForm: true, FeedbackForm: true, SupportConfirmation: true } },
	});
	await flushPromises();
	return w;
}

describe("SupportModal environment disclosure", () => {
	beforeEach(() => {
		vi.resetModules();
		getEnvironment.mockReset();
		setActivePinia(createPinia());
	});

	it("hands the server's versions to the issue form", async () => {
		getEnvironment.mockResolvedValue(SERVER_ENV);
		const env = (await openModal()).findComponent({ name: "IssueForm" }).props("environment");

		expect(env.fac_version).toBe("3.0.0-beta.1");
		expect(env.bench_version).toBe("5.24.1");
		expect(env.tenant_id).toBe("T-123");
		expect(env.installed_apps).toContain("erpnext 16.14.0");
		expect(env.model).toBe("claude-opus-5");
		expect(env.browser).toBeTruthy();
		expect(env).not.toHaveProperty("ar_version");
	});

	it("still renders a usable form when the versions call fails", async () => {
		getEnvironment.mockRejectedValue(new Error("offline"));
		const w = await openModal();

		expect(w.findComponent({ name: "IssueForm" }).props("environment").model).toBe(
			"claude-opus-5"
		);
	});
});

describe("SupportModal feedback scope", () => {
	beforeEach(() => {
		vi.resetModules();
		getEnvironment.mockReset();
		getEnvironment.mockResolvedValue(SERVER_ENV);
		submitFeedback.mockReset();
		submitFeedback.mockResolvedValue({});
		setActivePinia(createPinia());
	});

	it("never sends the conversation with feedback, even when opened from a chat", async () => {
		const w = await openModal({ mode: "feedback", conversationId: "sess-9" });
		w.findComponent({ name: "FeedbackForm" }).vm.$emit("submit", {
			rating: 5,
			comment: "nice",
			category: "Product",
		});
		await flushPromises();

		expect(submitFeedback).toHaveBeenCalledTimes(1);
		const payload = submitFeedback.mock.calls[0][0];
		expect(payload).not.toHaveProperty("conversationId");
		expect(JSON.stringify(payload)).not.toContain("sess-9");
	});

	it("still sends the rating, comment and environment", async () => {
		const w = await openModal({ mode: "feedback", conversationId: "sess-9" });
		w.findComponent({ name: "FeedbackForm" }).vm.$emit("submit", {
			rating: 4,
			comment: "good",
			category: "Product",
		});
		await flushPromises();

		const payload = submitFeedback.mock.calls[0][0];
		expect(payload.rating).toBe(4);
		expect(payload.comment).toBe("good");
		expect(payload.environment.fac_version).toBe("3.0.0-beta.1");
	});
});
