import { describe, it, expect, vi, beforeEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useChatStore } from "@/stores/chatStore";
import { api } from "@/api/client";

vi.mock("@/api/client", () => ({
	api: { chat: { send: vi.fn() } },
}));
vi.mock("frappe-ui", () => ({ call: vi.fn() }));

// Verbatim shape of upload_message_file's response["file"]. A filter on keys the endpoint never
// returns (is_image / file_type) once sent every image down the OCR path without any error.
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

describe("sendMessage vision attachments", () => {
	let store;

	beforeEach(() => {
		setActivePinia(createPinia());
		localStorage.clear();
		vi.clearAllMocks();
		api.chat.send.mockReturnValue(new Promise(() => {}));
		store = useChatStore();
		store.currentSessionId = "s1";
	});

	// send(sessionId, message, fileUrls, context, modelId, addendum, attachments, opts)
	const sentWith = async (files) => {
		store.sendMessage("look", files, null, "m1");
		await Promise.resolve();
		const call = api.chat.send.mock.calls[0];
		return { fileUrls: call[2], attachments: call[6] };
	};

	it("sends uploaded images to the vision API", async () => {
		const { attachments } = await sentWith([uploadedImage]);

		expect(attachments).toHaveLength(1);
		expect(attachments[0]).toMatchObject({
			type: "image",
			format: "png",
			data: uploadedImage.base64_data,
			name: "chart.png",
			file_url: "/private/files/chart.png",
		});
	});

	it("does not send documents as vision attachments but still extracts their text", async () => {
		const { attachments, fileUrls } = await sentWith([uploadedPdf]);

		expect(attachments).toHaveLength(0);
		expect(fileUrls).toEqual(["/private/files/invoice.pdf"]);
	});

	it("skips images too large for base64 inlining", async () => {
		const { base64_data, ...oversize } = uploadedImage;
		const { attachments } = await sentWith([oversize]);
		expect(attachments).toHaveLength(0);
	});

	it("carries the format through instead of defaulting every image to png", async () => {
		const { attachments } = await sentWith([{ ...uploadedImage, format: "jpeg" }]);
		expect(attachments[0].format).toBe("jpeg");
	});
});
