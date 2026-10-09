<template>
	<Teleport :to="teleportTarget">
		<div
			v-if="open"
			class="prompt-modal-overlay"
			role="dialog"
			aria-modal="true"
			:aria-label="__('Edit system prompt')"
			@click.self="$emit('update:open', false)"
			@keydown.esc="$emit('update:open', false)"
		>
			<div class="prompt-modal">
				<header class="prompt-modal-header">
					<h2 class="prompt-modal-title">{{ __("System prompt") }}</h2>
					<VariableInserter v-if="!readonly" :global-variables="variables" @insert="insert" />
					<button type="button" class="prompt-modal-close" @click="$emit('update:open', false)">
						{{ __("Done") }}
					</button>
				</header>
				<textarea
					ref="areaRef"
					data-test="expanded-prompt"
					class="prompt-modal-area"
					:value="modelValue"
					:readonly="readonly"
					@input="$emit('update:modelValue', $event.target.value)"
				></textarea>
			</div>
		</div>
	</Teleport>
</template>

<script setup>
import { ref, watch, nextTick } from "vue";
import { __ } from "@/utils/i18n";
import { useTeleportTarget } from "@/composables/useTeleportTarget";
import VariableInserter from "./VariableInserter.vue";

const props = defineProps({
	open: { type: Boolean, default: false },
	modelValue: { type: String, default: "" },
	variables: { type: Object, default: () => ({}) },
	readonly: { type: Boolean, default: false },
});
const emit = defineEmits(["update:open", "update:modelValue"]);
const teleportTarget = useTeleportTarget();
const areaRef = ref(null);

watch(
	() => props.open,
	async (isOpen) => {
		if (!isOpen) return;
		await nextTick();
		areaRef.value?.focus();
	}
);

function insert(placeholder) {
	const el = areaRef.value;
	const current = props.modelValue || "";
	const start = el?.selectionStart ?? current.length;
	const end = el?.selectionEnd ?? current.length;
	emit("update:modelValue", current.slice(0, start) + placeholder + current.slice(end));
}
</script>

<style scoped>
.prompt-modal-overlay {
	position: fixed;
	inset: 0;
	z-index: 1100;
	display: flex;
	align-items: center;
	justify-content: center;
	padding: 2rem;
	background: rgba(0, 0, 0, 0.45);
}
.prompt-modal {
	display: flex;
	flex-direction: column;
	width: min(60rem, 100%);
	height: min(80vh, 50rem);
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: var(--ql-radius-xl);
	overflow: hidden;
}
.prompt-modal-header {
	display: flex;
	align-items: center;
	gap: 0.75rem;
	padding: 0.75rem 1rem;
	border-bottom: 1px solid var(--ql-border);
}
.prompt-modal-title {
	flex: 1;
	font-size: 0.9375rem;
	font-weight: 600;
	color: var(--ql-text);
}
.prompt-modal-close {
	padding: 0.375rem 0.875rem;
	font-size: 0.8125rem;
	color: var(--ql-surface);
	background: var(--ql-accent);
	border: none;
	border-radius: var(--ql-radius-sm);
	cursor: pointer;
}
.prompt-modal-area {
	flex: 1;
	padding: 1rem;
	font-size: 0.875rem;
	line-height: 1.6;
	color: var(--ql-text);
	background: var(--ql-bg);
	border: none;
	resize: none;
	outline: none;
}
</style>
