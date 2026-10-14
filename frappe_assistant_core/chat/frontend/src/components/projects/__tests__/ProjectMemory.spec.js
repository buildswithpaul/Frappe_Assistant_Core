import { describe, it, expect, beforeAll, beforeEach, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";

const list = vi.fn();
const update = vi.fn();
const remove = vi.fn();
const clearProject = vi.fn();
vi.mock("@/api/client", () => ({
	api: {
		memories: {
			list: (...a) => list(...a),
			update: (...a) => update(...a),
			delete: (...a) => remove(...a),
			clearProject: (...a) => clearProject(...a),
		},
	},
}));
const showError = vi.fn();
vi.mock("@/composables/useToast", () => ({ useToast: () => ({ showError, showToast: vi.fn() }) }));

import ProjectMemory from "@/components/projects/ProjectMemory.vue";

beforeAll(() => {
	window.__ = (s) => s;
});

const memory = (id, type = "fact", content = `content ${id}`) => ({
	memory_id: id,
	memory_type: type,
	content,
	project_id: "p1",
});

const ConfirmStub = {
	props: ["open", "title"],
	emits: ["confirm", "cancel"],
	template: `<div v-if="open" data-test="confirm" :data-title="title"><button data-test="confirm-ok" @click="$emit('confirm')"/></div>`,
};

function mountBlock() {
	return mount(ProjectMemory, {
		props: { projectId: "p1" },
		global: { stubs: { ConfirmModal: ConfirmStub } },
	});
}

beforeEach(() => {
	vi.clearAllMocks();
	list.mockResolvedValue({ memories: [] });
});

describe("ProjectMemory", () => {
	it("shows the empty state and no clear button", async () => {
		const w = mountBlock();
		await flushPromises();
		expect(list).toHaveBeenCalledWith(null, 200, 0, "p1");
		expect(w.get("[data-test=memory-empty]").text()).toBe(
			"Nothing remembered for this project yet. As you chat here, FACO keeps project-specific facts in this list."
		);
		expect(w.find("[data-test=memory-clear]").exists()).toBe(false);
	});

	it("lists memories with a type pill each", async () => {
		list.mockResolvedValue({
			memories: [memory("a", "preference"), memory("b", "fact"), memory("c", "summary"), memory("d", "correction")],
		});
		const w = mountBlock();
		await flushPromises();
		expect(w.findAll("[data-test=memory-row]")).toHaveLength(4);
		expect(w.findAll("[data-test=memory-type]").map((p) => p.text())).toEqual([
			"Preference",
			"Fact",
			"Summary",
			"Correction",
		]);
	});

	it("edits a memory inline through the update endpoint", async () => {
		list.mockResolvedValue({ memories: [memory("a")] });
		update.mockResolvedValue({});
		const w = mountBlock();
		await flushPromises();
		await w.get("[data-test=memory-edit]").trigger("click");
		await w.get("[data-test=memory-edit-input]").setValue("new text");
		await w.get("[data-test=memory-edit-save]").trigger("click");
		await flushPromises();
		expect(update).toHaveBeenCalledWith("a", "new text");
		expect(w.get("[data-test=memory-content]").text()).toBe("new text");
	});

	it("keeps the editor and the draft open when a save fails", async () => {
		list.mockResolvedValue({ memories: [memory("a")] });
		update.mockRejectedValue(new Error("nope"));
		const w = mountBlock();
		await flushPromises();
		await w.get("[data-test=memory-edit]").trigger("click");
		await w.get("[data-test=memory-edit-input]").setValue("new text");
		await w.get("[data-test=memory-edit-save]").trigger("click");
		await flushPromises();
		expect(showError).toHaveBeenCalledWith("nope");
		expect(w.get("[data-test=memory-edit-input]").element.value).toBe("new text");
	});

	it("does not save on the Enter that ends an IME composition", async () => {
		list.mockResolvedValue({ memories: [memory("a")] });
		update.mockResolvedValue({});
		const w = mountBlock();
		await flushPromises();
		await w.get("[data-test=memory-edit]").trigger("click");
		const input = w.get("[data-test=memory-edit-input]");
		await input.setValue("新しい");
		await input.trigger("keydown", { key: "Enter", isComposing: true });
		expect(update).not.toHaveBeenCalled();
		await input.trigger("keydown", { key: "Enter" });
		await flushPromises();
		expect(update).toHaveBeenCalledWith("a", "新しい");
	});

	it("labels the row controls for assistive tech", async () => {
		list.mockResolvedValue({ memories: [memory("a")] });
		const w = mountBlock();
		await flushPromises();
		expect(w.get("[data-test=memory-edit]").attributes("aria-label")).toBe("Edit memory");
		expect(w.get("[data-test=memory-delete]").attributes("aria-label")).toBe("Delete memory");
		await w.get("[data-test=memory-edit]").trigger("click");
		expect(w.get("[data-test=memory-edit-input]").attributes("aria-label")).toBe("Memory text");
	});

	it("deletes one memory only after confirmation", async () => {
		list.mockResolvedValue({ memories: [memory("a"), memory("b")] });
		remove.mockResolvedValue({});
		const w = mountBlock();
		await flushPromises();
		await w.findAll("[data-test=memory-delete]")[0].trigger("click");
		expect(remove).not.toHaveBeenCalled();
		await w.get("[data-test=confirm-ok]").trigger("click");
		await flushPromises();
		expect(remove).toHaveBeenCalledWith("a");
		expect(w.findAll("[data-test=memory-row]")).toHaveLength(1);
	});

	it("clears the project's memory only after confirmation", async () => {
		list.mockResolvedValue({ memories: [memory("a"), memory("b")] });
		clearProject.mockResolvedValue({ status: "success", count: 2 });
		const w = mountBlock();
		await flushPromises();
		await w.get("[data-test=memory-clear]").trigger("click");
		expect(clearProject).not.toHaveBeenCalled();
		await w.get("[data-test=confirm-ok]").trigger("click");
		await flushPromises();
		expect(clearProject).toHaveBeenCalledWith("p1");
		expect(w.find("[data-test=memory-empty]").exists()).toBe(true);
	});

	it("keeps the list and toasts when a delete fails", async () => {
		list.mockResolvedValue({ memories: [memory("a")] });
		remove.mockRejectedValue(new Error("nope"));
		const w = mountBlock();
		await flushPromises();
		await w.get("[data-test=memory-delete]").trigger("click");
		await w.get("[data-test=confirm-ok]").trigger("click");
		await flushPromises();
		expect(showError).toHaveBeenCalledWith("nope");
		expect(w.findAll("[data-test=memory-row]")).toHaveLength(1);
	});

	it("shows a retry when the load fails", async () => {
		list.mockRejectedValueOnce(new Error("down"));
		const w = mountBlock();
		await flushPromises();
		expect(w.find("[data-test=memory-error]").exists()).toBe(true);
		expect(w.find("[data-test=memory-clear]").exists()).toBe(false);
		list.mockResolvedValue({ memories: [memory("a")] });
		await w.get("[data-test=memory-retry]").trigger("click");
		await flushPromises();
		expect(w.findAll("[data-test=memory-row]")).toHaveLength(1);
	});

	it("shows the memory count in the card header", async () => {
		list.mockResolvedValue({ memories: [memory("m1"), memory("m2")] });
		const w = mountBlock();
		await flushPromises();
		expect(w.find("[data-test=memory-count]").text()).toBe("· 2");
	});

	it("shows no count before any memory exists", async () => {
		list.mockResolvedValue({ memories: [] });
		const w = mountBlock();
		await flushPromises();
		expect(w.find("[data-test=memory-count]").exists()).toBe(false);
	});
});
