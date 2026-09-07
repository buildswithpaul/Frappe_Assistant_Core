import { mount } from "@vue/test-utils";
import { describe, it, expect } from "vitest";
import StepsBlock from "./StepsBlock.vue";

// Live-bug repro: the model writes prose sections inside a `steps` fence, so
// step lines routinely carry block-level markdown — `## Heading` most of all.
// `marked.parseInline` ignores block constructs by design, so the SPA printed
// the literal "## One deal, many jobs" while the widget, which runs the same
// text through a full markdown parse, showed a heading.
function stepHtml(body) {
	const wrapper = mount(StepsBlock, { props: { body } });
	return wrapper.findAll(".step-content").map((el) => el.html());
}

describe("StepsBlock markdown", () => {
	it("renders a heading line as a heading, not literal hashes", () => {
		const [html] = stepHtml("## One deal, many jobs");
		expect(html).toContain("<h2");
		expect(html).not.toContain("##");
	});

	it("still renders inline markdown inside a step", () => {
		const [html] = stepHtml("Ship **before** you `bill`");
		expect(html).toContain("<strong>before</strong>");
		expect(html).toContain("<code>bill</code>");
	});

	it("keeps one step per line and strips numbered prefixes", () => {
		const steps = stepHtml("1. Quote\n\n2. Order\n3. Invoice");
		expect(steps).toHaveLength(3);
		expect(steps[0]).toContain("Quote");
		expect(steps[0]).not.toContain("1.");
	});
});
