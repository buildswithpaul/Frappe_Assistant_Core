<template>
	<div class="panel-header">
		<div class="header-info">
			<div class="node-type-indicator" :style="color ? { background: color } : undefined"></div>
			<input
				v-model="editLabel"
				class="label-input"
				:aria-label="__('Node name')"
				:readonly="readonly"
				@blur="commitLabel"
				@keydown.enter="$event.target.blur()"
			/>
		</div>
		<div class="header-actions">
			<button
				v-if="!readonly"
				type="button"
				class="header-btn danger"
				:title="__('Delete node')"
				:aria-label="__('Delete node')"
				@click="$emit('delete')"
			>
				<svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
					/>
				</svg>
			</button>
			<button
				type="button"
				class="header-btn"
				:title="__('Close')"
				:aria-label="__('Close panel')"
				@click="$emit('close')"
			>
				<svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M6 18L18 6M6 6l12 12"
					/>
				</svg>
			</button>
		</div>
	</div>
</template>

<script setup>
import { ref, watch } from "vue";
import { __ } from "@/utils/i18n";

const props = defineProps({
	label: { type: String, default: "" },
	color: { type: String, default: "" },
	readonly: { type: Boolean, default: false },
});
const emit = defineEmits(["rename", "delete", "close"]);

const editLabel = ref(props.label);
watch(
	() => props.label,
	(value) => {
		editLabel.value = value;
	}
);

function commitLabel() {
	if (props.readonly) return;
	const trimmed = editLabel.value.trim();
	if (trimmed && trimmed !== props.label) emit("rename", trimmed);
}
</script>

<style scoped>
.panel-header {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding: 0.75rem 1rem;
	border-bottom: 1px solid var(--ql-border);
	gap: 0.5rem;
}

.header-info {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	min-width: 0;
	flex: 1;
}

.node-type-indicator {
	background: var(--ql-text-muted);
	width: 10px;
	height: 10px;
	border-radius: 50%;
	flex-shrink: 0;
}

.label-input {
	flex: 1;
	font-size: 0.875rem;
	font-weight: 600;
	color: var(--ql-text);
	background: transparent;
	border: none;
	border-bottom: 1px solid transparent;
	outline: none;
	padding: 0.125rem 0;
	min-width: 0;
	transition: border-color 0.15s ease;
}

.label-input:focus {
	border-bottom-color: var(--ql-accent);
}

.header-actions {
	display: flex;
	gap: 0.25rem;
	flex-shrink: 0;
}

.header-btn {
	display: flex;
	align-items: center;
	justify-content: center;
	width: 28px;
	height: 28px;
	background: transparent;
	border: none;
	color: var(--ql-text-muted);
	border-radius: 0.25rem;
	cursor: pointer;
	transition: all 0.15s ease;
}

.header-btn:hover {
	background: var(--ql-subtle);
	color: var(--ql-text);
}

.header-btn.danger:hover {
	background: color-mix(in srgb, var(--ql-danger) 10%, transparent);
	color: var(--ql-danger);
}
</style>
