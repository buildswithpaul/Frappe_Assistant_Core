import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import RunNodeDetail from "@/components/workflows/RunNodeDetail.vue";

const NODE_RUN = {
	node_id: "fetch_history",
	node_label: "Fetch Customer Invoice History",
	node_type: "agent",
	status: "Completed",
	duration_ms: 5311,
	model_id: "claude-haiku-4-5",
	tokens_used: 1234,
	credits_used: 0.42,
	tool_calls_count: 1,
	input_text: '{"trigger": {"doctype": "Sales Invoice"}}',
	output_text: "**2 overdue** invoices found",
};

describe("RunNodeDetail", () => {
	it("shows a truncated preview when collapsed", () => {
		const wrapper = mount(RunNodeDetail, { props: { nodeRun: NODE_RUN } });
		expect(wrapper.find(".preview-output").text()).toContain("overdue");
		expect(wrapper.find(".io-output").exists()).toBe(false);
	});

	it("expands to rendered markdown output on click", async () => {
		const wrapper = mount(RunNodeDetail, { props: { nodeRun: NODE_RUN } });
		await wrapper.find(".node-row").trigger("click");
		const output = wrapper.find(".io-output");
		expect(output.exists()).toBe(true);
		expect(output.html()).toContain("<strong>2 overdue</strong>");
	});

	it("reveals input only behind the toggle", async () => {
		const wrapper = mount(RunNodeDetail, { props: { nodeRun: NODE_RUN } });
		await wrapper.find(".node-row").trigger("click");
		expect(wrapper.find(".io-input").exists()).toBe(false);
		await wrapper.find(".input-toggle").trigger("click");
		expect(wrapper.find(".io-input").text()).toContain("Sales Invoice");
	});

	it("shows the truncation note when the server capped the output", async () => {
		const wrapper = mount(RunNodeDetail, {
			props: { nodeRun: { ...NODE_RUN, output_text_truncated: true } },
		});
		await wrapper.find(".node-row").trigger("click");
		expect(wrapper.find(".truncated-note").text()).toContain("truncated");
	});

	it("shows the full error when expanded on a failed node", async () => {
		const wrapper = mount(RunNodeDetail, {
			props: {
				nodeRun: {
					...NODE_RUN,
					status: "Failed",
					output_text: null,
					error_message: "Tool 'send_email' not available on this server",
				},
			},
		});
		expect(wrapper.find(".preview-error").exists()).toBe(true);
		await wrapper.find(".node-row").trigger("click");
		expect(wrapper.find(".full-error").text()).toContain("send_email");
	});

	it("renders meta: duration, model, tokens, credits, tool calls", () => {
		const wrapper = mount(RunNodeDetail, { props: { nodeRun: NODE_RUN } });
		const meta = wrapper.find(".node-meta").text();
		expect(meta).toContain("5.3s");
		expect(meta).toContain("claude-haiku-4-5");
		expect(meta).toContain("1234 tok");
		expect(meta).toContain("0.42 credits");
		expect(meta).toContain("1 tool call");
	});
});
