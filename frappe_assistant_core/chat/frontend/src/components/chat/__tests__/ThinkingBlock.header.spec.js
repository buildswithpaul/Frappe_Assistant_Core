import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import ThinkingBlock from "../ThinkingBlock.vue";

function header(content, extra = {}) {
	const wrapper = mount(ThinkingBlock, {
		props: { block: { id: "t1", content, isStreaming: false, isExpanded: false, ...extra } },
	});
	return wrapper.find(".thinking-summary");
}

describe("ThinkingBlock header", () => {
	it("shows a reasoning-summary title without its asterisks", () => {
		expect(header("**Assessing sales orders**\n\nCounting them.").text()).toBe("Assessing sales orders");
	});

	it("renders inline code in the header", () => {
		expect(header("Reading `Sales Order` fields").find("code").text()).toBe("Sales Order");
	});

	it("still says Thinking... while streaming", () => {
		expect(header("**Assessing**", { isStreaming: true }).text()).toBe("Thinking...");
	});
});
