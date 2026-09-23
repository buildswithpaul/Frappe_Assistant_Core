<template>
	<div class="memory-settings">
		<!-- Loading -->
		<div v-if="loading" class="loading-state">
			<div class="spinner"></div>
			<p>Loading memories...</p>
		</div>

		<!-- Error -->
		<div v-else-if="error" class="error-banner">
			<p>{{ error }}</p>
			<button @click="loadData" class="retry-btn">Retry</button>
		</div>

		<!-- Content -->
		<template v-else>
			<!-- Stats Card -->
			<div class="stats-card">
				<div class="stats-header">
					<h3 class="section-title">Your Memories</h3>
					<span class="stats-total"
						>{{ stats.total }}
						{{ stats.total === 1 ? "memory" : "memories" }} stored</span
					>
				</div>
				<div v-if="stats.total > 0" class="stats-pills">
					<button
						v-for="type in memoryTypes"
						:key="type.key"
						class="type-pill"
						:class="[`type-${type.key}`, { active: activeFilter === type.key }]"
						@click="setFilter(type.key)"
					>
						{{ type.label }}: {{ stats.by_type[type.key] || 0 }}
					</button>
					<button
						v-if="activeFilter"
						class="type-pill type-clear"
						@click="setFilter(activeFilter)"
					>
						Clear filter
					</button>
				</div>
			</div>

			<!-- View Toggle (only show when there are memories) -->
			<div v-if="!isEmpty" class="view-toggle">
				<button
					:class="['toggle-btn', { active: viewMode === 'summary' }]"
					@click="
						viewMode = 'summary';
						if (!summary && !summaryLoading) loadSummary();
					"
				>
					Summary
				</button>
				<button
					:class="['toggle-btn', { active: viewMode === 'memories' }]"
					@click="viewMode = 'memories'"
				>
					Memories
				</button>
			</div>

			<!-- Empty State -->
			<div v-if="isEmpty" class="empty-state">
				<svg class="empty-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="1.5"
						d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
					/>
				</svg>
				<p class="empty-title">No memories yet</p>
				<p class="empty-description">
					As you chat, I'll learn about your preferences and remember important details
					to personalize your experience.
				</p>
			</div>

			<!-- Memory Narrative -->
			<MemoryNarrative
				v-if="!isEmpty && viewMode === 'memories'"
				:sections="narrativeSections"
				@delete="handleDelete"
				@share="handleShare"
				@edit="handleEdit"
			/>

			<!-- AI Summary -->
			<MemorySummary
				v-if="!isEmpty && viewMode === 'summary'"
				:summary="summary"
				:loading="summaryLoading"
				:error="summaryError"
				:stale="summaryStale"
				@regenerate="regenerateSummary"
			/>

			<!-- Danger Zone -->
			<div v-if="!isEmpty" class="danger-zone">
				<hr class="divider" />
				<h3 class="section-title danger-title">Danger Zone</h3>
				<div class="danger-item">
					<div class="danger-info">
						<label class="setting-label">Clear all memories</label>
						<p class="setting-description">
							Permanently remove all stored memories. The AI will no longer have
							personalized context about you.
						</p>
					</div>
					<button v-if="!showClearAllConfirm" class="danger-btn" @click="openClearAll">
						Clear All
					</button>
					<div v-else class="clear-confirm">
						<p class="confirm-prompt">Type <strong>DELETE</strong> to confirm:</p>
						<div class="confirm-row">
							<input
								v-model="clearAllInput"
								type="text"
								class="confirm-input"
								placeholder="DELETE"
								@keyup.enter="handleClearAll"
							/>
							<button
								class="danger-btn danger-btn-confirm"
								:disabled="!canClearAll || deleting === 'all'"
								@click="handleClearAll"
							>
								{{ deleting === "all" ? "Clearing..." : "Clear" }}
							</button>
							<button class="cancel-btn" @click="closeClearAll">Cancel</button>
						</div>
					</div>
				</div>
			</div>
		</template>
	</div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { useMemoryData } from "@/composables/useMemoryData";
import { useSharedKnowledge } from "@/composables/useSharedKnowledge";
import { useMemoryNarrative } from "@/composables/useMemoryNarrative";
import { useMemorySummary } from "@/composables/useMemorySummary";
import { useUserStore } from "@/stores/userStore";
import MemoryNarrative from "./MemoryNarrative.vue";
import MemorySummary from "./MemorySummary.vue";

const {
	loading,
	error,
	memories,
	stats,
	activeFilter,
	deleting,
	showClearAllConfirm,
	clearAllInput,
	isEmpty,
	canClearAll,
	loadData,
	setFilter,
	executeDelete,
	executeUpdate,
	openClearAll,
	closeClearAll,
	executeClearAll,
} = useMemoryData();

const { shareMemory } = useSharedKnowledge();
const { sections: narrativeSections } = useMemoryNarrative(memories, activeFilter);
// Keyed by user so a shared browser never paints one person's profile for
// another before the request that would have corrected it comes back.
const userStore = useUserStore();
const {
	summary,
	summaryLoading,
	summaryError,
	summaryStale,
	loadSummary,
	regenerateSummary,
	clearSummary,
} = useMemorySummary(userStore.user);

const viewMode = ref("summary");

async function handleDelete(memoryId) {
	await executeDelete(memoryId);
	// Not clearSummary(): the profile built from the remaining memories is
	// still the best thing to show. The server marks it stale and refreshes
	// behind this call, so re-reading keeps the panel populated throughout.
	loadSummary();
}

async function handleEdit({ memoryId, content }) {
	await executeUpdate(memoryId, content);
	loadSummary();
}

// Clearing every memory is the one case that must forget the summary rather
// than refresh it: the profile is built from memories the user has just
// erased, and the browser copy would otherwise paint it straight back on the
// next visit — the one thing they asked us to stop doing.
async function handleClearAll() {
	await executeClearAll();
	clearSummary();
}

async function handleShare(memoryId) {
	const result = await shareMemory(memoryId);
	if (!result.success) {
		error.value = result.error;
	}
}

const memoryTypes = [
	{ key: "preference", label: "Preferences" },
	{ key: "fact", label: "Facts" },
	{ key: "summary", label: "Summaries" },
	{ key: "correction", label: "Corrections" },
];

onMounted(() => {
	loadData();
	loadSummary();
});
</script>

<style scoped>
.memory-settings {
	width: 100%;
	max-width: 1100px;
}

/* Loading */
.loading-state {
	display: flex;
	flex-direction: column;
	align-items: center;
	gap: 0.75rem;
	padding: 3rem 0;
	color: var(--ql-text-muted);
}

.spinner {
	width: 24px;
	height: 24px;
	border: 2px solid var(--ql-border);
	border-top-color: var(--ql-accent);
	border-radius: 50%;
	animation: spin 0.6s linear infinite;
}

@keyframes spin {
	to {
		transform: rotate(360deg);
	}
}

/* Error */
.error-banner {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding: 0.75rem 1rem;
	background: rgba(239, 68, 68, 0.08);
	border: 1px solid rgba(239, 68, 68, 0.2);
	border-radius: 0.5rem;
	color: var(--ql-danger);
	font-size: 0.875rem;
	margin-bottom: 1rem;
}

.retry-btn {
	padding: 0.375rem 0.75rem;
	font-size: 0.75rem;
	font-weight: 500;
	color: var(--ql-danger);
	background: none;
	border: 1px solid var(--ql-danger);
	border-radius: 0.25rem;
	cursor: pointer;
}

/* Stats Card */
.stats-card {
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 12px;
	padding: 24px;
	margin-bottom: 24px;
}

.stats-header {
	display: flex;
	align-items: baseline;
	gap: 0.75rem;
	margin-bottom: 0.75rem;
}

.section-title {
	font-size: 1rem;
	font-weight: 600;
	color: var(--ql-text);
	margin: 0;
}

.stats-total {
	font-size: 0.8rem;
	color: var(--ql-text-muted);
}

.stats-pills {
	display: flex;
	gap: 0.5rem;
	flex-wrap: wrap;
}

.type-pill {
	padding: 0.25rem 0.625rem;
	font-size: 0.75rem;
	font-weight: 500;
	border-radius: 1rem;
	border: 1px solid var(--ql-border);
	background: none;
	color: var(--ql-text-muted);
	cursor: pointer;
	transition: all 0.15s ease;
}

.type-pill:hover {
	background: var(--ql-subtle);
}

.type-pill.active {
	border-color: transparent;
}

.type-pill.type-preference.active {
	background: var(--ql-accent-soft);
	color: var(--ql-accent);
}

.type-pill.type-fact.active {
	background: rgba(16, 185, 129, 0.12);
	color: #10b981;
}

.type-pill.type-summary.active {
	background: rgba(245, 158, 11, 0.12);
	color: #f59e0b;
}

.type-pill.type-correction.active {
	background: rgba(239, 68, 68, 0.12);
	color: #ef4444;
}

.type-pill.type-clear {
	font-size: 0.7rem;
	color: var(--ql-text-muted);
	border-style: dashed;
}

/* View Toggle */
.view-toggle {
	display: inline-flex;
	border: 1px solid var(--ql-border);
	border-radius: 8px;
	overflow: hidden;
	margin-top: 0.75rem;
	margin-bottom: 0.5rem;
}

.toggle-btn {
	padding: 0.35rem 0.85rem;
	font-size: 0.8rem;
	font-weight: 500;
	border: none;
	background: transparent;
	color: var(--ql-text-muted);
	cursor: pointer;
	transition: all 0.15s ease;
}

.toggle-btn:not(:last-child) {
	border-right: 1px solid var(--ql-border);
}

.toggle-btn.active {
	background: var(--ql-accent);
	color: white;
}

.toggle-btn:hover:not(.active) {
	background: var(--ql-subtle);
}

/* Empty State */
.empty-state {
	display: flex;
	flex-direction: column;
	align-items: center;
	text-align: center;
	padding: 3rem 1rem;
}

.empty-icon {
	width: 48px;
	height: 48px;
	color: var(--ql-text-muted);
	opacity: 0.5;
	margin-bottom: 1rem;
}

.empty-title {
	font-size: 1rem;
	font-weight: 600;
	color: var(--ql-text);
	margin-bottom: 0.5rem;
}

.empty-description {
	font-size: 0.85rem;
	color: var(--ql-text-muted);
	max-width: 360px;
	line-height: 1.5;
}

/* Danger Zone */
.danger-zone {
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 12px;
	padding: 24px;
	margin-bottom: 24px;
}

.divider {
	border: none;
	border-top: 1px solid var(--ql-border);
	margin: 0 0 1rem 0;
}

.danger-title {
	color: var(--ql-danger);
}

.danger-item {
	display: flex;
	justify-content: space-between;
	align-items: flex-start;
	gap: 1rem;
	padding: 0.75rem 0;
}

.danger-info {
	flex: 1;
	min-width: 0;
}

.setting-label {
	display: block;
	font-size: 0.875rem;
	font-weight: 500;
	color: var(--ql-text);
}

.setting-description {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	margin-top: 0.125rem;
	line-height: 1.4;
}

.danger-btn {
	padding: 0.5rem 0.75rem;
	font-size: 0.875rem;
	font-weight: 500;
	color: var(--ql-danger);
	background: none;
	border: 1px solid var(--ql-danger);
	border-radius: 0.375rem;
	cursor: pointer;
	transition: all 0.15s ease;
	flex-shrink: 0;
}

.danger-btn:hover {
	background: rgba(239, 68, 68, 0.1);
}

.danger-btn:disabled {
	opacity: 0.4;
	cursor: not-allowed;
}

.danger-btn-confirm {
	padding: 0.375rem 0.625rem;
	font-size: 0.8rem;
}

.clear-confirm {
	display: flex;
	flex-direction: column;
	gap: 0.5rem;
}

.confirm-prompt {
	font-size: 0.8rem;
	color: var(--ql-text-muted);
	margin: 0;
}

.confirm-row {
	display: flex;
	gap: 0.5rem;
	align-items: center;
}

.confirm-input {
	width: 100px;
	padding: 0.375rem 0.5rem;
	font-size: 0.8rem;
	font-family: monospace;
	border: 1px solid var(--ql-border);
	border-radius: 0.25rem;
	background: var(--ql-bg);
	color: var(--ql-text);
	outline: none;
}

.confirm-input:focus {
	border-color: var(--ql-danger);
	box-shadow: 0 0 0 2px rgba(239, 68, 68, 0.1);
}

.cancel-btn {
	padding: 0.375rem 0.625rem;
	font-size: 0.8rem;
	font-weight: 500;
	color: var(--ql-text-muted);
	background: none;
	border: 1px solid var(--ql-border);
	border-radius: 0.375rem;
	cursor: pointer;
}

.cancel-btn:hover {
	color: var(--ql-text);
	background: var(--ql-subtle);
}
</style>
