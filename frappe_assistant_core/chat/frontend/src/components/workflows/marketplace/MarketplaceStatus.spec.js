import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import MarketplaceStatus from "@/components/workflows/marketplace/MarketplaceStatus.vue";

describe("MarketplaceStatus", () => {
	it("shows an outage with Retry instead of 'No templates available yet'", async () => {
		const w = mount(MarketplaceStatus, { props: { empty: true, error: "templates down" } });
		expect(w.text()).toContain("templates down");
		expect(w.text()).not.toContain("No templates available yet");
		await w.get('[role="alert"] button').trigger("click");
		expect(w.emitted("retry")).toHaveLength(1);
	});

	// regression guard: the empty copy existed before this change
	it("distinguishes a filtered-empty from a truly empty marketplace", () => {
		expect(mount(MarketplaceStatus, { props: { empty: true } }).text()).toContain(
			"No templates available yet",
		);
		expect(
			mount(MarketplaceStatus, { props: { empty: true, filtered: true } }).text(),
		).toContain("No templates match your search");
	});
});
