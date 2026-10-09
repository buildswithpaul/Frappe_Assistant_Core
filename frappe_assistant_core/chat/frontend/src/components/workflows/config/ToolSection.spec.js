import { describe, it, expect } from "vitest";
import { mount, RouterLinkStub } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";
import ToolSection from "./ToolSection.vue";
import ToolPicker from "./ToolPicker.vue";

setActivePinia(createPinia());
const stubs = { global: { stubs: { RouterLink: RouterLinkStub } } };

describe("ToolSection", () => {
	it("links to Settings -> Connections when no server is connected", () => {
		const w = mount(ToolSection, { props: { discoveryState: "no-servers" }, ...stubs });
		expect(w.findComponent(RouterLinkStub).props("to")).toBe("/settings/connections");
		expect(w.text()).not.toContain("Workspace");
	});

	it("names a server that failed while others answered", () => {
		const w = mount(ToolSection, {
			props: {
				directives: [{ tool_name: "list_documents", server: "Main Frappe Site" }],
				toolsResult: { success: true, tools: [{ name: "x" }], errors: [{ server: "Brave", error: "timeout" }] },
			},
			...stubs,
		});
		expect(w.text()).toContain("Brave");
		expect(w.text()).toContain("timeout");
	});
});

describe("ToolPicker", () => {
	it("shows what each tool does", () => {
		const w = mount(ToolPicker, {
			props: {
				allTools: [
					{
						name: "S:list_documents",
						original_name: "list_documents",
						server: "S",
						description: "List records of a DocType",
					},
				],
				selectedToolKeys: new Set(),
				modelValue: true,
			},
		});
		expect(w.text()).toContain("List records of a DocType");
	});
});
