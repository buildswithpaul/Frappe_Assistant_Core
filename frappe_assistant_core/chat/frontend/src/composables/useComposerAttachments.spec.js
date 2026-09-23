import { describe, it, expect, vi, beforeEach } from "vitest";
import { useComposerAttachments, UPLOAD_ACCEPT_ATTR } from "./useComposerAttachments";

const showError = vi.fn();
vi.mock("@/composables/useToast", () => ({
	useToast: () => ({ showError }),
}));

const makeFile = (name = "screenshot.png", type = "image/png") =>
	new File(["x"], name, { type });

function makePasteEvent(items, text = "") {
	return {
		clipboardData: {
			items,
			getData: (flavor) => (flavor === "text/plain" ? text : ""),
		},
		preventDefault: vi.fn(),
	};
}

describe("useComposerAttachments", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it("stages pasted clipboard files and forwards them to the upload pipeline", () => {
		const emit = vi.fn();
		const composer = useComposerAttachments(emit);

		const file = makeFile();
		const event = makePasteEvent([{ kind: "file", getAsFile: () => file }]);
		composer.handlePaste(event);

		expect(event.preventDefault).toHaveBeenCalled();
		expect(composer.attachedFiles.value).toEqual([file]);
		expect(emit).toHaveBeenCalledWith("file-upload", [file]);
	});

	it("ignores text-only pastes so normal typing/pasting is untouched", () => {
		const emit = vi.fn();
		const composer = useComposerAttachments(emit);

		const event = makePasteEvent([{ kind: "string", getAsFile: () => null }], "plain text");
		composer.handlePaste(event);

		expect(event.preventDefault).not.toHaveBeenCalled();
		expect(composer.attachedFiles.value).toEqual([]);
		expect(emit).not.toHaveBeenCalled();
	});

	it("prefers the text flavor when the clipboard carries both text and a bitmap (Excel/Word copies)", () => {
		const emit = vi.fn();
		const composer = useComposerAttachments(emit);

		const bitmap = makeFile("image.png");
		const event = makePasteEvent(
			[
				{ kind: "string", getAsFile: () => null },
				{ kind: "file", getAsFile: () => bitmap },
			],
			"Region\tRevenue\nSouth\t120"
		);
		composer.handlePaste(event);

		// The browser's default text paste must run — nothing staged.
		expect(event.preventDefault).not.toHaveBeenCalled();
		expect(composer.attachedFiles.value).toEqual([]);
		expect(emit).not.toHaveBeenCalled();
	});

	it("attaches the file when a string item is present but the text flavor is empty (browser image copy)", () => {
		const emit = vi.fn();
		const composer = useComposerAttachments(emit);

		const file = makeFile("shot.png");
		const event = makePasteEvent([
			{ kind: "string", getAsFile: () => null },
			{ kind: "file", getAsFile: () => file },
		]);
		composer.handlePaste(event);

		expect(event.preventDefault).toHaveBeenCalled();
		expect(composer.attachedFiles.value).toEqual([file]);
		expect(emit).toHaveBeenCalledWith("file-upload", [file]);
	});

	it("rejects pasted files the server would refuse and tells the user", () => {
		const emit = vi.fn();
		const composer = useComposerAttachments(emit);

		const zip = makeFile("archive.zip", "application/zip");
		const event = makePasteEvent([{ kind: "file", getAsFile: () => zip }]);
		composer.handlePaste(event);

		expect(composer.attachedFiles.value).toEqual([]);
		expect(emit).not.toHaveBeenCalled();
		expect(showError).toHaveBeenCalledWith(expect.stringContaining("archive.zip"));
	});

	it("stages allowed files and reports rejected ones from a mixed paste", () => {
		const emit = vi.fn();
		const composer = useComposerAttachments(emit);

		const png = makeFile("shot.png");
		const mov = makeFile("clip.mov", "video/quicktime");
		const event = makePasteEvent([
			{ kind: "file", getAsFile: () => png },
			{ kind: "file", getAsFile: () => mov },
		]);
		composer.handlePaste(event);

		expect(composer.attachedFiles.value).toEqual([png]);
		expect(emit).toHaveBeenCalledWith("file-upload", [png]);
		expect(showError).toHaveBeenCalledWith(expect.stringContaining("clip.mov"));
	});

	it("keeps the picker flow working through the shared addFiles path", () => {
		const emit = vi.fn();
		const composer = useComposerAttachments(emit);

		const file = makeFile("report.pdf", "application/pdf");
		const event = { target: { files: [file], value: "report.pdf" } };
		composer.handleFileSelect(event);

		expect(composer.attachedFiles.value).toEqual([file]);
		expect(emit).toHaveBeenCalledWith("file-upload", [file]);
		expect(event.target.value).toBe("");
	});

	it("exposes an accept attribute that matches the shared allowlist", () => {
		expect(UPLOAD_ACCEPT_ATTR).toContain(".png");
		expect(UPLOAD_ACCEPT_ATTR).toContain(".pdf");
		// Server rejects Office formats — the picker must not advertise them.
		expect(UPLOAD_ACCEPT_ATTR).not.toContain(".xlsx");
		expect(UPLOAD_ACCEPT_ATTR).not.toContain(".docx");
	});
});
