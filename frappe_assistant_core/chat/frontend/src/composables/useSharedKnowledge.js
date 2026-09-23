/**
 * Composable for managing shared knowledge — an editable markdown document
 * in the knowledge base that goes through the RAG pipeline.
 */

import { ref, computed } from "vue";
import { api } from "@/api/client";
import { logger } from "@/utils/logger";

export function useSharedKnowledge() {
	const content = ref("");
	const loading = ref(true);
	const saving = ref(false);
	const error = ref(null);
	const embeddingStatus = ref("Pending");
	const totalChunks = ref(0);
	const documentId = ref(null);
	const isEditing = ref(false);
	const editContent = ref("");

	let pollTimer = null;

	const isEmpty = computed(() => !content.value || !content.value.trim());
	const isProcessing = computed(
		() => embeddingStatus.value === "Processing" || embeddingStatus.value === "Pending"
	);

	function startPolling() {
		if (pollTimer) return;
		pollTimer = setInterval(() => load(), 5000);
	}

	function stopPolling() {
		if (pollTimer) {
			clearInterval(pollTimer);
			pollTimer = null;
		}
	}

	async function load() {
		loading.value = true;
		error.value = null;
		try {
			const result = await api.sharedKnowledge.get();
			content.value = result?.content || "";
			embeddingStatus.value = result?.embedding_status || "Pending";
			totalChunks.value = result?.total_chunks || 0;
			documentId.value = result?.document_id || null;

			// Stop polling once processing is done
			if (!isProcessing.value) {
				stopPolling();
			}
		} catch (err) {
			error.value = err.message || "Failed to load team notes";
			logger.error("Team notes load error:", err);
			stopPolling();
		} finally {
			loading.value = false;
		}
	}

	function startEditing() {
		editContent.value = content.value;
		isEditing.value = true;
	}

	function cancelEditing() {
		isEditing.value = false;
		editContent.value = "";
	}

	async function save() {
		saving.value = true;
		error.value = null;
		try {
			await api.sharedKnowledge.update(editContent.value);
			content.value = editContent.value;
			embeddingStatus.value = "Processing";
			isEditing.value = false;
			editContent.value = "";
			startPolling();
			return true;
		} catch (err) {
			error.value = err.message || "Failed to save team notes";
			return false;
		} finally {
			saving.value = false;
		}
	}

	async function shareMemory(memoryId) {
		try {
			await api.sharedKnowledge.shareMemory(memoryId);
			embeddingStatus.value = "Processing";
			startPolling();
			await load();
			return { success: true };
		} catch (err) {
			return { success: false, error: err.message || "Failed to share memory" };
		}
	}

	return {
		// State
		content,
		loading,
		saving,
		error,
		embeddingStatus,
		totalChunks,
		documentId,
		isEditing,
		editContent,
		// Computed
		isEmpty,
		isProcessing,
		// Actions
		load,
		startEditing,
		cancelEditing,
		save,
		shareMemory,
		stopPolling,
	};
}
