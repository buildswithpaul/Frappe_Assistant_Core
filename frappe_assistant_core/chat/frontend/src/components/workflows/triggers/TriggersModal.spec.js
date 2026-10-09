import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";

const T1 = {
	name: "T1",
	title: "Big orders",
	enabled: 1,
	doctype_event: "on_submit",
	reference_doctype: "Sales Order",
	filters: [],
};

const { triggers } = vi.hoisted(() => ({
	triggers: {
		list: vi.fn(),
		test: vi.fn(),
		update: vi.fn(),
		toggle: vi.fn(),
		delete: vi.fn(),
		getDoctypeFields: vi.fn(),
		listDoctypes: vi.fn(),
	},
}));

vi.mock("@/api/client", () => {
	const api = { workflows: { triggers } };
	return { api, default: api };
});

import TriggersModal from "./TriggersModal.vue";

const RESULT = { would_fire: true, sample_doc: "SO-0007", payload: { doc: {} } };

async function mountModal() {
	const w = mount(TriggersModal, {
		props: { modelValue: false, workflowId: "WF-1", workflowDisplayName: "Digest" },
		global: { stubs: { Teleport: true } },
	});
	await w.setProps({ modelValue: true });
	await flushPromises();
	return w;
}

describe("TriggersModal test results", () => {
	beforeEach(() => {
		Object.values(triggers).forEach((f) => f.mockReset());
		triggers.list.mockResolvedValue({ triggers: [T1] });
		triggers.getDoctypeFields.mockResolvedValue({ fields: [] });
		triggers.listDoctypes.mockResolvedValue({ doctypes: [] });
		triggers.update.mockResolvedValue({});
		triggers.toggle.mockResolvedValue({});
	});

	it("shows a result, then drops it once the trigger is edited and saved", async () => {
		triggers.test.mockResolvedValue(RESULT);
		const w = await mountModal();
		await w.get('[data-test="trigger-test"]').trigger("click");
		await flushPromises();
		expect(w.text()).toContain("SO-0007");

		await w.get('button[title="Edit"]').trigger("click");
		await flushPromises();
		await w.get('[data-test="trigger-save"]').trigger("click");
		await flushPromises();
		expect(w.text()).not.toContain("SO-0007");
	});

	it("drops the result when the trigger is toggled", async () => {
		triggers.test.mockResolvedValue(RESULT);
		const w = await mountModal();
		await w.get('[data-test="trigger-test"]').trigger("click");
		await flushPromises();
		await w.get('button[title="Disable"]').trigger("click");
		await flushPromises();
		expect(w.text()).not.toContain("SO-0007");
	});

	it("ignores a test that finishes after the trigger was changed", async () => {
		let resolve;
		triggers.test.mockReturnValue(new Promise((r) => (resolve = r)));
		const w = await mountModal();
		await w.get('[data-test="trigger-test"]').trigger("click");
		await w.get('button[title="Disable"]').trigger("click");
		await flushPromises();
		resolve(RESULT);
		await flushPromises();
		expect(w.text()).not.toContain("SO-0007");
	});

	it("keeps a spinner per card when two tests run at once", async () => {
		const T2 = { ...T1, name: "T2", title: "Other" };
		triggers.list.mockResolvedValue({ triggers: [T1, T2] });
		triggers.test.mockReturnValue(new Promise(() => {}));
		const w = await mountModal();
		await w.findAll('[data-test="trigger-test"]')[0].trigger("click");
		await w.findAll('[data-test="trigger-test"]')[1].trigger("click");
		await flushPromises();
		expect(w.findAll('[data-test="trigger-test"]').map((b) => b.element.disabled)).toEqual([true, true]);
	});
});
