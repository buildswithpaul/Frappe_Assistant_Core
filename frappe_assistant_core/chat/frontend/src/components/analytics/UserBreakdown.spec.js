import { mount } from "@vue/test-utils";
import { describe, it, expect } from "vitest";
import UserBreakdown from "./UserBreakdown.vue";

function mountRow(row) {
	return mount(UserBreakdown, {
		props: { users: [{ credits_consumed: 5, request_count: 2, ...row }], totalCredits: 10 },
	});
}

describe("UserBreakdown", () => {
	it("shows the full name with the email secondary", () => {
		const wrapper = mountRow({ user_id: "a@x.com", full_name: "Avery Lee" });
		expect(wrapper.find(".user-name").text()).toBe("Avery Lee");
		expect(wrapper.find(".user-email").text()).toBe("a@x.com");
	});

	it("falls back to the email when there is no full name", () => {
		const wrapper = mountRow({ user_id: "a@x.com", full_name: null });
		expect(wrapper.find(".user-name").text()).toBe("a@x.com");
		expect(wrapper.find(".user-email").exists()).toBe(false);
	});
});
