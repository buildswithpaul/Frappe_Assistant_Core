<template>
	<Teleport :to="teleportTarget">
		<div
			v-if="open"
			class="prompt-modal-overlay"
			role="dialog"
			aria-modal="true"
			:aria-label="__('Edit system prompt')"
			@click.self="close"
		>
			<div ref="dialogRef" class="prompt-modal">
				<header class="prompt-modal-header">
					<h2 class="prompt-modal-title">{{ __("System prompt") }}</h2>
					<VariableInserter v-if="!readonly" :global-variables="variables" @insert="insert" />
					<button type="button" class="prompt-modal-close" @click="close">
						{{ __("Done") }}
					</button>
				</header>
				<textarea
					ref="areaRef"
					data-test="expanded-prompt"
					class="prompt-modal-area"
					:aria-label="__('System prompt')"
					:value="modelValue"
					:readonly="readonly"
					@input="$emit('update:modelValue', $event.target.value)"
				></textarea>
			</div>
		</div>
	</Teleport>
</template>

<script setup>
import { ref, watch, nextTick, onBeforeUnmount } from "vue";
import { __ } from "@/utils/i18n";
import { useTeleportTarget } from "@/composables/useTeleportTarget";
import VariableInserter from "./VariableInserter.vue";
import { spliceAtCaret } from "./spliceAtCaret";

const FOCUSABLE = "button:not([disabled]), textarea, input, select, [href]";

const props = defineProps({
	open: { type: Boolean, default: false },
	modelValue: { type: String, default: "" },
	variables: { type: Object, default: () => ({}) },
	readonly: { type: Boolean, default: false },
});
const emit = defineEmits(["update:open", "update:modelValue"]);
const teleportTarget = useTeleportTarget();
const dialogRef = ref(null);
const areaRef = ref(null);
let openerEl = null;

function close() {
	emit("update:open", false);
}

function onKeydown(e) {
	if (e.key === "Escape") {
		// The builder's window-level Escape would also close the node panel under us.
		e.stopPropagation();
		close();
		return;
	}
	if (e.key !== "Tab" || !dialogRef.value) return;
	const focusables = dialogRef.value.querySelectorAll(FOCUSABLE);
	if (!focusables.length) return;
	const first = focusables[0];
	const last = focusables[focusables.length - 1];
	const inside = dialogRef.value.contains(document.activeElement);
	if (!inside || (e.shiftKey && document.activeElement === first)) {
		e.preventDefault();
		last.focus();
	} else if (!e.shiftKey && document.activeElement === last) {
		e.preventDefault();
		first.focus();
	}
}

watch(
	() => props.open,
	async (isOpen) => {
		if (isOpen) {
			openerEl = document.activeElement;
			document.addEventListener("keydown", onKeydown);
			await nextTick();
			areaRef.value?.focus();
			return;
		}
		document.removeEventListener("keydown", onKeydown);
		if (openerEl?.isConnected) openerEl.focus();
		openerEl = null;
	}
);

onBeforeUnmount(() => document.removeEventListener("keydown", onKeydown));

function insert(placeholder) {
	emit("update:modelValue", spliceAtCaret(props.modelValue || "", placeholder, areaRef.value));
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
