import { describe, it, expect, beforeEach, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

const listTools = vi.fn();
const resolveWorkflowTools = vi.fn();
const runNode = vi.fn();

vi.mock("@/api/client", () => ({
	api: {
		user: { listTools: (...a) => listTools(...a) },
		models: { getAvailable: vi.fn().mockResolvedValue({ models: [] }) },
		workflows: {
			resolveWorkflowTools: (...a) => resolveWorkflowTools(...a),
			runNode: (...a) => runNode(...a),
		},
	},
}));

import NodeConfigPanel from "./NodeConfigPanel.vue";
import { useUserStore } from "@/stores/userStore";
import { useWorkflowStore } from "@/stores/workflowStore";
import NodeRunSection from "./NodeRunSection.vue";
import { getDefaultConfig } from "./graphUtils";

const node = (type, config = {}) => ({
	id: `${type}_1`,
	type,
	data: { label: `My ${type}`, config: { ...getDefaultConfig(type), ...config } },
});

function mountPanel(n, { admin = false } = {}) {
	// Production reaches isAdmin through userStore.loadUser (can_use_faco -> is_admin);
	// the store has no other writer, so the test sets the same ref.
	useUserStore().isAdmin = admin;
	// currentWorkflow is the document the builder loaded; default_user_id is its "Runs as".
	useWorkflowStore().currentWorkflow = { name: "WF-1", default_user_id: "ops@example.com" };
	return mount(NodeConfigPanel, { props: { node: n } });
}

describe("NodeConfigPanel", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
		listTools.mockReset().mockResolvedValue({ success: true, tools: [] });
		resolveWorkflowTools.mockReset().mockResolvedValue({ resolved: [] });
	});

	it("routes a tool node to the tool form", async () => {
		const w = mountPanel(node("tool"));
		await flushPromises();
		expect(w.findComponent({ name: "ToolNodeConfig" }).exists()).toBe(true);
		expect(w.findComponent({ name: "AgentConfig" }).exists()).toBe(false);
	});

	it("routes a loop node to the loop form, which embeds the agent form", async () => {
		const w = mountPanel(node("loop"));
		await flushPromises();
		expect(w.findComponent({ name: "LoopNodeConfig" }).exists()).toBe(true);
		expect(w.findComponent({ name: "AgentConfig" }).exists()).toBe(true);
	});

	it("renames the node from the header", async () => {
		const w = mountPanel(node("tool"));
		const input = w.get(".label-input");
		await input.setValue("Fetch receivables");
		await input.trigger("blur");
		expect(w.emitted("update").at(-1)).toEqual(["tool_1", { label: "Fetch receivables" }]);
	});

	it("an admin previews the tools of the workflow's runs-as user", async () => {
		mountPanel(node("agent"), { admin: true });
		await flushPromises();
		expect(listTools).toHaveBeenCalledWith("ops@example.com");
	});

	it("the node's own user override wins over the workflow's", async () => {
		mountPanel(node("agent", { user_id: "sales@example.com" }), { admin: true });
		await flushPromises();
		expect(listTools).toHaveBeenCalledWith("sales@example.com");
	});

	it("re-resolves directives against the runs-as user once the viewer turns out to be an admin", async () => {
		const userStore = useUserStore();
		const w = mountPanel(node("agent", { tool_directives: [{ tool_name: "x" }] }));
		await flushPromises();
		expect(resolveWorkflowTools).toHaveBeenLastCalledWith([{ tool_name: "x" }], null);

		userStore.isAdmin = true;
		await flushPromises();
		expect(resolveWorkflowTools).toHaveBeenLastCalledWith([{ tool_name: "x" }], "ops@example.com");
		w.unmount();
	});

	it("loads the new node's tools at once on a node switch, debouncing only user_id typing", async () => {
		vi.useFakeTimers();
		try {
			const a = node("agent", { user_id: "a@example.com" });
			const b = { ...node("agent", { user_id: "b@example.com" }), id: "agent_2" };
			const w = mountPanel(a, { admin: true });
			await flushPromises();
			listTools.mockClear();

			await w.setProps({ node: b });
			await flushPromises();
			expect(listTools).toHaveBeenCalledWith("b@example.com");

			listTools.mockClear();
			await w.setProps({
				node: { ...b, data: { ...b.data, config: { ...b.data.config, user_id: "c@example.com" } } },
			});
			expect(listTools).not.toHaveBeenCalled();
			await vi.advanceTimersByTimeAsync(500);
			expect(listTools).toHaveBeenCalledWith("c@example.com");
		} finally {
			vi.useRealTimers();
		}
	});

	it("a burst of user_id typing resolves directives once, with the final value, after the debounce", async () => {
		vi.useFakeTimers();
		try {
			const base = node("agent", { tool_directives: [{ tool_name: "x" }] });
			const w = mountPanel(base, { admin: true });
			await flushPromises();
			resolveWorkflowTools.mockClear();

			for (const typed of ["s", "sa", "sales@example.com"]) {
				await w.setProps({
					node: { ...base, data: { ...base.data, config: { ...base.data.config, user_id: typed } } },
				});
				await vi.advanceTimersByTimeAsync(100);
			}
			expect(resolveWorkflowTools).not.toHaveBeenCalled();

			await vi.advanceTimersByTimeAsync(500);
			expect(resolveWorkflowTools).toHaveBeenCalledTimes(1);
			expect(resolveWorkflowTools).toHaveBeenCalledWith([{ tool_name: "x" }], "sales@example.com");
		} finally {
			vi.useRealTimers();
		}
	});

	it("a second tool node shows its own arguments, not the previous node's broken text", async () => {
		const a = { ...node("tool"), id: "tool_a" };
		const b = {
			...node("tool", { arguments: { report_name: "AR" } }),
			id: "tool_b",
		};
		const w = mountPanel(a);
		await flushPromises();
		await w.get('[data-test="tool-arguments"]').setValue("{ broken");
		expect(w.text()).toContain("Not valid JSON");

		await w.setProps({ node: b });
		await flushPromises();
		expect(w.text()).not.toContain("Not valid JSON");
		expect(w.get('[data-test="tool-arguments"]').element.value).toContain("report_name");
	});

	it("a non-admin never names a user", async () => {
		mountPanel(node("agent", { user_id: "sales@example.com", tool_directives: [{ tool_name: "x" }] }));
		await flushPromises();
		expect(listTools).toHaveBeenCalledWith(null);
		expect(resolveWorkflowTools).toHaveBeenCalledWith([{ tool_name: "x" }], null);
	});

	it("a single-node run never names the person at the keyboard", async () => {
		runNode.mockReset().mockResolvedValue({ status: "Completed" });
		// userStore.user is what loadUser sets from the session; the run must ignore it.
		const w = mountPanel(node("transform", { user_id: "sales@example.com" }), { admin: true });
		useUserStore().user = "admin@example.com";
		await flushPromises();
		await w.findComponent(NodeRunSection).props("runNode")("transform_1", "hi");
		expect(runNode).toHaveBeenCalledWith("WF-1", "transform_1", "hi");
		expect(runNode.mock.calls[0]).toHaveLength(3);
	});
});
