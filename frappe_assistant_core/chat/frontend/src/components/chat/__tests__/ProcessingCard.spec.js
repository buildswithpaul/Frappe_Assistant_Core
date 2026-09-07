import { mount } from "@vue/test-utils";
import { describe, it, expect } from "vitest";
import ProcessingCard from "../ProcessingCard.vue";

// Live-bug repro: the card received one chronological `blocks` array and split
// it into two independent lists, grouped by kind, so a 26-tool turn read as a
// wall of rows in an order the work never happened in.
function mountCard(blocks) {
	return mount(ProcessingCard, {
		props: { blocks, isExpanded: true, isStreaming: false, messageIndex: 0 },
	});
}

const QUOTE = {
	type: "tool_call",
	id: "c1",
	tool_name: "create_document",
	input: { doctype: "Quotation" },
	status: "success",
	result: "ok",
};

const SUBMIT = {
	type: "tool_call",
	id: "c2",
	tool_name: "submit_document",
	input: { doctype: "Quotation" },
	status: "success",
	result: "ok",
};

describe("ProcessingCard chronology", () => {
	it("renders rows in the order the blocks arrived, not grouped by kind", () => {
		// A non-tool block has to sit BETWEEN the tools for this to bite —
		// grouping by kind preserves the relative order of the tools themselves,
		// so a tool-only fixture passes under the very bug this test names.
		const wrapper = mountCard([
			QUOTE,
			{ type: "thinking", id: "th1", content: "now submit it" },
			SUBMIT,
		]);

		const sequence = wrapper
			.findAll(".processing-stream > *")
			.map((n) =>
				n.find(".timeline-label").exists() ? n.find(".timeline-label").text() : "thinking"
			);

		expect(sequence).toEqual([
			"Prepared new record → Quotation",
			"thinking",
			"Prepared submission → Quotation",
		]);
	});

	it("still hides internal tool calls", () => {
		const wrapper = mountCard([
			{ ...QUOTE, id: "c9", tool_name: "get_skill", isInternal: true },
		]);

		expect(wrapper.findAll(".timeline-label")).toHaveLength(0);
	});
});

describe("ProcessingCard with nothing to show", () => {
	// Every block filtered out leaves the summary header as the only content.
	// An openable card whose body is empty reads as a broken control.
	it("offers no body or chevron when every tool is internal", () => {
		const wrapper = mountCard([
			{ ...QUOTE, id: "c9", tool_name: "get_skill", isInternal: true },
			{ ...QUOTE, id: "c10", tool_name: "workspace_read_file", isInternal: true },
		]);

		expect(wrapper.find(".processing-card-content").exists()).toBe(false);
		expect(wrapper.find(".processing-chevron").exists()).toBe(false);
		expect(wrapper.find(".processing-summary").exists()).toBe(true);

		// Not merely bodyless — not a control at all, so it is neither focusable
		// nor announced as a collapsed disclosure that opens nothing.
		const header = wrapper.find(".processing-card-header");
		expect(header.element.tagName).toBe("DIV");
		expect(header.attributes("aria-expanded")).toBeUndefined();
	});
});

describe("ProcessingCard tool rows", () => {
	// The Quiet Ledger spec (§3.2) mandates the touched record be emphasized so
	// the row is scannable; buildTimelineRows computed `target` but both
	// renderers flattened it back into one undifferentiated string.
	it("emphasises the record a tool touched", () => {
		const wrapper = mountCard([QUOTE]);

		const label = wrapper.find(".timeline-label");
		expect(label.find("strong").text()).toBe("Quotation");
		expect(label.text()).toBe("Prepared new record → Quotation");
	});

	it("shows tool I/O without repeating the tool header inside the drawer", async () => {
		const wrapper = mountCard([QUOTE]);
		await wrapper.find(".timeline-line").trigger("click");

		expect(wrapper.find(".timeline-drawer").exists()).toBe(true);
		expect(wrapper.find(".timeline-drawer .tool-header").exists()).toBe(false);
	});
});
