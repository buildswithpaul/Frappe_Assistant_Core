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
		expect(w.text()).not.toContain(AR_TEXT);
		expect(w.findAllComponents(RouterLinkStub)).toHaveLength(0);
	});
	it("other errors are unchanged", () => {
		const w = mk({ errorCode: "network", isAdmin: true });
		expect(w.text()).toContain(AR_TEXT);
		expect(w.findAllComponents(RouterLinkStub)).toHaveLength(0);
	});
	it("dismiss emits dismiss-error even for quota errors", () => {
		const w = mk({ errorCode: "quota_exhausted", isAdmin: false });
		w.find(".dismiss-btn").trigger("click");
		expect(w.emitted("dismiss-error")).toBeTruthy();
	});
});

describe("ConnectionBanners personal limit refusal", () => {
	const REFUSAL = "Your individual credit limit has been reached. Contact your team admin.";

	it("tells an admin they can change their own limit, with the link to Users", () => {
		const w = mk({ error: REFUSAL, errorCode: "user_limit_reached", isAdmin: true });
		expect(w.find('[data-test="user-limit-error"]').exists()).toBe(true);
		expect(w.text()).toContain("You can change it in Settings → Users");
		expect(w.text()).not.toContain(REFUSAL);
		expect(w.findComponent(RouterLinkStub).props("to")).toEqual({ name: "settings-users" });
	});

	it("tells a member to ask their team admin, with no link", () => {
		const w = mk({ error: REFUSAL, errorCode: "user_limit_reached", isAdmin: false });
		expect(w.text()).toContain("Ask your team admin to raise it");
		expect(w.findAllComponents(RouterLinkStub)).toHaveLength(0);
	});

	it("can still be dismissed", () => {
		const w = mk({ error: REFUSAL, errorCode: "user_limit_reached", isAdmin: true });
		w.find('[data-test="user-limit-error"] .dismiss-btn').trigger("click");
		expect(w.emitted("dismiss-error")).toBeTruthy();
	});
});
