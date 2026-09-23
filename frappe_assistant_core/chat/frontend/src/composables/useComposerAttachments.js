import { ref } from "vue";
import { useToast } from "@/composables/useToast";

// Mirrors ALLOWED_UPLOAD_EXTENSIONS in chat/api/settings/uploads.py — the
// server hard-rejects anything else and the composer would be left showing a
// chip with no uploaded file behind it.
export const ALLOWED_UPLOAD_EXTENSIONS = [
	".pdf",
	".txt",
	".md",
	".png",
	".jpg",
	".jpeg",
	".gif",
	".webp",
	".csv",
	".json",
	".xml",
];

const ALLOWED_EXTENSION_SET = new Set(ALLOWED_UPLOAD_EXTENSIONS);

export const UPLOAD_ACCEPT_ATTR = ALLOWED_UPLOAD_EXTENSIONS.join(",");

function fileExtension(file) {
	const name = file.name || "";
	const dot = name.lastIndexOf(".");
	return dot === -1 ? "" : name.slice(dot).toLowerCase();
}

/**
 * Composer file-attachment state. Extracted from InputArea so the orchestrator
 * stays under the size budget. `emit` is the InputArea emit fn so file-upload
 * events still bubble identically.
 */
export function useComposerAttachments(emit) {
	const attachedFiles = ref([]);
	const fileInput = ref(null);
	const { showError } = useToast();

	function triggerFileInput() {
		fileInput.value?.click();
	}

	function addFiles(files) {
		const accepted = files.filter((f) => ALLOWED_EXTENSION_SET.has(fileExtension(f)));
		const rejected = files.filter((f) => !ALLOWED_EXTENSION_SET.has(fileExtension(f)));
		if (rejected.length) {
			showError(`Unsupported file type: ${rejected.map((f) => f.name || "unnamed").join(", ")}`);
		}
		if (!accepted.length) return;
		attachedFiles.value.push(...accepted);
		emit("file-upload", accepted);
	}

	function handleFileSelect(event) {
		addFiles(Array.from(event.target.files || []));
		event.target.value = "";
	}

	function handlePaste(event) {
		// Office apps (Excel, Word, …) put BOTH the copied text and a bitmap
		// rendition of it on the clipboard. When a text flavor is present the
		// user is pasting text — let the browser's default paste handle it.
		const text = event.clipboardData?.getData("text/plain") || "";
		if (text.trim()) return;

		const items = event.clipboardData?.items || [];
		const pasted = [];
		for (const it of items) {
			if (it.kind === "file") {
				const f = it.getAsFile();
				if (f) pasted.push(f);
			}
		}
		if (pasted.length) {
			event.preventDefault();
			addFiles(pasted);
		}
	}

	function removeFile(index) {
		attachedFiles.value.splice(index, 1);
	}

	function clearAttachments() {
		attachedFiles.value = [];
	}

	return {
		attachedFiles,
		fileInput,
		triggerFileInput,
		handleFileSelect,
		handlePaste,
		removeFile,
		clearAttachments,
	};
}
