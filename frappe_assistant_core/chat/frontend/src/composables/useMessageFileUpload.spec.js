import { describe, it, expect, vi, beforeEach } from "vitest";
import { useMessageFileUpload } from "./useMessageFileUpload";
import { api } from "@/api/client";

vi.mock("@/api/client", () => ({ api: { chat: { uploadFile: vi.fn() } } }));
vi.mock("@/utils/logger", () => ({ logger: { error: vi.fn() } }));

const makeFile = (name) => new File(["x"], name, { type: "application/pdf" });
const uploaded = (file) => ({ file_name: file.name, file_url: `/private/files/${file.name}` });

function deferred() {
	let resolve;
	const promise = new Promise((r) => (resolve = r));
	return { promise, resolve };
}

describe("useMessageFileUpload", () => {
	beforeEach(() => vi.clearAllMocks());

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
});
