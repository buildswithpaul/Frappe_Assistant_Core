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

describe("ToolSection server failures", () => {
	const directives = [{ tool_name: "list_documents", server: "Main Frappe Site" }];
	const expired = { server: "Main Frappe Site", error: "x", error_code: "REFRESH_TOKEN_EXPIRED" };

	it("names an expired server and links to reconnect when tools are configured", () => {
		const w = mount(ToolSection, {
			props: {
				directives,
				discoveryState: "auth",
				toolsResult: { success: true, tools: [], errors: [expired] },
			},
			...stubs,
		});
		expect(w.text()).toContain("Main Frappe Site");
		expect(w.text()).toContain("sign-in expired");
		expect(w.findComponent(RouterLinkStub).props("to")).toBe("/settings/connections");
	});

	it("does not repeat an expired server under the reconnect empty state", () => {
		const w = mount(ToolSection, {
			props: {
				discoveryState: "auth",
				toolsResult: { success: true, tools: [], errors: [expired] },
			},
			...stubs,
		});
		expect(w.find(".server-failures").exists()).toBe(false);
	});

	it("omits the colon when a failure has no message", () => {
		const w = mount(ToolSection, {
			props: { directives, toolsResult: { success: true, tools: [{ name: "x" }], errors: [{ server: "Brave" }] } },
			...stubs,
		});
		expect(w.get(".server-failures").text()).toBe("Couldn't reach Brave. Its tools are missing from the list.");
	});

	it("does not claim every server failed when only some did", () => {
		const w = mount(ToolSection, {
			props: {
				discoveryState: "failed",
				toolsResult: { success: true, tools: [], errors: [{ server: "Brave", error: "timeout" }] },
			},
			...stubs,
		});
		expect(w.get(".tools-empty-state").text()).not.toContain("The MCP servers could not be reached");
	});

	it("renders two failures from the same server without key clashes", () => {
		const w = mount(ToolSection, {
			props: {
				directives,
				toolsResult: { success: true, tools: [{ name: "x" }], errors: [{ server: "B", error: "a" }, { server: "B", error: "b" }] },
			},
			...stubs,
		});
		expect(w.findAll(".server-failures li")).toHaveLength(2);
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
