import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import AttachmentPicker from "@/components/support/support/AttachmentPicker.vue";

const doneImg = {
	id: 1,
	file_id: "F1",
	file_name: "a.png",
	is_image: true,
	previewUrl: "blob:x",
	status: "done",
	error: null,
};
const uploadingPdf = {
	id: 3,
	file_id: null,
	file_name: "c.pdf",
	is_image: false,
	previewUrl: null,
	status: "uploading",
	error: null,
};
const errPdf = {
	id: 2,
	file_id: null,
	file_name: "b.pdf",
	is_image: false,
	previewUrl: null,
	status: "error",
	error: "Upload failed",
};

describe("AttachmentPicker", () => {
	it("renders an attach button", () => {
		const w = mount(AttachmentPicker, { props: { files: [] } });
		expect(w.find(".attach-btn").exists()).toBe(true);
	});

	it("renders an image thumbnail for a done image", () => {
		const w = mount(AttachmentPicker, { props: { files: [doneImg] } });
		expect(w.find("img.thumb").attributes("src")).toBe("blob:x");
	});

	it("renders a PDF chip for a non-image entry", () => {
		const w = mount(AttachmentPicker, { props: { files: [uploadingPdf] } });
		expect(w.find(".pdf-icon").exists()).toBe(true);
		expect(w.text()).toContain("c.pdf");
	});

	it("shows an upload spinner while uploading", () => {
		const w = mount(AttachmentPicker, { props: { files: [uploadingPdf] } });
		expect(w.find(".spinner").exists()).toBe(true);
	});

	it("emits remove with the index when the x is clicked", async () => {
		const w = mount(AttachmentPicker, { props: { files: [doneImg] } });
		await w.find("[data-test=remove]").trigger("click");
		expect(w.emitted("remove")[0]).toEqual([0]);
	});

	it("shows an error state with a retry affordance", async () => {
		const w = mount(AttachmentPicker, { props: { files: [errPdf] } });
		expect(w.text()).toContain("Upload failed");
		await w.find("[data-test=retry]").trigger("click");
		expect(w.emitted("retry")[0]).toEqual([0]);
	});

	it("emits add with dropped files", async () => {
		const w = mount(AttachmentPicker, { props: { files: [] } });
		const file = new File([1], "c.png", { type: "image/png" });
		await w
			.find("[data-test=dropzone]")
			.trigger("drop", { dataTransfer: { files: [file] } });
		expect(w.emitted("add")[0][0]).toEqual([file]);
	});

	it("emits add with files chosen via the file input", async () => {
		const w = mount(AttachmentPicker, { props: { files: [] } });
		const file = new File([1], "d.png", { type: "image/png" });
		const input = w.find("input[type=file]");
		Object.defineProperty(input.element, "files", { value: [file] });
		await input.trigger("change");
		expect(w.emitted("add")[0][0]).toEqual([file]);
	});

	it("disables the attach button once maxFiles is reached", () => {
		const w = mount(AttachmentPicker, {
			props: { files: [doneImg], maxFiles: 1 },
		});
		expect(w.find(".attach-btn").attributes("disabled")).toBeDefined();
	});

	it("disables the attach button when disabled prop is set", () => {
		const w = mount(AttachmentPicker, {
			props: { files: [], disabled: true },
		});
		expect(w.find(".attach-btn").attributes("disabled")).toBeDefined();
	});
});
