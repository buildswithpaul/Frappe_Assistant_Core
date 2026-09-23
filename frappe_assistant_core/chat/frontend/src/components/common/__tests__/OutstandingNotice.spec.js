import { mount } from "@vue/test-utils";
import { describe, it, expect } from "vitest";
import OutstandingNotice from "@/components/common/OutstandingNotice.vue";
import InvoiceHistory from "@/components/settings/billing/InvoiceHistory.vue";

const OWED = { amount: 7076.46, currency: "INR", invoice: "INV-0042" };

describe("OutstandingNotice", () => {
	it("states the amount owed", () => {
		const w = mount(OutstandingNotice, { props: { outstanding: OWED } });
		expect(w.text()).toContain("7,076.46");
		expect(w.text()).toContain("outstanding");
	});

	it("renders nothing when nothing is owed", () => {
		// The surfaces key on presence, so a null must occupy no space at all
		// rather than leave an empty bordered box on four pages.
		expect(
			mount(OutstandingNotice, { props: { outstanding: null } }).find(".due-notice").exists()
		).toBe(false);
		expect(
			mount(OutstandingNotice, { props: { outstanding: { amount: 0 } } })
				.find(".due-notice")
				.exists()
		).toBe(false);
	});

	it("carries a per-surface reason, because one wording in four places gets tuned out", () => {
		const w = mount(OutstandingNotice, {
			props: { outstanding: OWED, reason: "Seats can't be added until this clears." },
		});
		expect(w.text()).toContain("Seats can't be added until this clears.");
	});

	it("emits pay rather than navigating itself", async () => {
		const w = mount(OutstandingNotice, { props: { outstanding: OWED } });
		await w.find(".due-btn").trigger("click");
		expect(w.emitted("pay")).toHaveLength(1);
	});

	it("can be shown without an action where there is nowhere to send the click", () => {
		const w = mount(OutstandingNotice, { props: { outstanding: OWED, showAction: false } });
		expect(w.find(".due-btn").exists()).toBe(false);
	});
});

describe("the owed invoice row", () => {
	const invoices = [
		{ id: "INV-0042", amount: 7076.46, currency: "INR", status: "pending", date: "2026-09-11" },
		{ id: "INV-0041", amount: 7076.46, currency: "INR", status: "pending", date: "2026-08-11" },
		{ id: "INV-0040", amount: 6540, currency: "INR", status: "paid", date: "2026-07-11" },
	];
	const props = {
		invoices,
		formatCurrency: (a) => String(a),
		formatInvoiceDate: (i) => i.date,
		formatStatus: (s) => s,
	};

	it("offers Pay on the owed row only, not on every unpaid one", () => {
		// Two rows sit unpaid; exactly one is the balance the button settles.
		const w = mount(InvoiceHistory, { props: { ...props, outstandingInvoiceId: "INV-0042" } });
		expect(w.findAll(".pay-link")).toHaveLength(1);
	});

	it("offers Pay nowhere when nothing is owed", () => {
		const w = mount(InvoiceHistory, { props: { ...props, outstandingInvoiceId: null } });
		expect(w.findAll(".pay-link")).toHaveLength(0);
	});

	it("keeps the download action on paid rows", () => {
		const w = mount(InvoiceHistory, { props: { ...props, outstandingInvoiceId: "INV-0042" } });
		expect(w.findAll(".download-link")).toHaveLength(1);
	});
});
