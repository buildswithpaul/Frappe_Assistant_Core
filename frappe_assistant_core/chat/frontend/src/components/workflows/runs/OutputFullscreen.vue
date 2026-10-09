<template>
	<Teleport :to="teleportTarget">
		<div
			v-if="open"
			class="fs-overlay"
			role="dialog"
			aria-modal="true"
			:aria-label="title || __('Run output')"
			@click.self="close"
		>
			<div ref="dialogRef" class="fs-panel">
				<header class="fs-header">
					<h2 class="fs-title">{{ title || __("Run output") }}</h2>
					<button type="button" class="fs-close" @click="close">{{ __("Close") }}</button>
				</header>
				<div class="fs-body markdown-body" v-html="html"></div>
			</div>
		</div>
	</Teleport>
</template>

<script setup>
import { computed, ref, watch, nextTick, onBeforeUnmount } from "vue";
import { marked } from "marked";
import DOMPurify from "dompurify";
import { __ } from "@/utils/i18n";
import { useTeleportTarget } from "@/composables/useTeleportTarget";

const FOCUSABLE = "button:not([disabled]), textarea, input, select, [href]";

const props = defineProps({
	open: { type: Boolean, default: false },
	text: { type: String, default: "" },
	title: { type: String, default: "" },
});
const emit = defineEmits(["update:open"]);
const teleportTarget = useTeleportTarget();
const dialogRef = ref(null);
const html = computed(() => DOMPurify.sanitize(marked.parse(props.text || "")));
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
			dialogRef.value?.querySelector(".fs-close")?.focus();
			return;
		}
		document.removeEventListener("keydown", onKeydown);
		if (openerEl?.isConnected) openerEl.focus();
		openerEl = null;
	},
	{ immediate: true }
);

onBeforeUnmount(() => {
	document.removeEventListener("keydown", onKeydown);
	if (props.open && openerEl?.isConnected) openerEl.focus();
});
</script>

<style scoped>
.fs-overlay {
	position: fixed;
	inset: 0;
	z-index: 1150;
	display: flex;
	align-items: center;
	justify-content: center;
	padding: 2rem;
	background: rgba(0, 0, 0, 0.5);
}
.fs-panel {
	display: flex;
	flex-direction: column;
	width: min(70rem, 100%);
	height: min(90vh, 60rem);
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: var(--ql-radius-xl);
	overflow: hidden;
}
.fs-header {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding: 0.75rem 1rem;
	border-bottom: 1px solid var(--ql-border);
}
.fs-title {
	font-size: 0.9375rem;
	font-weight: 600;
	color: var(--ql-text);
}
.fs-close {
	font-size: 0.8125rem;
	color: var(--ql-accent);
	background: none;
	border: none;
	cursor: pointer;
}
.fs-body {
	flex: 1;
	overflow: auto;
	padding: 1.25rem 1.5rem;
	scrollbar-color: var(--ql-border) transparent;
	font-size: 0.875rem;
	line-height: 1.65;
	color: var(--ql-text);
	word-break: break-word;
}
.fs-body :deep(h1) { font-size: 1.375rem; font-weight: 600; margin: 1rem 0 0.5rem; }
.fs-body :deep(h2) { font-size: 1.125rem; font-weight: 600; margin: 1rem 0 0.5rem; }
.fs-body :deep(h3) { font-size: 1rem; font-weight: 600; margin: 0.75rem 0 0.375rem; }
.fs-body :deep(ul) { list-style: disc; padding-left: 1.25rem; }
.fs-body :deep(ol) { list-style: decimal; padding-left: 1.25rem; }
.fs-body :deep(table) { border-collapse: collapse; margin: 0.75rem 0; }
.fs-body :deep(th),
.fs-body :deep(td) { border: 1px solid var(--ql-border); padding: 0.25rem 0.5rem; text-align: left; }
.fs-body :deep(pre) { background: var(--ql-subtle); padding: 0.75rem; border-radius: var(--ql-radius-sm); overflow: auto; }
</style>
