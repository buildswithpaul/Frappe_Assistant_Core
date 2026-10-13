export const ALLOWED_EXTENSIONS = [".pdf", ".md", ".txt", ".markdown", ".text"];
export const ALLOWED_TYPES = ["application/pdf", "text/markdown", "text/plain", "text/x-markdown"];
export const ACCEPT_ATTRIBUTE = ALLOWED_EXTENSIONS.join(",");
export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;

/** Returns an error message for a file the knowledge base would refuse, else null. */
export function validateKnowledgeFile(file) {
	const ext = "." + file.name.split(".").pop().toLowerCase();
	if (!ALLOWED_EXTENSIONS.includes(ext) && !ALLOWED_TYPES.includes(file.type)) {
		return `Unsupported file type: ${file.name}. Only PDF, Markdown, and Text files are allowed.`;
	}
	if (file.size > MAX_UPLOAD_BYTES) {
		return `File too large: ${file.name}. Maximum size is 10 MB.`;
	}
	return null;
}
