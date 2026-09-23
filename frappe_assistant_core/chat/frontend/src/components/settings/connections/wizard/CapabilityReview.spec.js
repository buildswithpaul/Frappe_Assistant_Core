import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";
import CapabilityReview from "./CapabilityReview.vue";

const CAPS = {
	tools: [
		{ name: "create_task", description: "Create a task in the default project." },
		{ name: "search_tasks", description: "Full-text search across every task you can see." },
	],
	resources: [{ name: "task://recent" }],
	prompts: [{ name: "weekly_review" }],
	capabilities: { tools: {}, resources: {}, prompts: {} },
	tool_count: 14,
	est_tokens: 3200,
};

const mountReview = (props = {}) =>
	mount(CapabilityReview, {
		props: { capabilities: CAPS, suggestedName: "Acme Tasks", existingNames: [], ...props },
	});

describe("CapabilityReview", () => {
	it("states the context cost in tools", () => {
		const w = mountReview();
		expect(w.find('[data-test="context-cost"]').text()).toBe(
			"Adds 14 tools to every conversation."
		);
	});

	it("never shows a raw token figure", () => {
		// FAC prices everything to users in credits, and a token count is not a
		// unit anyone choosing a connection reasons in. Tools are.
		const w = mountReview();
		expect(w.text()).not.toMatch(/token/i);
		expect(w.text()).not.toContain("3,200");
	});

	it("says tool, singular, for a one-tool server", () => {
		const w = mountReview({ capabilities: { ...CAPS, tool_count: 1, est_tokens: 240 } });
		expect(w.find('[data-test="context-cost"]').text()).toContain("Adds 1 tool ");
	});

	it("falls back to the tool array length when tool_count is absent", () => {
		const w = mountReview({
			capabilities: { ...CAPS, tool_count: undefined },
		});
		expect(w.find('[data-test="context-cost"]').text()).toContain("Adds 2 tools");
	});

	it("keeps a real tool_count of zero instead of falling back to the tools array", () => {
		const w = mountReview({ capabilities: { ...CAPS, tool_count: 0 } });
		expect(w.find('[data-test="context-cost"]').text()).toContain("Adds 0 tools");
	});

	it("lists every tool with its description collapsed", () => {
		const w = mountReview();
		const rows = w.findAll('[data-test="tool-row"]');
		expect(rows).toHaveLength(2);
		expect(w.find('[data-test="tool-description"]').exists()).toBe(false);
	});

	it("expands one tool's description on click", async () => {
		const w = mountReview();
		await w.findAll('[data-test="tool-toggle"]')[0].trigger("click");
		expect(w.find('[data-test="tool-description"]').text()).toContain(
			"Create a task in the default project."
		);
	});

	it("counts resources and prompts", () => {
		const w = mountReview();
		expect(w.find('[data-test="resource-count"]').text()).toContain("1");
		expect(w.find('[data-test="prompt-count"]').text()).toContain("1");
	});

	it("pre-fills the name from initialize", () => {
		const w = mountReview();
		expect(w.find('[data-test="server-name"]').element.value).toBe("Acme Tasks");
	});

	it("emits the trimmed name on add", async () => {
		const w = mountReview();
		await w.find('[data-test="server-name"]').setValue("  Acme Tasks  ");
		await w.find('[data-test="add"]').trigger("click");
		expect(w.emitted("add")[0][0]).toEqual({ server_name: "Acme Tasks" });
	});

	it("refuses an empty name", async () => {
		const w = mountReview();
		await w.find('[data-test="server-name"]').setValue("   ");
		await w.find('[data-test="add"]').trigger("click");
		expect(w.emitted("add")).toBeUndefined();
		expect(w.find('[data-test="review-error"]').text()).toMatch(/name/i);
	});

	it("refuses the reserved managed name", async () => {
		const w = mountReview();
		await w.find('[data-test="server-name"]').setValue("Main Frappe Site");
		await w.find('[data-test="add"]').trigger("click");
		expect(w.emitted("add")).toBeUndefined();
		expect(w.find('[data-test="review-error"]').text()).toContain("Main Frappe Site");
	});

	it("refuses a name already in use", async () => {
		const w = mountReview({ existingNames: ["Acme Tasks"] });
		await w.find('[data-test="add"]').trigger("click");
		expect(w.emitted("add")).toBeUndefined();
		expect(w.find('[data-test="review-error"]').text()).toContain("already have");
	});

	it("disables Add while the container is saving", () => {
		const w = mountReview({ saving: true });
		expect(w.find('[data-test="add"]').attributes("disabled")).toBeDefined();
	});
});

describe("CapabilityReview when the probe got no answer", () => {
	// Slack answers tools/list with HTTP 400 and "App is not enabled for Slack
	// MCP server access. Please enable it here: <url>". AR now carries that
	// sentence through as `error` with `measured: false`.
	const SLACK_REFUSAL =
		"MCP error from Slack Mcp: App is not enabled for Slack MCP server access. " +
		"Please enable it here: https://api.slack.com/apps/A0C29SGT6LR/app-assistant";

	const refused = {
		tools: [],
		resources: [],
		prompts: [],
		capabilities: {},
		tool_count: 0,
		measured: false,
		error: SLACK_REFUSAL,
	};

	it("does not claim the server exposes no tools", () => {
		// That is a statement about the server. We never heard from it.
		const w = mountReview({ capabilities: refused });
		expect(w.text()).not.toContain("This server exposes no tools.");
	});

	it("says it could not read them, and why", () => {
		const w = mountReview({ capabilities: refused });
		expect(w.find('[data-test="probe-failed"]').exists()).toBe(true);
		expect(w.find('[data-test="probe-error"]').text()).toBe(SLACK_REFUSAL);
	});

	it("still says nothing when the server genuinely has none", () => {
		const w = mountReview({
			capabilities: { ...refused, measured: true, error: null },
		});
		expect(w.text()).toContain("This server exposes no tools.");
		expect(w.find('[data-test="probe-failed"]').exists()).toBe(false);
	});

	it("keeps quiet about a reason it was not given", () => {
		const w = mountReview({ capabilities: { ...refused, error: null } });
		expect(w.find('[data-test="probe-failed"]').exists()).toBe(true);
		expect(w.find('[data-test="probe-error"]').exists()).toBe(false);
	});

	it("leaves an older payload with no `measured` key alone", () => {
		// AR rows probed before this shipped carry neither field.
		const w = mountReview({ capabilities: { ...CAPS, tools: [], tool_count: 0 } });
		expect(w.text()).toContain("This server exposes no tools.");
	});
});
