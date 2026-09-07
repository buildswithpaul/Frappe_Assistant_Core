import { beforeEach, describe, expect, it, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";

const getEnvironment = vi.fn();
vi.mock("@/api/client", () => ({
	api: { support: { getEnvironment, createTicket: vi.fn(), submitFeedback: vi.fn() } },
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

async function openModal() {
	const { useSupportStore } = await import("@/stores/supportStore");
	const { default: SupportModal } = await import("@/components/support/SupportModal.vue");
	const store = useSupportStore();
	store.open({ mode: "issue" });

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
