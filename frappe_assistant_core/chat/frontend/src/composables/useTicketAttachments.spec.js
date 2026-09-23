import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { flushPromises } from "@vue/test-utils";

vi.mock("@/api/client", () => ({
	api: { support: { uploadTicketAttachment: vi.fn() } },
}));

import { api } from "@/api/client";
import {
	useTicketAttachments,
	validateTicketFile,
	TICKET_MAX_FILES,
	TICKET_MAX_BYTES,
} from "@/composables/useTicketAttachments.js";

const pngFile = (name = "a.png", size = 10) =>
	new File([new Uint8Array(size)], name, { type: "image/png" });

describe("validateTicketFile", () => {
	it("accepts a png under the cap", () => {
		expect(validateTicketFile(pngFile(), 0).ok).toBe(true);
	});
	it("rejects a disallowed type", () => {
		const txt = new File(["x"], "a.txt", { type: "text/plain" });
		expect(validateTicketFile(txt, 0).ok).toBe(false);
	});
	it("rejects oversize", () => {
		const big = new File([new Uint8Array(TICKET_MAX_BYTES + 1)], "b.png", { type: "image/png" });
		expect(validateTicketFile(big, 0).ok).toBe(false);
	});
	it("rejects when at the file-count cap", () => {
		expect(validateTicketFile(pngFile(), TICKET_MAX_FILES).ok).toBe(false);
	});
});

describe("useTicketAttachments", () => {
	beforeEach(() => {
		vi.stubGlobal("URL", { createObjectURL: () => "blob:x", revokeObjectURL() {} });
		api.support.uploadTicketAttachment.mockReset();
	});
	afterEach(() => vi.restoreAllMocks());

	it("uploads and records file_id with status done", async () => {
		api.support.uploadTicketAttachment.mockResolvedValue({
			file_id: "F1",
			file_name: "a.png",
			file_url: "/a.png",
			is_image: true,
		});
		const t = useTicketAttachments();
		await t.addFiles([pngFile()]);
		await flushPromises();
		expect(t.files.value).toHaveLength(1);
		expect(t.files.value[0].file_id).toBe("F1");
		expect(t.files.value[0].status).toBe("done");
	});

	it("marks a failed upload as error and keeps the row", async () => {
		api.support.uploadTicketAttachment.mockRejectedValue(new Error("boom"));
		const t = useTicketAttachments();
		await t.addFiles([pngFile()]);
		await flushPromises();
		expect(t.files.value[0].status).toBe("error");
	});

	it("consumeAttachmentIds returns only done ids and resets", async () => {
		api.support.uploadTicketAttachment.mockResolvedValue({
			file_id: "F1",
			file_name: "a.png",
			file_url: "/a.png",
			is_image: true,
		});
		const t = useTicketAttachments();
		await t.addFiles([pngFile()]);
		await flushPromises();
		expect(t.consumeAttachmentIds()).toEqual(["F1"]);
		expect(t.files.value).toHaveLength(0);
	});

	it("rejects files beyond the count cap without uploading them", async () => {
		api.support.uploadTicketAttachment.mockResolvedValue({ file_id: "F", is_image: true });
		const t = useTicketAttachments();
		const many = Array.from({ length: TICKET_MAX_FILES + 2 }, (_, i) => pngFile(`f${i}.png`));
		await t.addFiles(many);
		await flushPromises();
		const accepted = t.files.value.filter((f) => f.status !== "error");
		const rejected = t.files.value.filter((f) => f.status === "error");
		expect(accepted.length).toBe(TICKET_MAX_FILES);
		expect(rejected.length).toBe(2);
		expect(api.support.uploadTicketAttachment).toHaveBeenCalledTimes(TICKET_MAX_FILES);
	});

	it("extracts image files from a paste event and uploads them", async () => {
		api.support.uploadTicketAttachment.mockResolvedValue({
			file_id: "F2",
			file_name: "pasted.png",
			file_url: "/pasted.png",
			is_image: true,
		});
		const t = useTicketAttachments();
		const file = pngFile("pasted.png");
		const preventDefault = vi.fn();
		const event = {
			preventDefault,
			clipboardData: {
				items: [
					{ kind: "file", getAsFile: () => file },
					{ kind: "string", getAsFile: () => null },
				],
			},
		};
		t.handlePaste(event);
		await flushPromises();
		expect(preventDefault).toHaveBeenCalled();
		expect(t.files.value).toHaveLength(1);
		expect(t.files.value[0].file_id).toBe("F2");
	});

	it("does not preventDefault when the clipboard has no files", () => {
		const t = useTicketAttachments();
		const preventDefault = vi.fn();
		const event = { preventDefault, clipboardData: { items: [{ kind: "string", getAsFile: () => null }] } };
		t.handlePaste(event);
		expect(preventDefault).not.toHaveBeenCalled();
		expect(t.files.value).toHaveLength(0);
	});

	it("removeFile revokes the preview object URL and drops the entry", async () => {
		api.support.uploadTicketAttachment.mockResolvedValue({
			file_id: "F1",
			file_name: "a.png",
			file_url: "/a.png",
			is_image: true,
		});
		const revokeObjectURL = vi.fn();
		vi.stubGlobal("URL", { createObjectURL: () => "blob:x", revokeObjectURL });
		const t = useTicketAttachments();
		await t.addFiles([pngFile()]);
		await flushPromises();
		expect(t.files.value).toHaveLength(1);
		t.removeFile(0);
		expect(revokeObjectURL).toHaveBeenCalledWith("blob:x");
		expect(t.files.value).toHaveLength(0);
	});
});
