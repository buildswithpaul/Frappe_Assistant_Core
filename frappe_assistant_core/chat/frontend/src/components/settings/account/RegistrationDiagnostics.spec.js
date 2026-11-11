import { beforeEach, describe, expect, it, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";

const runDiagnostics = vi.fn();
vi.mock("@/api/client", () => ({
	api: { registration: { runDiagnostics: (...args) => runDiagnostics(...args) } },
}));

import RegistrationDiagnostics from "./RegistrationDiagnostics.vue";

const warning = {
	status: "warning",
	slots: 4,
	required_slots: 20,
	reasons: [
		"Web server uses sync workers, which serve one request at a time, so chat polling, MCP callbacks and page loads queue behind each other. Run gunicorn with --worker-class gthread --threads 8.",
	],
	fix: "--worker-class gthread --threads 8",
};

async function runWith(result) {
	runDiagnostics.mockResolvedValue(result);
	const wrapper = mount(RegistrationDiagnostics);
	await wrapper.find(".run-btn").trigger("click");
	await flushPromises();
	return wrapper;
}

describe("RegistrationDiagnostics web server row", () => {
	beforeEach(() => runDiagnostics.mockReset());

	it("shows the warning and the fix beside an otherwise healthy registration", async () => {
		const wrapper = await runWith({ status: "ok", server_setup: warning });
		const row = wrapper.find("[data-testid='server-setup']");
		expect(row.text()).toContain("Web server");
		expect(row.text()).toContain("sync workers");
		expect(row.text().split("--worker-class gthread --threads 8")).toHaveLength(2);
		expect(row.classes()).toContain("banner-warn");
	});

	it("shows the row when the site has no FAC Cloud client", async () => {
		const wrapper = await runWith({ status: "no_client", server_setup: warning });
		expect(wrapper.find("[data-testid='server-setup']").exists()).toBe(true);
	});

	it("reports slots when the setup is fine", async () => {
		const wrapper = await runWith({
			status: "ok",
			server_setup: { status: "ok", slots: 32, required_slots: 20, reasons: [], fix: null },
		});
		const row = wrapper.find("[data-testid='server-setup']");
		expect(row.classes()).toContain("banner-success");
		expect(row.text()).toContain("32 request slots");
	});

	it("does not print a slot count for workers that multiplex connections", async () => {
		const wrapper = await runWith({
			status: "ok",
			server_setup: { status: "ok", slots: null, required_slots: 20, reasons: [], fix: null },
		});
		expect(wrapper.find("[data-testid='server-setup']").text()).not.toContain("null");
	});

	it("hides the row when the setup cannot be read", async () => {
		const wrapper = await runWith({
			status: "ok",
			server_setup: { status: "unknown", slots: null, required_slots: 20, reasons: [], fix: null },
		});
		expect(wrapper.find("[data-testid='server-setup']").exists()).toBe(false);
	});
});
