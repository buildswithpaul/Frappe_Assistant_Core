import { api } from "@/api/client";
import { useToast } from "@/composables/useToast";
import { __ } from "@/utils/i18n";
import { logger } from "@/utils/logger";
import { megabytes, uploadLimit } from "@/utils/uploadLimit";

/**
 * Pre-upload files via FACO's upload_message_file endpoint (matches widget behavior —
 * files are uploaded on selection, not on send). Uploads are keyed by the File, so a
 * send takes exactly the files still in the composer: a chip removed before sending
 * stays behind, and an upload still in flight is waited for rather than dropped.
 */
export function useMessageFileUpload() {
	const uploads = new Map();
	const { showError } = useToast();

	// `onFailed` is the composer's callback (useComposerAttachments) that drops
	// the chip for a file the server rejected.
	function handleFileUpload(files, onFailed) {
		for (const file of files) {
			const limit = uploadLimit();
			if (limit && file.size > limit) {
				// Frappe would refuse it before FACO could say why (#33987)
				showError(
					`${file.name}: ${__("Larger than this site's {0} upload limit.", [megabytes(limit)])}`
				);
				onFailed?.(file);
				continue;
			}
			const upload = api.chat.uploadFile(file).catch((err) => {
				logger.error("File upload failed:", err);
				showError(`${file.name}: ${err?.userMessage || err?.message || __("Upload failed")}`);
				uploads.delete(file);
				onFailed?.(file);
				return null;
			});
			uploads.set(file, upload);
		}
	}

	function discardUploads(files = []) {
		files.forEach((file) => uploads.delete(file));
	}

	/** The upload results for `files`, once every one of them has finished uploading. */
	async function consumeUploadedFiles(files = []) {
		const pending = files.map((file) => uploads.get(file)).filter(Boolean);
		discardUploads(files);
		return (await Promise.all(pending)).filter(Boolean);
	}

	return { handleFileUpload, consumeUploadedFiles, discardUploads };
}
