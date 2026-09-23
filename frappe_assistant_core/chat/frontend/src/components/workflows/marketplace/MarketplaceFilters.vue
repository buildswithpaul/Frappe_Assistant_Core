<template>
	<div class="marketplace-header">
		<h2 class="marketplace-title">Template Marketplace</h2>

		<div class="filters-row">
			<div class="search-input-wrap">
				<svg
					class="search-icon"
					width="14"
					height="14"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
				>
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
					/>
				</svg>
				<input
					:value="searchQuery"
					class="search-input"
					placeholder="Search templates..."
					@input="$emit('update:searchQuery', $event.target.value)"
				/>
			</div>
			<select
				:value="sortBy"
				class="sort-select"
				@change="$emit('update:sortBy', $event.target.value)"
			>
				<option value="">Popular</option>
				<option value="rating">Top Rated</option>
				<option value="recent">Recent</option>
				<option value="featured">Featured</option>
			</select>
		</div>

		<div class="category-pills">
			<button
				v-for="cat in categories"
				:key="cat"
				class="pill"
				:class="{ active: categoryFilter === cat }"
				@click="$emit('update:categoryFilter', cat)"
			>
				{{ cat }}
			</button>
		</div>
	</div>
</template>

<script setup>
defineProps({
	searchQuery: { type: String, default: "" },
	categoryFilter: { type: String, default: null },
	sortBy: { type: String, default: "" },
	categories: { type: Array, required: true },
});

defineEmits(["update:searchQuery", "update:categoryFilter", "update:sortBy"]);
</script>

<style scoped>
.marketplace-header {
	padding: 1.25rem 1.5rem 0;
	flex-shrink: 0;
}

.marketplace-title {
	font-size: 1.125rem;
	font-weight: 600;
	color: var(--ql-text);
	margin: 0 0 1rem;
}

.filters-row {
	display: flex;
	gap: 0.5rem;
	margin-bottom: 0.75rem;
	align-items: stretch;
}

.search-input-wrap {
	position: relative;
	flex: 1;
}

.search-icon {
	position: absolute;
	left: 0.625rem;
	top: 50%;
	transform: translateY(-50%);
	color: var(--ql-text-muted);
	pointer-events: none;
}

.search-input {
	width: 100%;
	padding: 0.5rem 0.75rem 0.5rem 2rem;
	font-size: 0.8125rem;
	color: var(--ql-text);
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	outline: none;
	box-sizing: border-box;
	transition: border-color 0.15s ease;
}

.search-input:focus {
	border-color: var(--ql-accent);
}

.sort-select {
	padding: 0.5rem 0.75rem;
	font-size: 0.8125rem;
	color: var(--ql-text);
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	outline: none;
	cursor: pointer;
	transition: border-color 0.15s ease;
	appearance: none;
	-webkit-appearance: none;
	background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6'%3E%3Cpath d='M1 1l4 4 4-4' stroke='%239ca3af' fill='none' stroke-width='1.5' stroke-linecap='round'/%3E%3C/svg%3E");
	background-repeat: no-repeat;
	background-position: right 0.625rem center;
	padding-right: 2rem;
	min-width: 7rem;
}

.sort-select:focus {
	border-color: var(--ql-accent);
}

.category-pills {
	display: flex;
	flex-wrap: wrap;
	gap: 0.375rem;
	margin-bottom: 1rem;
	padding-bottom: 1rem;
	border-bottom: 1px solid var(--ql-border);
}

.pill {
	padding: 0.25rem 0.625rem;
	font-size: 0.6875rem;
	font-weight: 500;
	color: var(--ql-text-muted);
	background: transparent;
	border: 1px solid var(--ql-border);
	border-radius: 9999px;
	cursor: pointer;
	transition: all 0.15s ease;
}

.pill:hover {
	color: var(--ql-text);
	border-color: var(--ql-text);
}

.pill.active {
	color: white;
	background: var(--ql-accent);
	border-color: var(--ql-accent);
}

@media (max-width: 640px) {
	.filters-row {
		flex-direction: column;
	}

	.sort-select {
		min-width: unset;
	}
}
</style>
