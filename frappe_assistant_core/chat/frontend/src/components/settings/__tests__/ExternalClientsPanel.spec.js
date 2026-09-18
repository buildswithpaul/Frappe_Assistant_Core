import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";
import ExternalClientsPanel from "@/components/settings/connections/ExternalClientsPanel.vue";

describe("ExternalClientsPanel", () => {
	it("renders the endpoint url", () => {
		const w = mount(ExternalClientsPanel, {
			props: { endpointUrl: "https://s.example.com/mcp" },
		});
		expect(w.text()).toContain("https://s.example.com/mcp");
	});

	it("never frames itself as adding a connection", () => {
		const w = mount(ExternalClientsPanel, {
			props: { endpointUrl: "https://s.example.com/mcp" },
		});
		expect(w.text().toLowerCase()).not.toMatch(/add (this|a) connection/);
	});

	it("copies the url to the clipboard", async () => {
		const writeText = vi.fn().mockResolvedValue();
		vi.stubGlobal("navigator", { clipboard: { writeText } });
		const w = mount(ExternalClientsPanel, {
			props: { endpointUrl: "https://s.example.com/mcp" },
		});
		await w.find('[data-test="copy"]').trigger("click");
		expect(writeText).toHaveBeenCalledWith("https://s.example.com/mcp");
	});

	it("renders nothing without an endpoint url", () => {
		const w = mount(ExternalClientsPanel, { props: { endpointUrl: "" } });
		expect(w.find('[data-test="copy"]').exists()).toBe(false);
	});
});
