import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { getLoading, setLoading, showError } = vi.hoisted(() => ({
	getLoading: vi.fn(),
	setLoading: vi.fn(),
	showError: vi.fn(),
}));
vi.mock("@/api/client", () => ({
	api: { tools: { getLoading: (...a) => getLoading(...a), setLoading: (...a) => setLoading(...a) } },
}));
vi.mock("@/composables/useToast", () => ({ useToast: () => ({ showError }) }));

import ToolsSettings from "../ToolsSettings.vue";

async function mountSettings(loadAsNeeded = true) {
	getLoading.mockResolvedValue({ load_tools_as_needed: loadAsNeeded });
	const w = mount(ToolsSettings);
	await flushPromises();
	return w;
}

describe("ToolsSettings", () => {
	beforeEach(() => {
		getLoading.mockReset();
		setLoading.mockReset().mockImplementation(async (value) => ({ load_tools_as_needed: value }));
		showError.mockReset();
	});

	it("labels the toggle and explains the trade-off", async () => {
		const w = await mountSettings();
		expect(w.find("label[for='load-tools-as-needed']").text()).toBe("Load tools as needed (recommended)");
		expect(w.text()).toContain(
			"FACO loads only the tools a conversation needs, which keeps answers faster and cheaper. Turn off to give FACO every tool on every message."
		);
	});

	it("shows the saved choice, on by default", async () => {
		expect((await mountSettings(true)).find("#load-tools-as-needed").element.checked).toBe(true);
		expect((await mountSettings(false)).find("#load-tools-as-needed").element.checked).toBe(false);
	});

	it("saves the choice when toggled", async () => {
		const w = await mountSettings(true);
		await w.find("#load-tools-as-needed").setValue(false);
		expect(setLoading).toHaveBeenLastCalledWith(false);
		expect(w.find("#load-tools-as-needed").element.checked).toBe(false);
		expect(w.text()).toContain("Saved");
	});

	it("puts the toggle back and says so when saving fails", async () => {
		setLoading.mockRejectedValue(new Error("nope"));
		const w = await mountSettings(true);
		await w.find("#load-tools-as-needed").setValue(false);
		await flushPromises();
		expect(w.find("#load-tools-as-needed").element.checked).toBe(true);
		expect(showError).toHaveBeenCalledWith("nope");
	});

	it("shows no toggle when the choice cannot be loaded", async () => {
		getLoading.mockRejectedValue(new Error("down"));
		const w = mount(ToolsSettings);
		await flushPromises();
		expect(w.find("#load-tools-as-needed").exists()).toBe(false);
		expect(w.find("[role=alert]").exists()).toBe(true);
	});
});
