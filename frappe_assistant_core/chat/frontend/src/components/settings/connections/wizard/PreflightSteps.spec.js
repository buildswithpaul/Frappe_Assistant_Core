import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";
import PreflightSteps from "./PreflightSteps.vue";

const STEPS = [
	{ key: "url_shape", label: "URL shape", status: "pass", detail: "https, well formed", next_action: null },
	{ key: "reachable", label: "Reachable", status: "pass", detail: "Responded in 210 ms", next_action: null },
	{ key: "oauth_discovery", label: "OAuth discovery", status: "skipped", detail: "No auth advertised", next_action: null },
	{
		key: "speaks_mcp",
		label: "Speaks MCP",
		status: "fail",
		detail: "The server answered, but not with MCP.",
		next_action: "Check you pasted the MCP endpoint, not the site's home page.",
	},
];

const mountSteps = (props) => mount(PreflightSteps, { props: { steps: STEPS, ...props } });

describe("PreflightSteps", () => {
	it("draws nothing before the container reveals anything", () => {
		const w = mountSteps({ revealed: 0 });
		expect(w.findAll('[data-test="preflight-step"]')).toHaveLength(0);
	});

	it("draws only the rows revealed so far", () => {
		const w = mountSteps({ revealed: 2 });
		const rows = w.findAll('[data-test="preflight-step"]');
		expect(rows).toHaveLength(2);
		expect(rows[0].text()).toContain("URL shape");
		expect(rows[1].text()).toContain("Reachable");
	});

	it("every drawn row already carries a verdict — never a pending placeholder", () => {
		const w = mountSteps({ revealed: STEPS.length });
		for (const row of w.findAll('[data-test="preflight-step"]')) {
			const status = row.find('[data-test="preflight-mark"]').attributes("data-status");
			expect(["pass", "fail", "skipped"]).toContain(status);
		}
	});

	it("a skipped step says skipped rather than looking like a pass", () => {
		const w = mountSteps({ revealed: STEPS.length });
		const skipped = w
			.findAll('[data-test="preflight-step"]')
			.find((r) => r.text().includes("OAuth discovery"));
		expect(skipped.classes()).toContain("is-skipped");
		expect(skipped.text()).toMatch(/skipped/i);
	});

	it("a failure shows its concrete next action", () => {
		const w = mountSteps({ revealed: STEPS.length });
		expect(w.find('[data-test="next-action"]').text()).toContain(
			"Check you pasted the MCP endpoint"
		);
	});

	it("shows a single running line while work is outstanding", () => {
		const w = mountSteps({ revealed: 1, running: true });
		expect(w.find('[data-test="preflight-running"]').exists()).toBe(true);
	});

	it("drops the running line once the check is done", () => {
		const w = mountSteps({ revealed: STEPS.length, running: false });
		expect(w.find('[data-test="preflight-running"]').exists()).toBe(false);
	});
});
