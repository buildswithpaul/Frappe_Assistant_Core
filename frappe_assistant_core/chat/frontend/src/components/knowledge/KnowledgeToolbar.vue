<template>
	<div class="documents-toolbar">
		<div class="toolbar-left">
			<div class="search-input-wrapper">
				<svg class="search-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
					/>
				</svg>
				<input
					ref="searchInput"
					:value="searchQuery"
					type="text"
					class="search-input"
					placeholder="Search documents..."
					@input="$emit('update:searchQuery', $event.target.value)"
				/>
				<kbd v-if="!searchQuery" class="search-kbd">/</kbd>
			</div>
			<div class="filter-chips">
				<button
					v-for="f in visibilityFilters"
					:key="f.value"
					class="filter-chip"
					:class="{ active: activeFilter === f.value }"
					@click="$emit('update:activeFilter', f.value)"
				>
					{{ f.label }}
				</button>
			</div>
		</div>
		<div class="toolbar-right">
			<button
				class="view-toggle"
				:class="{ active: viewMode === 'grid' }"
				@click="$emit('update:viewMode', 'grid')"
				title="Grid view"
				aria-label="Grid view"
			>
				<svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z"
					/>
				</svg>
			</button>
			<button
				class="view-toggle"
				:class="{ active: viewMode === 'list' }"
				@click="$emit('update:viewMode', 'list')"
				title="List view"
				aria-label="List view"
			>
				<svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M4 6h16M4 12h16M4 18h16"
					/>
				</svg>
			</button>
		</div>
	</div>
</template>

<script setup>
import { ref } from "vue";

defineProps({
	searchQuery: { type: String, default: "" },
	activeFilter: { type: String, default: "all" },
	viewMode: { type: String, default: "grid" },
});

defineEmits(["update:searchQuery", "update:activeFilter", "update:viewMode"]);

const searchInput = ref(null);

function focus() {
	searchInput.value?.focus();
}

defineExpose({ focus });

const visibilityFilters = [
	{ value: "all", label: "All" },
	{ value: "mine", label: "My Documents" },
	{ value: "public", label: "Public" },
	{ value: "private", label: "Private" },
	{ value: "shared", label: "Shared" },
];
</script>

<style scoped>
/* Toolbar */
.documents-toolbar {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 0.75rem;
	margin-bottom: 1rem;
	position: relative;
	z-index: 5;
}

.toolbar-left {
	display: flex;
	align-items: center;
	gap: 0.75rem;
	flex: 1;
	min-width: 0;
}

.toolbar-right {
	display: flex;
	align-items: center;
	gap: 0.25rem;
	flex-shrink: 0;
}

/* Search */
.search-input-wrapper {
	position: relative;
	width: 200px;
	flex-shrink: 0;
}

.search-input {
	width: 100%;
	padding: 0.375rem 0.75rem 0.375rem 2rem;
	font-size: 0.8125rem;
	color: var(--ql-text);
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	outline: none;
	transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.search-input:focus {
	border-color: var(--ql-accent);
	box-shadow: 0 0 0 2px rgba(15, 110, 92, 0.1);
}

.search-input::placeholder {
	color: var(--ql-text-muted);
}

.search-icon {
	position: absolute;
	left: 0.625rem;
	top: 50%;
	transform: translateY(-50%);
	width: 0.875rem;
	height: 0.875rem;
	color: var(--ql-text-muted);
	pointer-events: none;
}

.search-kbd {
	position: absolute;
	right: 0.5rem;
	top: 50%;
	transform: translateY(-50%);
	font-size: 0.625rem;
	padding: 0.0625rem 0.3125rem;
	background: var(--ql-subtle);
	border: 1px solid var(--ql-border);
	border-radius: 0.25rem;
	color: var(--ql-text-muted);
	font-family: monospace;
	line-height: 1.4;
}

/* Filter Chips */
.filter-chips {
	display: flex;
	gap: 0.375rem;
	flex-wrap: wrap;
}

.filter-chip {
	padding: 0.25rem 0.75rem;
	font-size: 0.75rem;
	font-weight: 500;
	color: var(--ql-text-muted);
	background: var(--ql-subtle);
	border: 1px solid transparent;
	border-radius: 1rem;
	cursor: pointer;
	transition: all 0.15s ease;
}

.filter-chip:hover {
	color: var(--ql-text);
	border-color: var(--ql-border);
}

.filter-chip.active {
	color: var(--ql-accent);
	background: var(--ql-accent-soft);
	border-color: var(--ql-accent);
}

/* View Toggle */
.view-toggle {
	padding: 0.375rem;
	background: none;
	border: 1px solid transparent;
	border-radius: 0.375rem;
	color: var(--ql-text-muted);
	cursor: pointer;
	transition: all 0.15s ease;
	display: flex;
	align-items: center;
	justify-content: center;
}

.view-toggle svg {
	width: 1rem;
	height: 1rem;
}

.view-toggle:hover {
	color: var(--ql-text);
}

.view-toggle.active {
	color: var(--ql-text);
	background: var(--ql-subtle);
	border-color: var(--ql-border);
}

@media (max-width: 768px) {
	.documents-toolbar {
		flex-wrap: wrap;
	}
	.search-input-wrapper {
		width: 100%;
		order: -1;
	}
	.toolbar-left {
		flex-wrap: wrap;
	}
	.filter-chips {
		order: 1;
	}
}
</style>
