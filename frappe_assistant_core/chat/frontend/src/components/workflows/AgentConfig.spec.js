import { describe, it, expect, beforeEach, vi } from "vitest";
import { mount } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";
import { reactive, nextTick } from "vue";

const resolveWorkflowTools = vi.fn();

vi.mock("@/api/client", () => ({
	api: {
		workflows: { resolveWorkflowTools: (...args) => resolveWorkflowTools(...args) },
	},
}));

import AgentConfig from "@/components/workflows/AgentConfig.vue";

// Exactly the shape AR's api/tools.py:list_tools returns: bare original_name,
// server-prefixed name.
const LIST_DOCUMENTS = {
	name: "Main Frappe Site:list_documents",
	original_name: "list_documents",
	server: "Main Frappe Site",
	description: "List documents",
};

function mountConfig(config = {}, props = {}) {
	const reactiveConfig = reactive({
		system_prompt: "",
		model_id: "",
		user_id: "",
		mcp_servers: [],
		tool_directives: [],
		...config,
	});
	const wrapper = mount(AgentConfig, {
		props: {
			config: reactiveConfig,
			nodeId: "agent_1",
			allTools: [LIST_DOCUMENTS],
			toolsResult: { success: true, tools: [LIST_DOCUMENTS], servers_queried: ["Main Frappe Site"] },
			models: [
				{ model_id: "m-fast", display_name: "Fast", tier: "Standard", tier_rank: 1 },
				{ model_id: "m-smart", display_name: "Smart", tier: "Premium", tier_rank: 2 },
			],
			...props,
		},
	});
	return { wrapper, config: reactiveConfig };
}

describe("AgentConfig", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
		resolveWorkflowTools.mockReset();
		resolveWorkflowTools.mockResolvedValue({ resolved: [], all_tools_available: true });
	});

	it("writes the bare tool name the engine resolves against", async () => {
		const { wrapper, config } = mountConfig();
		wrapper.findComponent({ name: "ToolSection" }).vm.$emit("add", LIST_DOCUMENTS);
		await nextTick();

		expect(config.tool_directives).toHaveLength(1);
		expect(config.tool_directives[0].tool_name).toBe("list_documents");
		expect(config.tool_directives[0].capability).toBe("list_documents");
	});

	it("scopes the node to the tool's MCP server", async () => {
		const { wrapper, config } = mountConfig();
		wrapper.findComponent({ name: "ToolSection" }).vm.$emit("add", LIST_DOCUMENTS);
		await nextTick();
		expect(config.mcp_servers).toEqual(["Main Frappe Site"]);
	});

	it("never narrows mcp_servers to [] when the tool inventory failed to load", async () => {
		const { wrapper, config } = mountConfig(
			{ mcp_servers: ["Main Frappe Site"], tool_directives: [{ tool_name: "list_documents" }] },
			{ allTools: [], toolsResult: { success: false, tools: [] } }
		);
		wrapper.findComponent({ name: "ToolSection" }).vm.$emit("remove", 0);
		await nextTick();
		expect(config.mcp_servers).toEqual(["Main Frappe Site"]);
	});

	it("heals a directive saved with the server-prefixed name", async () => {
		const { config } = mountConfig({
			tool_directives: [
				{ tool_name: "Main Frappe Site:list_documents", capability: "list_documents" },
			],
		});
		await nextTick();
		expect(config.tool_directives[0].tool_name).toBe("list_documents");
	});

	it("resolves the configured tools against the runtime user on mount", async () => {
		mountConfig({ tool_directives: [{ tool_name: "list_documents" }] });
		await nextTick();
		expect(resolveWorkflowTools).toHaveBeenCalledWith([{ tool_name: "list_documents" }]);
	});

	it("does not call the admin-only resolver for a read-only viewer", async () => {
		mountConfig({ tool_directives: [{ tool_name: "list_documents" }] }, { readonly: true });
		await nextTick();
		expect(resolveWorkflowTools).not.toHaveBeenCalled();
	});

	it("groups models by tier and labels them by display_name", () => {
		const { wrapper } = mountConfig();
		const groups = wrapper.findAll("optgroup");
		expect(groups.map((g) => g.attributes("label"))).toEqual(["Standard", "Premium"]);
		expect(wrapper.text()).toContain("Fast");
		expect(wrapper.text()).toContain("Smart");
	});

	it("exposes the memory + team instructions toggle", async () => {
		const { wrapper, config } = mountConfig();
		const checkbox = wrapper.find('input[type="checkbox"]');
		await checkbox.setValue(true);
		expect(config.use_memory).toBe(true);
	});

	it("exposes required as a real per-tool checkbox", async () => {
		const { wrapper, config } = mountConfig({
			tool_directives: [{ tool_name: "list_documents", required: false }],
		});
		wrapper.findComponent({ name: "ToolSection" }).vm.$emit("toggle-required", 0, true);
		await nextTick();
		expect(config.tool_directives[0].required).toBe(true);
	});
});
