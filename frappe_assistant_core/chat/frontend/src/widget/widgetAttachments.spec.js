import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const widgetJs = resolve(process.cwd(), "../../public/chat/widget/widget.js");

/**
 * Evaluate the widget's real vision-attachment expression against a payload
 * shaped exactly like `upload_message_file`'s response. A regex assertion would
 * not have caught the original bug (`f.is_image` / `f.file_type` — keys the
 * endpoint never returns), because the filter silently produced an empty array
 * and every image quietly fell back to the OCR path.
 */
function buildAttachments(attachedFiles) {
	const src = readFileSync(widgetJs, "utf8");
	const block = src.match(/const attachments = this\.attached_files[\s\S]*?\}\)\);/);
	expect(block, "vision-attachment block not found in widget.js").not.toBeNull();

	const body = block[0].replace(/this\.attached_files/g, "attached_files");
	return new Function("attached_files", `${body}\nreturn attachments;`)(attachedFiles);
}

// Verbatim shape of `upload_message_file` -> response["file"].
const uploadedImage = {
	name: "9f2a1c",
	file_name: "chart.png",
	file_url: "/private/files/chart.png",
	file_size: 20481,
	is_private: 1,
	format: "png",
	type: "image",
	base64_data: "iVBORw0KGgoAAAANSUhEUg==",
};

const uploadedPdf = {
	name: "77bb02",
	file_name: "invoice.pdf",
	file_url: "/private/files/invoice.pdf",
	file_size: 91234,
	is_private: 1,
	format: "pdf",
	type: "document",
};

describe("Desk widget vision attachments", () => {
	it("sends uploaded images to the vision API", () => {
		const attachments = buildAttachments([uploadedImage]);

		expect(attachments).toHaveLength(1);
		expect(attachments[0]).toMatchObject({
			type: "image",
			format: "png",
			data: uploadedImage.base64_data,
			name: "chart.png",
			file_url: "/private/files/chart.png",
		});
	});

	it("does not send documents as vision attachments", () => {
		expect(buildAttachments([uploadedPdf])).toHaveLength(0);
	});

	it("skips images too large for base64 inlining", () => {
		const { base64_data, ...oversizeImage } = uploadedImage;
		expect(buildAttachments([oversizeImage])).toHaveLength(0);
	});

	it("carries the format through instead of defaulting every image to png", () => {
		const jpeg = { ...uploadedImage, file_name: "photo.jpg", format: "jpeg" };
		expect(buildAttachments([jpeg])[0].format).toBe("jpeg");
	});
});
