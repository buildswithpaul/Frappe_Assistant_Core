import { ref, reactive, computed } from "vue";
import { api } from "@/api/client";
import { logger } from "@/utils/logger";

/**
 * Support-ticket attachment state: pick/drop/paste files, pre-upload each via
 * Task 15's uploadTicketAttachment, and expose resolved file_ids for submit.
 * Modeled on useComposerAttachments.js + useMessageFileUpload.js.
 */

export const TICKET_MAX_FILES = 5;
export const TICKET_MAX_BYTES = 10 * 1024 * 1024;
export const TICKET_ACCEPT = "image/png,image/jpeg,image/gif,image/webp,application/pdf";

const ALLOWED_TYPES = new Set([
	"image/png",
	"image/jpeg",
	"image/gif",
	"image/webp",
	"application/pdf",
]);
const ALLOWED_EXT = /\.(png|jpe?g|gif|webp|pdf)$/i;

export function validateTicketFile(file, currentCount) {
	if (currentCount >= TICKET_MAX_FILES) {
		return { ok: false, error: `You can attach up to ${TICKET_MAX_FILES} files.` };
	}
	const typeOk = ALLOWED_TYPES.has(file.type) || ALLOWED_EXT.test(file.name || "");
	if (!typeOk) {
		return { ok: false, error: "Only images (PNG, JPG, GIF, WebP) and PDF are allowed." };
	}
	if (file.size > TICKET_MAX_BYTES) {
		return { ok: false, error: "Each file must be 10MB or smaller." };
	}
	return { ok: true };
}

let _seq = 0;

export function useTicketAttachments() {
	const files = ref([]);
	const fileInput = ref(null);

	const canAdd = computed(() => files.value.length < TICKET_MAX_FILES);

	function triggerFileInput() {
		fileInput.value?.click();
	}

	async function _upload(entry, file) {
		try {
			const res = await api.support.uploadTicketAttachment(file);
			entry.file_id = res.file_id;
			entry.file_name = res.file_name || file.name;
			entry.is_image = !!res.is_image;
			entry.status = "done";
		} catch (err) {
			logger.error("Ticket attachment upload failed:", err);
			entry.status = "error";
			entry.error = err?.userMessage || err?.message || "Upload failed";
		}
	}

	async function addFiles(list) {
		const incoming = Array.from(list || []);
		const jobs = [];
		for (const file of incoming) {
			const check = validateTicketFile(file, files.value.length);
			if (!check.ok) {
				files.value.push({
					id: ++_seq,
					file_id: null,
					file_name: file.name,
					is_image: (file.type || "").startsWith("image/"),
					previewUrl: null,
					status: "error",
					error: check.error,
				});
				continue;
			}
			const isImage = (file.type || "").startsWith("image/");
			const entry = reactive({
				id: ++_seq,
				file_id: null,
				file_name: file.name,
				is_image: isImage,
				previewUrl: isImage ? URL.createObjectURL(file) : null,
				status: "uploading",
				error: null,
				_file: file,
			});
			files.value.push(entry);
			jobs.push(_upload(entry, file));
		}
		await Promise.all(jobs);
	}

	function handlePaste(event) {
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
		const entry = files.value[index];
		if (entry?.previewUrl) URL.revokeObjectURL(entry.previewUrl);
		files.value.splice(index, 1);
	}

	function retryFile(index) {
		const entry = files.value[index];
		if (!entry?._file) return;
		entry.status = "uploading";
		entry.error = null;
		_upload(entry, entry._file);
	}

	function consumeAttachmentIds() {
		const ids = files.value.filter((f) => f.status === "done" && f.file_id).map((f) => f.file_id);
		reset();
		return ids;
	}

	function reset() {
		for (const f of files.value) if (f.previewUrl) URL.revokeObjectURL(f.previewUrl);
		files.value = [];
	}

	return {
		files,
		fileInput,
		canAdd,
		triggerFileInput,
		addFiles,
		handlePaste,
		removeFile,
		retryFile,
		consumeAttachmentIds,
		reset,
	};
}
