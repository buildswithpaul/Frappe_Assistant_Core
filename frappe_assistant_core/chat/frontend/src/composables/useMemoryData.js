/**
 * Composable for managing user memory data — list, delete, stats.
 *
 * Follows the same pattern as useBillingData.js: encapsulates all state,
 * loading logic, and action handlers for the MemorySettings component.
 */

import { ref, computed } from "vue";
import { api } from "@/api/client";
import { logger } from "@/utils/logger";

export function useMemoryData() {
	// State
	const loading = ref(true);
	const error = ref(null);
	const memories = ref([]);
	const stats = ref({
		total: 0,
		by_type: { preference: 0, summary: 0, fact: 0 },
		total_accesses: 0,
	});
	const pagination = ref({ total: 0, limit: 200, offset: 0, has_more: false });

	// Filter state
	const activeFilter = ref(null); // null = all, 'preference', 'summary', 'fact'

	// Action states
	const deleting = ref(null); // memory_id being deleted, or 'all'
	const deleteConfirmId = ref(null); // memory_id awaiting confirmation
	const showClearAllConfirm = ref(false);
	const clearAllInput = ref("");

	// Computed
	const groupedMemories = computed(() => {
		const source = activeFilter.value
			? memories.value.filter((m) => m.memory_type === activeFilter.value)
			: memories.value;

		const groups = {};
		for (const m of source) {
			const type = m.memory_type || "fact";
			if (!groups[type]) groups[type] = [];
			groups[type].push(m);
		}
		return groups;
	});

	const isEmpty = computed(() => stats.value.total === 0);
	const canClearAll = computed(() => clearAllInput.value === "DELETE");

	// Data loading
	async function loadData() {
		loading.value = true;
		error.value = null;
		try {
			const [memoryResult, statsResult] = await Promise.all([
				api.memories.list(null, 200, 0),
				api.memories.getStats(),
			]);
			memories.value = memoryResult?.memories || [];
			pagination.value = memoryResult?.pagination || { total: 0 };
			stats.value = statsResult || {
				total: 0,
				by_type: { preference: 0, summary: 0, fact: 0 },
				total_accesses: 0,
			};
		} catch (err) {
			error.value = err.message || "Failed to load memories";
			logger.error("Memory load error:", err);
		} finally {
			loading.value = false;
		}
	}

	function setFilter(type) {
		activeFilter.value = type === activeFilter.value ? null : type;
	}

	// Delete single memory
	function confirmDelete(memoryId) {
		deleteConfirmId.value = memoryId;
	}

	function cancelDelete() {
		deleteConfirmId.value = null;
	}

	async function executeDelete(memoryId) {
		deleting.value = memoryId;
		error.value = null;
		try {
			await api.memories.delete(memoryId);
			// Remove from local state
			const idx = memories.value.findIndex((m) => m.memory_id === memoryId);
			if (idx !== -1) {
				const removed = memories.value[idx];
				memories.value.splice(idx, 1);
				// Update stats locally
				if (
					removed.memory_type &&
					stats.value.by_type[removed.memory_type] !== undefined
				) {
					stats.value.by_type[removed.memory_type]--;
				}
				stats.value.total = Math.max(0, stats.value.total - 1);
			}
			deleteConfirmId.value = null;
		} catch (err) {
			error.value = err.message || "Failed to delete memory";
		} finally {
			deleting.value = null;
		}
	}

	// Update memory content
	async function executeUpdate(memoryId, newContent) {
		error.value = null;
		try {
			await api.memories.update(memoryId, newContent);
			// Update local state
			const idx = memories.value.findIndex((m) => m.memory_id === memoryId);
			if (idx !== -1) {
				memories.value[idx].content = newContent;
			}
		} catch (err) {
			error.value = err.message || "Failed to update memory";
		}
	}

	// Clear all memories
	function openClearAll() {
		showClearAllConfirm.value = true;
		clearAllInput.value = "";
	}

	function closeClearAll() {
		showClearAllConfirm.value = false;
		clearAllInput.value = "";
	}

	async function executeClearAll() {
		if (!canClearAll.value) return;
		deleting.value = "all";
		error.value = null;
		try {
			await api.memories.deleteAll();
			memories.value = [];
			stats.value = {
				total: 0,
				by_type: { preference: 0, summary: 0, fact: 0 },
				total_accesses: 0,
			};
			showClearAllConfirm.value = false;
			clearAllInput.value = "";
		} catch (err) {
			error.value = err.message || "Failed to clear memories";
		} finally {
			deleting.value = null;
		}
	}

	return {
		// State
		loading,
		error,
		memories,
		stats,
		pagination,
		activeFilter,
		deleting,
		deleteConfirmId,
		showClearAllConfirm,
		clearAllInput,
		// Computed
		groupedMemories,
		isEmpty,
		canClearAll,
		// Actions
		loadData,
		setFilter,
		confirmDelete,
		cancelDelete,
		executeDelete,
		executeUpdate,
		openClearAll,
		closeClearAll,
		executeClearAll,
	};
}
