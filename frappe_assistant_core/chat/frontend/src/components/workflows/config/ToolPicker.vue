<template>
	<div ref="pickerRef" class="tool-picker">
		<div class="picker-search-wrap">
			<svg
				class="picker-search-icon"
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
				ref="searchInputRef"
				v-model="toolSearch"
				class="picker-search-input"
				:placeholder="__('Search tools...')"
			/>
		</div>
		<div class="picker-list">
			<div v-if="isLoading" class="picker-status">
				<div class="picker-spinner"></div>
				{{ __("Loading tools...") }}
			</div>
			<div v-else-if="filteredPickerTools.length === 0" class="picker-status">
				{{ toolSearch.trim() ? __("No tools match that search") : emptyMessage || __("No tools found") }}
			</div>
			<template v-else>
				<div v-for="group in filteredPickerTools" :key="group.server" class="picker-group">
					<div class="picker-server-label">{{ group.server }}</div>
					<button
						v-for="tool in group.tools"
						:key="tool.name"
						class="picker-tool-btn"
						:class="{ disabled: isSelected(tool) }"
						:disabled="isSelected(tool)"
						@click="handleSelect(tool)"
					>
						<span class="picker-tool-name">{{ tool.original_name || tool.name }}</span>
						<span v-if="tool.description" class="picker-tool-desc">{{
							tool.description
						}}</span>
						<svg
							v-if="isSelected(tool)"
							class="picker-check"
							width="14"
							height="14"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
						>
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								stroke-width="2.5"
								d="M5 13l4 4L19 7"
							/>
						</svg>
					</button>
				</div>
			</template>
		</div>
	</div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from "vue";
import { __ } from "@/utils/i18n";
import { toolKey } from "./toolDirectives";

const props = defineProps({
	allTools: { type: Array, default: () => [] },
	/** directiveKey of every configured tool — the same name on another site is still pickable. */
	selectedToolKeys: { type: Set, required: true },
	isLoading: { type: Boolean, default: false },
	modelValue: { type: Boolean, default: false },
	/** What "no tools" actually means here — a failure is not an empty toolbox. */
	emptyMessage: { type: String, default: "" },
});

const emit = defineEmits(["update:modelValue", "select"]);

const toolSearch = ref("");
const pickerRef = ref(null);
const searchInputRef = ref(null);

const toolsByServer = computed(() => {
	const groups = {};
	for (const tool of props.allTools) {
		const server = tool.server || "unknown";
		if (!groups[server]) groups[server] = [];
		groups[server].push(tool);
	}
	return Object.entries(groups)
		.sort(([a], [b]) => a.localeCompare(b))
		.map(([server, tools]) => ({
			server,
			tools: tools.sort((a, b) =>
				(a.original_name || a.name).localeCompare(b.original_name || b.name)
			),
		}));
});

const filteredPickerTools = computed(() => {
	const query = toolSearch.value.toLowerCase().trim();
	return toolsByServer.value
		.map((group) => ({
			server: group.server,
			tools: group.tools.filter((t) => {
				if (!query) return true;
				const name = (t.original_name || t.name || "").toLowerCase();
				const desc = (t.description || "").toLowerCase();
				return name.includes(query) || desc.includes(query);
			}),
		}))
		.filter((g) => g.tools.length > 0);
});

// Directives store the bare tool name (what the engine resolves against),
// so membership is tested on that, not on the server-prefixed name.
function isSelected(tool) {
	return props.selectedToolKeys.has(toolKey(tool));
}

function handleSelect(tool) {
	emit("select", tool);
}

function close() {
	toolSearch.value = "";
	emit("update:modelValue", false);
}

function handleClickOutside(e) {
	if (pickerRef.value && !pickerRef.value.contains(e.target)) {
		close();
	}
}

// Focus search input when picker becomes visible
watch(
	() => props.modelValue,
	(visible) => {
		if (visible) {
			toolSearch.value = "";
			nextTick(() => {
				searchInputRef.value?.focus();
			});
		}
	}
);

onMounted(() => document.addEventListener("mousedown", handleClickOutside));
onUnmounted(() => document.removeEventListener("mousedown", handleClickOutside));
</script>

<style scoped>
.tool-picker {
	border: 1px solid var(--ql-border);
	border-radius: 0.375rem;
	background: var(--ql-surface);
	box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
	margin-bottom: 0.5rem;
	overflow: hidden;
}

.picker-search-wrap {
	display: flex;
	align-items: center;
	gap: 0.375rem;
	padding: 0.5rem;
	border-bottom: 1px solid var(--ql-border);
}

.picker-search-icon {
	flex-shrink: 0;
	color: var(--ql-text-muted);
}

.picker-search-input {
	flex: 1;
	font-size: 0.8125rem;
	color: var(--ql-text);
	background: transparent;
	border: none;
	outline: none;
	min-width: 0;
}

.picker-list {
	max-height: 240px;
	overflow-y: auto;
}

.picker-status {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	padding: 0.75rem;
	font-size: 0.75rem;
	color: var(--ql-text-muted);
}

.picker-spinner {
	width: 14px;
	height: 14px;
	border: 2px solid var(--ql-border);
	border-top-color: var(--ql-accent);
	border-radius: 50%;
	animation: spin 0.6s linear infinite;
	flex-shrink: 0;
}

@keyframes spin {
	to {
		transform: rotate(360deg);
	}
}

.picker-group + .picker-group {
	border-top: 1px solid var(--ql-border);
}

.picker-server-label {
	font-size: 0.625rem;
	font-weight: 600;
	color: var(--ql-text-muted);
	text-transform: uppercase;
	letter-spacing: 0.04em;
	padding: 0.375rem 0.625rem 0.125rem;
}

.picker-tool-btn {
	position: relative;
	display: flex;
	flex-direction: column;
	align-items: flex-start;
	gap: 0.125rem;
	width: 100%;
	padding: 0.375rem 0.625rem;
	font-size: 0.8125rem;
	color: var(--ql-text);
	background: transparent;
	border: none;
	text-align: left;
	cursor: pointer;
	transition: background 0.1s ease;
}

.picker-tool-btn:hover:not(.disabled) {
	background: var(--ql-subtle);
}

.picker-tool-btn.disabled {
	color: var(--ql-text-muted);
	cursor: default;
	opacity: 0.6;
}

.picker-tool-name {
	max-width: 100%;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.picker-tool-desc {
	display: -webkit-box;
	-webkit-line-clamp: 2;
	-webkit-box-orient: vertical;
	overflow: hidden;
	font-size: 0.6875rem;
	color: var(--ql-text-muted);
	text-align: left;
}

.picker-check {
	position: absolute;
	top: 0.5rem;
	right: 0.625rem;
	flex-shrink: 0;
	color: var(--ql-success);
}
</style>
