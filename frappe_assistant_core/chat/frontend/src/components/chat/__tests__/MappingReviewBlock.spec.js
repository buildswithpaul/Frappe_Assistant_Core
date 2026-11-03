import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
	api: { imports: { mappingReview: vi.fn(), setMappingColumn: vi.fn() } },
}));

import { api } from "@/api/client";
import MappingReviewBlock from "@/components/chat/MappingReviewBlock.vue";

const review = (overrides = {}) => ({
	session: "IMP-1",
	ready: true,
	file_name: "customers.csv",
	doctype: "Customer",
	editable: true,
	columns: [
		{ position: 0, column: "Customer Name", samples: ["Acme", "Globex"], field: "customer_name", label: "Customer Name", status: "mapped" },
		{ position: 1, column: "Region", samples: ["South"], field: null, label: null, status: "unmapped" },
	],
	options: [
		{ value: "Don't Import", label: "Don't import" },
		{ value: "customer_name", label: "Customer Name", required: true },
		{ value: "territory", label: "Territory" },
	],
	missing_required: [],
	summary: "1 columns mapped, 0 not imported, 1 unmapped.",
	...overrides,
});

beforeEach(() => {
	api.imports.mappingReview.mockReset().mockResolvedValue(review());
	api.imports.setMappingColumn.mockReset();
});

describe("the mapping review card (#34415)", () => {
	it("shows each column with its first values, field and status", async () => {
		const w = mount(MappingReviewBlock, { props: { session: "IMP-1" } });
		await flushPromises();
		expect(w.text()).toContain("Customer Name");
		expect(w.text()).toContain("Acme, Globex");
		expect(w.text()).toContain("No field");
		expect(w.findAll("select.mr-select")[0].element.value).toBe("customer_name");
	});

	it("saves a changed dropdown at once, with no chat message, and shows what was saved", async () => {
		const saved = review({
			columns: [review().columns[0], { ...review().columns[1], field: "territory", label: "Territory", status: "mapped" }],
		});
		api.imports.setMappingColumn.mockResolvedValue({ success: true, review: saved });
		const w = mount(MappingReviewBlock, { props: { session: "IMP-1" } });
		await flushPromises();

		await w.findAll("select.mr-select")[1].setValue("territory");
		await flushPromises();

		expect(api.imports.setMappingColumn).toHaveBeenCalledWith("IMP-1", 1, "territory");
		expect(w.findAll(".mr-status")[1].text()).toBe("Mapped");
	});

	it("says why a change was refused", async () => {
		api.imports.setMappingColumn.mockResolvedValue({ success: false, error: "The mapping was not saved.", problems: ["Bad field"], review: review() });
		const w = mount(MappingReviewBlock, { props: { session: "IMP-1" } });
		await flushPromises();
		await w.findAll("select.mr-select")[1].setValue("territory");
		await flushPromises();
		expect(w.find(".mr-error").text()).toContain("Bad field");
	});

	it("lists required fields with no column above the table", async () => {
		api.imports.mappingReview.mockResolvedValue(review({ missing_required: [{ field: "customer_group", label: "Customer Group" }] }));
		const w = mount(MappingReviewBlock, { props: { session: "IMP-1" } });
		await flushPromises();
		expect(w.find(".mr-missing").text()).toContain("Customer Group");
	});

	it("can't be changed while the session is importing", async () => {
		api.imports.mappingReview.mockResolvedValue(review({ editable: false, refused: "This session's import is still running." }));
		const w = mount(MappingReviewBlock, { props: { session: "IMP-1" } });
		await flushPromises();
		expect(w.findAll("select.mr-select").every((s) => s.element.disabled)).toBe(true);
		expect(w.find(".mr-locked").text()).toContain("still running");
	});
});
