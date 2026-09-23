import { afterEach, describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";
import SeatPurchaseModal from "./SeatPurchaseModal.vue";

const confirmData = (over) => ({
	user_id: "new@example.com",
	full_name: "New User",
	perUserPrice: 1999,
	proratedRate: 66.63,
	tax: 0,
	total: 66.63,
	daysRemaining: 20,
	daysInCycle: 30,
	currency: "INR",
	newSeatCount: 10,
	...over,
});

// The modal teleports to <body>, so it is the document -- not the wrapper --
// that has to be queried.
function mountModal(props = {}) {
	mount(SeatPurchaseModal, { props: { confirmData: confirmData(), ...props } });
	return document.querySelector(".seat-confirm-modal");
}

afterEach(() => {
	document.body.replaceChildren();
});

describe("SeatPurchaseModal", () => {
	it("promises seats, not users, in the renewal note", () => {
		// 9 paid, 5 assigned, adding one: newSeatCount is 10 -- the paid
		// count, not the member count. "10 users" would be false: this
		// admin has six people once the invite is accepted.
		const modal = mountModal({ confirmData: confirmData({ newSeatCount: 10 }) });
		expect(modal.textContent).toContain("10 seats");
		expect(modal.textContent).not.toContain("10 users");
	});
});
