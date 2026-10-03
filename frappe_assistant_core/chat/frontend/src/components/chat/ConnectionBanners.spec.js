import { describe, it, expect } from "vitest";
import { mount, RouterLinkStub } from "@vue/test-utils";
import ConnectionBanners from "./ConnectionBanners.vue";

const AR_TEXT = "Monthly credit quota exceeded. Please upgrade your plan, purchase credits, or wait for the next billing cycle.";
const mk = (props) => mount(ConnectionBanners, { props: { error: AR_TEXT, ...props }, global: { stubs: { RouterLink: RouterLinkStub } } });

describe("ConnectionBanners quota CTA", () => {
	it("admins get See plans and Buy credits", () => {
		const w = mk({ errorCode: "quota_exhausted", isAdmin: true });
		const links = w.findAllComponents(RouterLinkStub).map((l) => l.props("to"));
		expect(links).toEqual(["/settings/billing?tab=plans", "/settings/billing?tab=credits"]);
	});
	it("members are told to ask their admin, with no links", () => {
		const w = mk({ errorCode: "quota_exhausted", isAdmin: false });
		expect(w.text()).toContain("Ask your workspace admin");
		expect(w.findAllComponents(RouterLinkStub)).toHaveLength(0);
	});
	it("other errors are unchanged", () => {
		const w = mk({ errorCode: "network", isAdmin: true });
		expect(w.text()).toContain(AR_TEXT);
		expect(w.findAllComponents(RouterLinkStub)).toHaveLength(0);
	});
});
