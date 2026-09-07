import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";
import VacantSeatsBanner from "../VacantSeatsBanner.vue";

const paidTeam = (over) => ({
	is_per_user: true, paid_seats: 9, assigned_seats: 5, vacant_seats: 4,
	min_users: 3, ...over,
});

describe("VacantSeatsBanner", () => {
	it("names both numbers so they cannot be confused", () => {
		const w = mount(VacantSeatsBanner, { props: { userLimit: paidTeam() } });
		expect(w.text()).toContain("5 of 9");
		expect(w.text()).toMatch(/4 (seats|vacant)/i);
	});

	it("says nothing when every paid seat is taken", () => {
		const w = mount(VacantSeatsBanner, {
			props: { userLimit: paidTeam({ assigned_seats: 9, vacant_seats: 0 }) },
		});
		expect(w.find("[data-test=vacant-banner]").exists()).toBe(false);
	});

	it("says nothing on a flat plan", () => {
		const w = mount(VacantSeatsBanner, {
			props: {
				userLimit: {
					is_per_user: false, paid_seats: null,
					assigned_seats: null, vacant_seats: null,
				},
			},
		});
		expect(w.find("[data-test=vacant-banner]").exists()).toBe(false);
	});

	it("says nothing on a flat plan even with stale seat numbers", () => {
		// `null > 0` is false in JS, so the previous test alone can't tell a
		// real is_per_user gate from one that was never written — a downgraded
		// tenant keeps a stale, still-positive user_count, so this fixture
		// carries positive numbers specifically to force that gate to fire.
		const w = mount(VacantSeatsBanner, {
			props: { userLimit: paidTeam({ is_per_user: false }) },
		});
		expect(w.find("[data-test=vacant-banner]").exists()).toBe(false);
	});

	it("emits release", async () => {
		const w = mount(VacantSeatsBanner, { props: { userLimit: paidTeam() } });
		await w.find("[data-test=release-seat]").trigger("click");
		expect(w.emitted("release")).toBeTruthy();
	});

	it("cannot release below the plan minimum", () => {
		const w = mount(VacantSeatsBanner, {
			props: {
				userLimit: paidTeam({ paid_seats: 3, assigned_seats: 0, vacant_seats: 3 }),
			},
		});
		expect(w.find("[data-test=release-seat]").attributes("disabled")).toBeDefined();
	});
});
