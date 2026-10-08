import { api } from "@/api/client";
import { logger } from "@/utils/logger";

/**
 * Pre-upload files via FACO's upload_message_file endpoint (matches widget behavior —
 * files are uploaded on selection, not on send). Uploads are keyed by the File, so a
 * send takes exactly the files still in the composer: a chip removed before sending
 * stays behind, and an upload still in flight is waited for rather than dropped.
 */
export function useMessageFileUpload() {
	const uploads = new Map();

	function handleFileUpload(files) {
		for (const file of files) {
			const upload = api.chat.uploadFile(file).catch((err) => {
				logger.error("File upload failed:", err);
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
