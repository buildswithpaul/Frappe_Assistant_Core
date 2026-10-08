import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import SpotlightCard from "./SpotlightCard.vue";

const content = {
	id: "n1",
	kind: "announcement",
	eyebrow: "New",
	title: "Ask FACO anything",
	body: "Reads your **live** data.",
	highlights: ["Who owes us most?", "Summarise last month"],
	primary: { label: "Try now" },
	secondary: { label: "Not now" },
};

describe("SpotlightCard", () => {
	it("renders nothing without content", () => {
		expect(mount(SpotlightCard, { props: { content: null } }).html()).toBe("<!--v-if-->");
	});

	it("shows the announcement inline as a region, not a modal dialog", () => {
		const w = mount(SpotlightCard, { props: { content } });
		const card = w.find("[data-test='spotlight-card']");
		expect(card.attributes("role")).toBe("region");
		expect(card.attributes("aria-modal")).toBeUndefined();
		expect(w.text()).toContain("Ask FACO anything");
		expect(w.findAll("[data-test='spotlight-highlight']")).toHaveLength(2);
		expect(w.find(".spot-body strong").text()).toBe("live");
	});

	it("emits the same actions as the modal", async () => {
		const w = mount(SpotlightCard, { props: { content } });
		await w.find("[data-test='spotlight-primary']").trigger("click");
		await w.find("[data-test='spotlight-secondary']").trigger("click");
		await w.find("[data-test='spotlight-dismiss']").trigger("click");
		expect(Object.keys(w.emitted())).toEqual(expect.arrayContaining(["primary", "secondary", "dismiss"]));
	});

	it("keeps the quota art for a quota moment", () => {
		const w = mount(SpotlightCard, {
			props: { content: { ...content, kind: "quota", threshold: 80, media: { art: "quota" } } },
		});
		expect(w.findComponent({ name: "SpotlightQuotaArt" }).exists()).toBe(true);
	});
});
