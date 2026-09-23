import { ref } from "vue";
import { api } from "@/api/client";

const ALLOWED_TYPES = ["application/pdf", "text/markdown", "text/plain", "text/x-markdown"];
const ALLOWED_EXTENSIONS = [".pdf", ".md", ".txt", ".markdown", ".text"];

export function useDocumentUpload({ onUploaded, onFilesSelected }) {
	const uploads = ref([]);
	const uploadError = ref(null);
	const isDragging = ref(false);
	const fileInput = ref(null);
	const pendingFiles = ref([]);

	let dragCounter = 0;

	function triggerUpload() {
		fileInput.value?.click();
	}

	function handleFileSelect(event) {
		const files = Array.from(event.target.files || []);
		if (files.length > 0) {
			selectFiles(files);
		}
		event.target.value = "";
	}

	function validateFile(file) {
		const ext = "." + file.name.split(".").pop().toLowerCase();
		if (!ALLOWED_EXTENSIONS.includes(ext) && !ALLOWED_TYPES.includes(file.type)) {
			return `Unsupported file type: ${file.name}. Only PDF, Markdown, and Text files are allowed.`;
		}
		if (file.size > 10 * 1024 * 1024) {
			return `File too large: ${file.name}. Maximum size is 10 MB.`;
		}
		return null;
	}

	function getFileType(file) {
		const ext = file.name.split(".").pop().toLowerCase();
		if (ext === "pdf") return "PDF";
		if (["md", "markdown"].includes(ext)) return "Markdown";
		return "Text";
	}

	function selectFiles(files) {
		uploadError.value = null;

		// Validate all files first
		const validFiles = [];
		for (const file of files) {
			const error = validateFile(file);
			if (error) {
				uploadError.value = error;
			} else {
				validFiles.push(file);
			}
		}

		if (validFiles.length > 0) {
			pendingFiles.value = validFiles;
			if (onFilesSelected) {
				onFilesSelected(validFiles);
			}
		}
	}

	function cancelPending() {
		pendingFiles.value = [];
	}

	async function confirmUpload(visibility = "public", sharedWith = null) {
		const files = [...pendingFiles.value];
		pendingFiles.value = [];
		uploadError.value = null;

		for (const file of files) {
			const uploadId = Date.now() + "-" + Math.random().toString(36).slice(2);
			const uploadEntry = {
				id: uploadId,
				name: file.name,
				type: getFileType(file),
				progress: 0,
			};
			uploads.value.unshift(uploadEntry);
			uploadEntry.progress = 30;

			try {
				await api.documents.upload(file, { visibility, sharedWith });
				uploadEntry.progress = 100;

				setTimeout(() => {
					uploads.value = uploads.value.filter((u) => u.id !== uploadId);
				}, 500);

				if (onUploaded) await onUploaded();
			} catch (e) {
				uploads.value = uploads.value.filter((u) => u.id !== uploadId);
				uploadError.value = e.message || `Failed to upload ${file.name}`;
			}
		}
	}

	function onDragOver() {
		dragCounter++;
		isDragging.value = true;
	}

	function onDragLeave() {
		dragCounter--;
		if (dragCounter <= 0) {
			isDragging.value = false;
			dragCounter = 0;
		}
	}

	function onDrop(event) {
		isDragging.value = false;
		dragCounter = 0;

		const files = Array.from(event.dataTransfer?.files || []);
		if (files.length > 0) {
			selectFiles(files);
		}
	}

	return {
		uploads,
		uploadError,
		isDragging,
		fileInput,
		pendingFiles,
		triggerUpload,
		handleFileSelect,
		confirmUpload,
		cancelPending,
		onDragOver,
		onDragLeave,
		onDrop,
	};
}
