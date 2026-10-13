import { describe, it, expect, beforeAll, beforeEach, afterEach, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";

const list = vi.fn();
const upload = vi.fn();
const remove = vi.fn();
vi.mock("@/api/client", () => ({
	api: {
		documents: {
			list: (...a) => list(...a),
			upload: (...a) => upload(...a),
			delete: (...a) => remove(...a),
			getDownloadUrl: (id) => `/dl/${id}`,
		},
	},
}));
const showError = vi.fn();
vi.mock("@/composables/useToast", () => ({ useToast: () => ({ showError }) }));

import ProjectDocuments from "@/components/projects/ProjectDocuments.vue";

beforeAll(() => {
	window.__ = (s) => s;
});

const doc = (id, status, name = `${id}.pdf`) => ({
	document_id: id,
	file_name: name,
	file_size: 2048,
	embedding_status: status,
	project_id: "p1",
});

const ConfirmStub = {
	props: ["open"],
	emits: ["confirm", "cancel"],
	template: `<div v-if="open" data-test="confirm"><button data-test="confirm-ok" @click="$emit('confirm')"/></div>`,
};

function mountBlock() {
	return mount(ProjectDocuments, {
		props: { projectId: "p1" },
		attachTo: document.body,
		global: { stubs: { ConfirmModal: ConfirmStub } },
	});
}

beforeEach(() => {
	vi.useFakeTimers();
	vi.clearAllMocks();
	list.mockResolvedValue({ documents: [] });
});

afterEach(() => {
	vi.useRealTimers();
	document.body.innerHTML = "";
});

describe("ProjectDocuments", () => {
	it("shows the empty state", async () => {
		const w = mountBlock();
		await flushPromises();
		expect(list).toHaveBeenCalledWith({ project: "p1" });
		expect(w.get("[data-test=docs-empty]").text()).toBe(
			"No documents yet. Upload files the assistant should know for this project."
		);
	});

	it("lists documents with a status pill per embedding state", async () => {
		list.mockResolvedValue({
			documents: [doc("a", "Pending"), doc("b", "Processing"), doc("c", "Completed"), doc("d", "Failed")],
		});
		const w = mountBlock();
		await flushPromises();
		expect(w.findAll("[data-test=doc-status]").map((n) => n.text())).toEqual([
			"Processing",
			"Processing",
			"Ready",
			"Failed",
		]);
		w.unmount();
	});

	it("uploads with the project and refreshes the list", async () => {
		upload.mockResolvedValue({});
		const w = mountBlock();
		await flushPromises();
		list.mockResolvedValue({ documents: [doc("a", "Completed", "notes.pdf")] });
		const file = new File(["x"], "notes.pdf", { type: "application/pdf" });
		const input = w.get("[data-test=docs-file-input]");
		Object.defineProperty(input.element, "files", { value: [file], configurable: true });
		await input.trigger("change");
		await flushPromises();
		expect(upload).toHaveBeenCalledWith(file, { project: "p1" });
		expect(w.findAll("[data-test=doc-row]")).toHaveLength(1);
		w.unmount();
	});

	it("refuses an unsupported file without calling upload", async () => {
		const w = mountBlock();
		await flushPromises();
		const file = new File(["x"], "pic.png", { type: "image/png" });
		await w.get("[data-test=project-documents]").trigger("drop", { dataTransfer: { files: [file] } });
		await flushPromises();
		expect(upload).not.toHaveBeenCalled();
		expect(showError).toHaveBeenCalled();
		w.unmount();
	});

	it("a dropped file goes through the same upload", async () => {
		upload.mockResolvedValue({});
		const w = mountBlock();
		await flushPromises();
		const file = new File(["x"], "a.md", { type: "text/markdown" });
		await w.get("[data-test=project-documents]").trigger("drop", { dataTransfer: { files: [file] } });
		await flushPromises();
		expect(upload).toHaveBeenCalledWith(file, { project: "p1" });
		w.unmount();
	});

	it("polls every 5s while processing, stops when done, and stops on unmount", async () => {
		list.mockResolvedValue({ documents: [doc("a", "Processing")] });
		const w = mountBlock();
		await flushPromises();
		expect(list).toHaveBeenCalledTimes(1);
		await vi.advanceTimersByTimeAsync(5000);
		expect(list).toHaveBeenCalledTimes(2);

		list.mockResolvedValue({ documents: [doc("a", "Completed")] });
		await vi.advanceTimersByTimeAsync(5000);
		expect(list).toHaveBeenCalledTimes(3);
		await vi.advanceTimersByTimeAsync(15000);
		expect(list).toHaveBeenCalledTimes(3);
		w.unmount();
	});

	it("stops polling when unmounted while a document is still processing", async () => {
		list.mockResolvedValue({ documents: [doc("a", "Pending")] });
		const w = mountBlock();
		await flushPromises();
		w.unmount();
		const calls = list.mock.calls.length;
		await vi.advanceTimersByTimeAsync(20000);
		expect(list).toHaveBeenCalledTimes(calls);
	});

	it("deletes after confirmation and removes the row", async () => {
		list.mockResolvedValue({ documents: [doc("a", "Completed"), doc("b", "Completed")] });
		remove.mockResolvedValue({});
		const w = mountBlock();
		await flushPromises();
		await w.findAll("[data-test=doc-menu]")[0].trigger("click");
		await w.get("[data-test=doc-delete]").trigger("click");
		expect(remove).not.toHaveBeenCalled();
		await w.get("[data-test=confirm-ok]").trigger("click");
		await flushPromises();
		expect(remove).toHaveBeenCalledWith("a");
		expect(w.findAll("[data-test=doc-row]")).toHaveLength(1);
		w.unmount();
	});

	it("keeps the row and toasts when delete fails", async () => {
		list.mockResolvedValue({ documents: [doc("a", "Completed")] });
		remove.mockRejectedValue(new Error("nope"));
		const w = mountBlock();
		await flushPromises();
		await w.get("[data-test=doc-menu]").trigger("click");
		await w.get("[data-test=doc-delete]").trigger("click");
		await w.get("[data-test=confirm-ok]").trigger("click");
		await flushPromises();
		expect(showError).toHaveBeenCalledWith("nope");
		expect(w.findAll("[data-test=doc-row]")).toHaveLength(1);
		w.unmount();
	});

	it("offers Download and closes the menu on an outside click or Escape without bubbling", async () => {
		list.mockResolvedValue({ documents: [doc("a", "Completed")] });
		const w = mountBlock();
		await flushPromises();
		await w.get("[data-test=doc-menu]").trigger("click");
		expect(w.get("[data-test=doc-download]").attributes("href")).toBe("/dl/a");

		document.body.click();
		await flushPromises();
		expect(w.find("[data-test=doc-download]").exists()).toBe(false);

		await w.get("[data-test=doc-menu]").trigger("click");
		const outer = vi.fn();
		document.addEventListener("keydown", outer);
		const ev = new KeyboardEvent("keydown", { key: "Escape", bubbles: true });
		w.get("[role=menu]").element.dispatchEvent(ev);
		await flushPromises();
		document.removeEventListener("keydown", outer);
		expect(w.find("[data-test=doc-download]").exists()).toBe(false);
		expect(outer).not.toHaveBeenCalled();
		w.unmount();
	});
});
