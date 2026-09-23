<script setup>
import { computed, ref, watch, onMounted, onBeforeUnmount } from "vue";
import { WHISPER_LANGUAGES, findLanguage } from "@/constants/whisperLanguages";

const props = defineProps({
	modelValue: { type: String, default: "" },
	placeholder: { type: String, default: "Select a language…" },
});

const emit = defineEmits(["update:modelValue"]);

const open = ref(false);
const query = ref("");
const root = ref(null);

const selected = computed(() => findLanguage(props.modelValue));

const displayLabel = computed(() => {
	if (!selected.value) return "";
	return `${selected.value.native} — ${selected.value.name}`;
});

const filtered = computed(() => {
	const q = query.value.trim().toLowerCase();
	if (!q) return WHISPER_LANGUAGES;
	return WHISPER_LANGUAGES.filter(
		(l) =>
			l.code.includes(q) ||
			l.name.toLowerCase().includes(q) ||
			l.native.toLowerCase().includes(q)
	);
});

function pick(lang) {
	emit("update:modelValue", lang.code);
	open.value = false;
	query.value = "";
}

function clear() {
	emit("update:modelValue", "");
}

function toggle() {
	open.value = !open.value;
	if (open.value) {
		// Defer focus to next tick so the input is rendered.
		setTimeout(() => {
			const input = root.value?.querySelector(".lang-search");
			input?.focus();
		}, 0);
	}
}

function onDocClick(e) {
	if (root.value && !root.value.contains(e.target)) open.value = false;
}

function onKey(e) {
	if (e.key === "Escape") open.value = false;
}

watch(() => props.modelValue, () => {
	query.value = "";
});

onMounted(() => {
	document.addEventListener("click", onDocClick);
	document.addEventListener("keydown", onKey);
});
onBeforeUnmount(() => {
	document.removeEventListener("click", onDocClick);
	document.removeEventListener("keydown", onKey);
});
</script>

<template>
	<div ref="root" class="lang-select" :class="{ 'is-open': open }">
		<button type="button" class="lang-trigger" @click.stop="toggle">
			<span v-if="selected" class="lang-label">{{ displayLabel }}</span>
			<span v-else class="lang-placeholder">{{ placeholder }}</span>
			<svg class="lang-chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
				<polyline points="6 9 12 15 18 9"></polyline>
			</svg>
		</button>

		<div v-if="open" class="lang-panel" @click.stop>
			<input
				v-model="query"
				type="text"
				class="lang-search"
				placeholder="Search language or code…"
				autocomplete="off"
				spellcheck="false"
			/>
			<div class="lang-list" role="listbox">
				<button
					v-if="modelValue"
					type="button"
					class="lang-clear"
					@click="clear"
				>
					Clear selection (auto-detect)
				</button>
				<button
					v-for="lang in filtered"
					:key="lang.code"
					type="button"
					class="lang-option"
					:class="{ 'is-selected': selected && selected.code === lang.code }"
					role="option"
					@click="pick(lang)"
				>
					<span class="lang-native">{{ lang.native }}</span>
					<span class="lang-meta">{{ lang.name }} · {{ lang.code }}</span>
				</button>
				<div v-if="!filtered.length" class="lang-empty">
					No language matches “{{ query }}”
				</div>
			</div>
		</div>
	</div>
</template>

<style scoped>
.lang-select {
	position: relative;
	width: 100%;
}

.lang-trigger {
	display: flex;
	align-items: center;
	justify-content: space-between;
	width: 100%;
	padding: 0.5rem 0.75rem;
	background: var(--ql-bg, #fff);
	border: 1px solid var(--ql-border, #e2e8f0);
	border-radius: 6px;
	font-size: 0.875rem;
	color: var(--ql-text, #1e293b);
	cursor: pointer;
	transition: border-color 0.15s ease;
	text-align: left;
}

.lang-trigger:hover { border-color: var(--ql-accent, var(--ql-accent)); }
.lang-select.is-open .lang-trigger { border-color: var(--ql-accent, var(--ql-accent)); }

.lang-label { flex: 1; truncate: true; }
.lang-placeholder {
	flex: 1;
	color: var(--ql-text-muted, #94a3b8);
}
.lang-chevron {
	flex-shrink: 0;
	margin-left: 0.5rem;
	color: var(--ql-text-muted, #94a3b8);
	transition: transform 0.15s ease;
}
.lang-select.is-open .lang-chevron { transform: rotate(180deg); }

.lang-panel {
	position: absolute;
	top: calc(100% + 4px);
	left: 0;
	right: 0;
	z-index: 50;
	background: var(--ql-surface, #fff);
	border: 1px solid var(--ql-border, #e2e8f0);
	border-radius: 6px;
	box-shadow: 0 8px 24px rgba(15, 23, 42, 0.12);
	overflow: hidden;
}

.lang-search {
	width: 100%;
	padding: 0.625rem 0.75rem;
	border: none;
	border-bottom: 1px solid var(--ql-border, #e2e8f0);
	font-size: 0.875rem;
	outline: none;
	background: transparent;
	color: var(--ql-text, #1e293b);
}

.lang-list {
	max-height: 280px;
	overflow-y: auto;
	padding: 0.25rem 0;
}

.lang-option,
.lang-clear {
	display: flex;
	flex-direction: column;
	gap: 0.125rem;
	width: 100%;
	padding: 0.5rem 0.75rem;
	background: transparent;
	border: none;
	text-align: left;
	cursor: pointer;
	transition: background 0.1s ease;
}

.lang-option:hover,
.lang-clear:hover {
	background: var(--ql-subtle, #f1f5f9);
}

.lang-option.is-selected {
	background: var(--ql-accent-soft);
}

.lang-native {
	font-size: 0.875rem;
	color: var(--ql-text, #1e293b);
}

.lang-meta {
	font-size: 0.75rem;
	color: var(--ql-text-muted, #94a3b8);
}

.lang-clear {
	border-bottom: 1px solid var(--ql-border, #e2e8f0);
	font-size: 0.8125rem;
	color: var(--ql-text-muted, #64748b);
}

.lang-empty {
	padding: 1rem 0.75rem;
	text-align: center;
	font-size: 0.8125rem;
	color: var(--ql-text-muted, #94a3b8);
}
</style>
