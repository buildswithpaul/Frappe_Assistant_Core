import { describe, it, expect, vi, beforeEach } from "vitest";
import { useMessageFileUpload } from "./useMessageFileUpload";
import { friendlyError } from "@/api/_core";
import { api } from "@/api/client";
import { setUploadLimit } from "@/utils/uploadLimit";

vi.mock("@/api/client", () => ({ api: { chat: { uploadFile: vi.fn() } } }));
vi.mock("@/utils/logger", () => ({ logger: { error: vi.fn() } }));

const showError = vi.fn();
vi.mock("@/composables/useToast", () => ({
	useToast: () => ({ showError }),
}));

const makeFile = (name) => new File(["x"], name, { type: "application/pdf" });
const uploaded = (file) => ({ file_name: file.name, file_url: `/private/files/${file.name}` });

function deferred() {
	let resolve;
	const promise = new Promise((r) => (resolve = r));
	return { promise, resolve };
}

const REJECTION = "File content does not match its extension: .xlsx";

// What Frappe returns for frappe.throw(..., ValidationError): HTTP 417 with the
// message triple-encoded in _server_messages.
const rejectionBody = JSON.stringify({
	exception: `frappe.exceptions.ValidationError: ${REJECTION}`,
	exc_type: "ValidationError",
	_server_messages: JSON.stringify([
		JSON.stringify({ message: REJECTION, title: "Message", indicator: "red", raise_exception: 1 }),
	]),
});

describe("useMessageFileUpload", () => {
	beforeEach(() => {
		vi.clearAllMocks();
		setUploadLimit(null);
	});

	it("waits for an upload still in flight when the user sends", async () => {
		// The composer uploads on selection, so Send can land before a slow upload has finished.
		const file = makeFile("invoice.pdf");
		const upload = deferred();
		api.chat.uploadFile.mockReturnValue(upload.promise);
		const { handleFileUpload, consumeUploadedFiles } = useMessageFileUpload();

		handleFileUpload([file]);
		const sent = consumeUploadedFiles([file]);
		upload.resolve(uploaded(file));

		expect(await sent).toEqual([uploaded(file)]);
	});

	it("sends only the files still in the composer, not one whose chip was removed", async () => {
		const kept = makeFile("kept.pdf");
		const removed = makeFile("removed.pdf");
		api.chat.uploadFile.mockImplementation(async (file) => uploaded(file));
		const { handleFileUpload, consumeUploadedFiles } = useMessageFileUpload();

		handleFileUpload([kept, removed]);

		expect(await consumeUploadedFiles([kept])).toEqual([uploaded(kept)]);
	});

	it("does not carry a file into a later message once it has been sent", async () => {
		const file = makeFile("once.pdf");
		api.chat.uploadFile.mockImplementation(async (f) => uploaded(f));
		const { handleFileUpload, consumeUploadedFiles } = useMessageFileUpload();

		handleFileUpload([file]);
		await consumeUploadedFiles([file]);

		expect(await consumeUploadedFiles([file])).toEqual([]);
	});

	it("drops a failed upload and still sends the rest", async () => {
		const good = makeFile("good.pdf");
		const bad = makeFile("bad.pdf");
		api.chat.uploadFile.mockImplementation(async (file) => {
			if (file === bad) throw new Error("413");
			return uploaded(file);
		});
		const { handleFileUpload, consumeUploadedFiles } = useMessageFileUpload();

		handleFileUpload([good, bad]);

		expect(await consumeUploadedFiles([good, bad])).toEqual([uploaded(good)]);
	});

	it("discards the uploads of files sent with a card answer", async () => {
		const file = makeFile("answer.pdf");
		api.chat.uploadFile.mockImplementation(async (f) => uploaded(f));
		const { handleFileUpload, consumeUploadedFiles, discardUploads } = useMessageFileUpload();

		handleFileUpload([file]);
		discardUploads([file]);

		expect(await consumeUploadedFiles([file])).toEqual([]);
	});

	it("shows the server's rejection and drops that file's chip", async () => {
		const bad = new File(["MZ"], "payroll.xlsx");
		api.chat.uploadFile.mockRejectedValue(friendlyError({ status: 417 }, rejectionBody));
		const onFailed = vi.fn();
		const { handleFileUpload, consumeUploadedFiles } = useMessageFileUpload();

		handleFileUpload([bad], onFailed);

		expect(await consumeUploadedFiles([bad])).toEqual([]);
		expect(showError).toHaveBeenCalledWith(`payroll.xlsx: ${REJECTION}`);
		expect(onFailed.mock.calls[0][0]).toBe(bad);
	});

	it("drops only the rejected file's chip when another file uploads", async () => {
		const bad = new File(["MZ"], "payroll.xlsx");
		const good = new File(["a,b"], "customers.csv");
		api.chat.uploadFile.mockImplementation(async (file) => {
			if (file === bad) throw friendlyError({ status: 417 }, rejectionBody);
			return uploaded(file);
		});
		const onFailed = vi.fn();
		const { handleFileUpload, consumeUploadedFiles } = useMessageFileUpload();

		handleFileUpload([bad, good], onFailed);

		expect(await consumeUploadedFiles([bad, good])).toEqual([uploaded(good)]);
		expect(onFailed).toHaveBeenCalledTimes(1);
		expect(onFailed.mock.calls[0][0]).toBe(bad);
	});

	it("refuses a file over the site's limit before uploading it, naming the limit (#33987)", async () => {
		// Frappe answers a request over its limit with an HTML 413, before FACO can say why
		setUploadLimit(25 * 1048576);
		const big = new File(["x"], "ledger.xlsx");
		Object.defineProperty(big, "size", { value: 30 * 1048576 });
		const onFailed = vi.fn();
		const { handleFileUpload, consumeUploadedFiles } = useMessageFileUpload();

		handleFileUpload([big], onFailed);

		expect(api.chat.uploadFile).not.toHaveBeenCalled();
		expect(showError).toHaveBeenCalledWith("ledger.xlsx: Larger than this site's 25 MB upload limit.");
		expect(onFailed.mock.calls[0][0]).toBe(big);
		expect(await consumeUploadedFiles([big])).toEqual([]);
	});
});
