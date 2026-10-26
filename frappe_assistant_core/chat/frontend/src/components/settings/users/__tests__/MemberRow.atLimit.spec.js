import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";
import MemberRow from "../MemberRow.vue";

const row = (user) =>
	mount(MemberRow, {
		props: { user: { user_id: "u1", full_name: "R", status: "Active", user_role: "Member", ...user } },
		attachTo: document.createElement("tbody"),
	});

describe("MemberRow at its limit", () => {
	it("marks a member who has used their whole personal limit, so an admin can spot who is blocked", () => {
		const wrapper = row({ monthly_credit_limit: 10000, credits_used_this_month: 11234 });
		expect(wrapper.find("[data-test='at-limit']").exists()).toBe(true);
	});

	it("doesn't mark a member under their limit or on the shared pool", () => {
		expect(row({ monthly_credit_limit: 10000, credits_used_this_month: 10 }).find("[data-test='at-limit']").exists()).toBe(false);
		expect(row({ monthly_credit_limit: 0, credits_used_this_month: 99999 }).find("[data-test='at-limit']").exists()).toBe(false);
	});
});
