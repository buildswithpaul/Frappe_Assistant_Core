<template>
	<button class="model-trigger" :disabled="disabled" :title="name" @click="$emit('toggle')">
		<svg class="model-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
			<path
				stroke-linecap="round"
				stroke-linejoin="round"
				stroke-width="2"
				d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
			/>
		</svg>
		<span class="model-name">{{ name }}</span>
		<span class="model-name-short">{{ shortModelName(name) }}</span>
		<svg
			class="chevron-icon"
			:class="{ open }"
			fill="none"
			stroke="currentColor"
			viewBox="0 0 24 24"
		>
			<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
		</svg>
	</button>
</template>

<script setup>
import { shortModelName } from "@/utils/modelName";

defineProps({
	name: { type: String, default: "" },
	open: { type: Boolean, default: false },
	disabled: { type: Boolean, default: false },
});

defineEmits(["toggle"]);
</script>

<style scoped>
.model-trigger {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	padding: 0.5rem 0.75rem;
	font-size: 0.875rem;
	font-weight: 500;
	color: var(--ql-text);
	background: var(--ql-subtle);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	cursor: pointer;
	transition: all 0.15s ease;
	max-width: 200px;
}

.model-trigger:hover {
	background-color: var(--ql-border);
}

.model-trigger:disabled {
	opacity: 0.6;
	cursor: not-allowed;
}

.model-icon {
	width: 1rem;
	height: 1rem;
	flex-shrink: 0;
	color: var(--ql-text-muted);
}

.model-name,
.model-name-short {
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.model-name-short {
	display: none;
}

.chevron-icon {
	width: 1rem;
	height: 1rem;
	flex-shrink: 0;
	color: var(--ql-text-muted);
	transition: transform 0.2s ease;
}

.chevron-icon.open {
	transform: rotate(180deg);
}

/* A phone shows the short name instead of the icon, so the chosen model stays visible. */
@media (max-width: 640px) {
	.model-trigger {
		max-width: 132px;
		min-width: 0;
		padding-inline: 0.625rem;
	}

	.model-icon,
	.model-name {
		display: none;
	}

	.model-name-short {
		display: inline;
		min-width: 0;
	}
}
</style>
