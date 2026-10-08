<template>
	<div>
		<div v-if="isLoading && workflows.length === 0" class="loading-state">
			<div class="loading-spinner"></div>
			<p>{{ __("Loading agents…") }}</p>
		</div>

		<LoadErrorState
			v-else-if="error && workflows.length === 0"
			:message="error"
			@retry="$emit('retry')"
		/>

		<EmptyState
			v-else-if="workflows.length === 0"
			:title="__('No agents yet')"
			:description="__('Create your first AI agent to automate work intelligently.')"
			:cta="isAdmin ? __('Create agent') : ''"
			@cta="$emit('create')"
		/>

		<ListPageShell v-else>
			<template #header>
				<ListHeaderBand :title="__('Agents')" :stat="workflowsStat">
					<template #actions>
						<input
							v-model="searchQuery"
							class="list-search"
							type="search"
							:placeholder="__('Search this page…')"
							:aria-label="__('Search agents on this page')"
						/>
						<div class="filter-tabs">
							<button
								v-for="tab in filterTabs"
								:key="tab.value"
								class="filter-tab"
								:class="{ active: statusFilter === tab.value }"
								@click="handleFilterChange(tab.value)"
							>
								{{ tab.label }}
							</button>
						</div>
						<button v-if="isAdmin" class="ql-primary-action" @click="$emit('create')">
							{{ __("+ New agent") }}
						</button>
					</template>
				</ListHeaderBand>
			</template>

			<WorkflowCard
				v-for="wf in visibleWorkflows"
				:key="wf.name"
				:workflow="wf"
				@click="$emit('open', wf.name)"
				@delete="$emit('delete', wf)"
				@duplicate="$emit('duplicate', wf)"
			/>
			<AddSlotCard
				v-if="isAdmin && !searchQuery"
				:label="__('New agent')"
				@click="$emit('create')"
			/>
		</ListPageShell>

		<ListPager
			v-if="!error || workflows.length > 0"
			:page="currentPage"
			:page-count="pageCount"
			:disabled="isLoading"
			@change="goToPage"
		/>
	</div>
</template>

<script setup>
import { ref, computed } from "vue";
import { __ } from "@/utils/i18n";
import WorkflowCard from "@/components/workflows/WorkflowCard.vue";
import ListPageShell from "@/components/common/list/ListPageShell.vue";
import ListHeaderBand from "@/components/common/list/ListHeaderBand.vue";
import AddSlotCard from "@/components/common/list/AddSlotCard.vue";
import EmptyState from "@/components/common/list/EmptyState.vue";
import ListPager from "@/components/common/list/ListPager.vue";
import LoadErrorState from "@/components/common/list/LoadErrorState.vue";

const props = defineProps({
	workflows: { type: Array, required: true },
	isLoading: { type: Boolean, default: false },
	error: { type: String, default: null },
	total: { type: Number, default: 0 },
	statusFilter: { type: String, default: null },
	currentPage: { type: Number, default: 0 },
	pageSize: { type: Number, default: 20 },
	isAdmin: { type: Boolean, default: false },
});

const emit = defineEmits(["open", "delete", "duplicate", "create", "filter", "page", "retry"]);

const searchQuery = ref("");

const filterTabs = [
	{ label: __("All"), value: null },
	{ label: __("Draft"), value: "Draft" },
	{ label: __("Active"), value: "Active" },
	{ label: __("Paused"), value: "Paused" },
];

// Search filters the loaded page. The list endpoint has no server-side search,
// so the label says exactly that rather than implying a global result.
const visibleWorkflows = computed(() => {
	const q = searchQuery.value.trim().toLowerCase();
	if (!q) return props.workflows;
	return props.workflows.filter(
		(wf) =>
			(wf.workflow_name || "").toLowerCase().includes(q) ||
			(wf.description || "").toLowerCase().includes(q),
	);
});

const pageCount = computed(() => Math.max(1, Math.ceil((props.total || 0) / props.pageSize)));

const workflowsStat = computed(() => {
	const shown = visibleWorkflows.value.length;
	if (searchQuery.value.trim()) {
		return __("{0} of {1} on this page match", [shown, props.workflows.length]);
	}
	const label = shown === 1 ? "{0} agent · {1} total" : "{0} agents · {1} total";
	return __(label, [shown, props.total ?? shown]);
});

function handleFilterChange(status) {
	searchQuery.value = "";
	emit("filter", status);
}

function goToPage(page) {
	if (page < 0 || page >= pageCount.value) return;
	searchQuery.value = "";
	emit("page", page);
}
</script>

<style scoped>
.list-search {
	padding: 0.375rem 0.625rem;
	font-size: 0.8125rem;
	color: var(--ql-text);
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 9999px;
	outline: none;
	min-width: 12rem;
}

.list-search:focus {
	border-color: var(--ql-accent);
}

.filter-tabs {
	display: flex;
	gap: 0.375rem;
	flex-wrap: wrap;
}

.filter-tab {
	padding: 0.375rem 0.875rem;
	font-size: 0.8125rem;
	font-weight: 500;
	color: var(--ql-text-muted);
	background: transparent;
	border: 1px solid var(--ql-border);
	border-radius: 9999px;
	cursor: pointer;
	transition: all 0.15s ease;
}

.filter-tab:hover {
	color: var(--ql-text);
	border-color: var(--ql-text);
}

.filter-tab.active {
	color: #fff;
	background: var(--ql-accent);
	border-color: var(--ql-accent);
}

.loading-state {
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	padding: 4rem 2rem;
	text-align: center;
	color: var(--ql-text-muted);
}

.loading-spinner {
	width: 2rem;
	height: 2rem;
	border: 2px solid var(--ql-border);
	border-top-color: var(--ql-accent);
	border-radius: 50%;
	animation: spin 0.8s linear infinite;
	margin-bottom: 1rem;
}

@keyframes spin {
	to {
		transform: rotate(360deg);
	}
}

.ql-primary-action {
	font-size: 13px;
	font-weight: 600;
	color: #fff;
	background: var(--ql-accent);
	border: none;
	border-radius: 8px;
	padding: 6px 12px;
	cursor: pointer;
	transition: background 0.15s ease;
}

.ql-primary-action:hover {
	background: var(--ql-accent-hover);
}
</style>
