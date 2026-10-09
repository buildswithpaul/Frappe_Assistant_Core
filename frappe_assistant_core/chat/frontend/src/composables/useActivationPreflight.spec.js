import { describe, it, expect, vi, beforeEach } from "vitest";
import { ref } from "vue";

const resolveWorkflowTools = vi.fn();
vi.mock("@/api/client", () => ({
	api: { workflows: { resolveWorkflowTools: (...a) => resolveWorkflowTools(...a) } },
}));

import { collectDirectives, useActivationPreflight } from "./useActivationPreflight";

const makeNodes = () =>
	ref([
		{
			id: "a",
			type: "agent",
			data: {
				label: "Draft reply",
				config: { tool_directives: [{ tool_name: "create_document", server: "Main Frappe Site" }] },
			},
		},
		{
			id: "t",
			type: "tool",
			data: { label: "Fetch AR", config: { tool_name: "generate_report", server: "Main Frappe Site" } },
		},
		{
			id: "l",
			type: "loop",
			data: { label: "Per customer", config: { tool_directives: [{ tool_name: "send_email" }] } },
		},
		{ id: "c", type: "condition", data: { label: "If", config: {} } },
	]);

const build = (overrides = {}) =>
	useActivationPreflight({
		nodes: makeNodes(),
		currentWorkflow: ref({ default_user_id: "ops@example.com" }),
		isAdmin: ref(true),
		...overrides,
	});

describe("collectDirectives", () => {
	it("gathers agent, loop and tool-node tools with their node labels and runtime user", () => {
		const found = collectDirectives(makeNodes().value, "ops@example.com");
		expect(found.map((d) => [d.tool_name, d.node_label, d.user])).toEqual([
			["create_document", "Draft reply", "ops@example.com"],
			["generate_report", "Fetch AR", "ops@example.com"],
			["send_email", "Per customer", "ops@example.com"],
		]);
	});

	it("lets a node's own user_id override the workflow default", () => {
		const nodes = [
			{
				id: "a",
				type: "agent",
				data: { label: "A", config: { user_id: "x@example.com", tool_directives: [{ tool_name: "t" }] } },
			},
		];
		expect(collectDirectives(nodes, "ops@example.com")[0].user).toBe("x@example.com");
	});
});

describe("useActivationPreflight", () => {
	beforeEach(() => {
		resolveWorkflowTools.mockReset();
	});

	it("warns only about resolved tools that will not run unattended", async () => {
		resolveWorkflowTools.mockResolvedValue({
			resolved: [
				{ tool_name: "create_document", server: "Main Frappe Site", status: "resolved", runs_unattended: false },
				{ tool_name: "generate_report", server: "Main Frappe Site", status: "resolved", runs_unattended: true },
				{ tool_name: "send_email", status: "resolved", runs_unattended: false },
			],
		});
		const p = build();
		const warnings = await p.check();
		expect(warnings.map((w) => [w.tool, w.nodes])).toEqual([
			["create_document", ["Draft reply"]],
			["send_email", ["Per customer"]],
		]);
		const [sent, user] = resolveWorkflowTools.mock.calls[0];
		expect(user).toBe("ops@example.com");
		expect(sent.every((d) => !("node_label" in d) && !("user" in d))).toBe(true);
	});

	it("gives no warning for a tool that did not resolve", async () => {
		resolveWorkflowTools.mockResolvedValue({
			resolved: [{ tool_name: "create_document", server: "Main Frappe Site", status: "missing", runs_unattended: false }],
		});
		expect(await build().check()).toEqual([]);
	});

	it("does not warn when the server says nothing about approval", async () => {
		resolveWorkflowTools.mockResolvedValue({ resolved: [{ tool_name: "create_document", status: "resolved" }] });
		expect(await build().check()).toEqual([]);
	});

	it("makes one resolve call per distinct runtime user", async () => {
		const nodes = ref([
			{ id: "a", type: "agent", data: { label: "A", config: { tool_directives: [{ tool_name: "t1" }] } } },
			{ id: "b", type: "agent", data: { label: "B", config: { tool_directives: [{ tool_name: "t2" }] } } },
			{
				id: "c",
				type: "agent",
				data: { label: "C", config: { user_id: "other@example.com", tool_directives: [{ tool_name: "t3" }] } },
			},
		]);
		resolveWorkflowTools.mockImplementation(async (directives, user) => ({
			resolved: directives.map((d) => ({
				tool_name: d.tool_name,
				status: "resolved",
				runs_unattended: user !== "other@example.com",
			})),
		}));
		const warnings = await build({ nodes }).check();
		expect(resolveWorkflowTools).toHaveBeenCalledTimes(2);
		expect(resolveWorkflowTools.mock.calls.map(([d, u]) => [d.map((x) => x.tool_name), u])).toEqual([
			[["t1", "t2"], "ops@example.com"],
			[["t3"], "other@example.com"],
		]);
		expect(warnings.map((w) => [w.tool, w.user])).toEqual([["t3", "other@example.com"]]);
	});

	it("sends no runtime user for a non-admin", async () => {
		resolveWorkflowTools.mockResolvedValue({ resolved: [] });
		await build({ isAdmin: ref(false) }).check();
		expect(resolveWorkflowTools.mock.calls[0][1]).toBeNull();
	});

	it("does not call the server when the graph has no tools", async () => {
		const p = build({ nodes: ref([{ id: "c", type: "condition", data: { config: {} } }]) });
		expect(await p.check()).toEqual([]);
		expect(resolveWorkflowTools).not.toHaveBeenCalled();
		expect(p.checked.value).toBe(true);
	});

	it("does not block on a failed check", async () => {
		resolveWorkflowTools.mockRejectedValue(new Error("down"));
		const p = build();
		expect(await p.check()).toEqual([]);
		expect(p.error.value).toBe("down");
	});

	it("clears a previous success when a later check fails", async () => {
		resolveWorkflowTools.mockResolvedValueOnce({ resolved: [] });
		const p = build();
		await p.check();
		expect(p.checked.value).toBe(true);
		resolveWorkflowTools.mockRejectedValueOnce(new Error("down"));
		await p.check();
		expect(p.checked.value).toBe(false);
		expect(p.error.value).toBe("down");
	});

	it("keeps one user's warnings when another user's resolve fails", async () => {
		const nodes = ref([
			{ id: "a", type: "agent", data: { label: "A", config: { tool_directives: [{ tool_name: "t1" }] } } },
			{
				id: "c",
				type: "agent",
				data: { label: "C", config: { user_id: "other@example.com", tool_directives: [{ tool_name: "t3" }] } },
			},
		]);
		resolveWorkflowTools.mockImplementation(async (directives, user) => {
			if (user === "other@example.com") throw new Error("down");
			return { resolved: [{ tool_name: "t1", status: "resolved", runs_unattended: false }] };
		});
		const p = build({ nodes });
		const warnings = await p.check();
		expect(warnings.map((w) => w.tool)).toEqual(["t1"]);
		expect(p.error.value).toBe("down");
		expect(p.checked.value).toBe(false);
	});

	it("reads the server from server_name and keeps a pinned warning off another server", async () => {
		const nodes = ref([
			{
				id: "a",
				type: "agent",
				data: { label: "On site A", config: { tool_directives: [{ tool_name: "send_email", server: "A" }] } },
			},
			{
				id: "b",
				type: "agent",
				data: { label: "On site B", config: { tool_directives: [{ tool_name: "send_email", server: "B" }] } },
			},
		]);
		resolveWorkflowTools.mockResolvedValue({
			resolved: [
				{ tool_name: "send_email", server_name: "A", status: "resolved", runs_unattended: false },
				{ tool_name: "send_email", server_name: "B", status: "resolved", runs_unattended: true },
			],
		});
		const warnings = await build({ nodes }).check();
		expect(warnings.map((w) => [w.server, w.nodes])).toEqual([["A", ["On site A"]]]);
	});
});
