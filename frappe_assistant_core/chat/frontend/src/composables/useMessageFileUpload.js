import { ref } from "vue";
import { api } from "@/api/client";
import { logger } from "@/utils/logger";

/**
 * Pre-upload files via FACO's upload_message_file endpoint (matches widget behavior —
 * files are uploaded on selection, not on send). Exposes the accumulated upload
 * results so the caller can attach them to the next outgoing message, then reset.
 */
export function useMessageFileUpload() {
	const uploadedFiles = ref([]);

	async function handleFileUpload(files) {
		for (const file of files) {
			try {
				const result = await api.chat.uploadFile(file);
				uploadedFiles.value.push(result);
			} catch (err) {
				logger.error("File upload failed:", err);
			}
		}
	}

	function consumeUploadedFiles() {
		const files = uploadedFiles.value;
		uploadedFiles.value = [];
		return files;
	}

	return { uploadedFiles, handleFileUpload, consumeUploadedFiles };
}
