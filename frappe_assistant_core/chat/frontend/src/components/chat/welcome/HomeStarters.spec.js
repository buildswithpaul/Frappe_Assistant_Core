import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import HomeStarters from "./HomeStarters.vue";

const heading = (area) => mount(HomeStarters, { props: { tiles: [], area } }).find(".hs-heading").text();

describe("HomeStarters heading", () => {
	it.each(["books", "pipeline", "stock", "team", "tickets", "business"])("names the %s area", (area) => {
		expect(heading(area)).toBe(`Ask about your ${area}`);
	});

	it("falls back to business for a missing or unknown area", () => {
		expect(heading(null)).toBe("Ask about your business");
		expect(heading("unmapped")).toBe("Ask about your business");
	});
});
