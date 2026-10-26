import { describe, it, expect } from "vitest";
import { mount, RouterLinkStub } from "@vue/test-utils";
import PersonalLimitBanner from "./PersonalLimitBanner.vue";

const mk = (props) => mount(PersonalLimitBanner, { props, global: { stubs: { RouterLink: RouterLinkStub } } });

describe("PersonalLimitBanner", () => {
	it("tells an admin the limit is theirs to change, and links to Users", () => {
		const w = mk({ isAdmin: true, used: 11234, limit: 10000 });
		expect(w.text()).toContain("You've reached your personal monthly limit.");
		expect(w.text()).toContain("Settings → Users (0 means no personal limit)");
		expect(w.findComponent(RouterLinkStub).props("to")).toEqual({ name: "settings-users" });
		expect(w.find('[data-test="change-limit"]').text()).toBe("Change limit");
	});

	it("tells a member to ask their team admin, with no link", () => {
		const w = mk({ isAdmin: false, used: 500, limit: 500 });
		expect(w.text()).toContain("Ask your team admin to raise it.");
		expect(w.findAllComponents(RouterLinkStub)).toHaveLength(0);
	});

	it("shows the usage against the limit when it knows them", () => {
		expect(mk({ isAdmin: true, used: 500, limit: 500 }).text()).toMatch(/of .* credits used this month/);
		expect(mk({ isAdmin: true }).text()).not.toMatch(/credits used this month/);
	});
});
