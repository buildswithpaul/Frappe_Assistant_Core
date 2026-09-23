<template>
	<div class="accordion-block">
		<div
			v-for="(section, idx) in sections"
			:key="idx"
			class="accordion-section"
			:class="{ 'accordion-open': openSections[idx] }"
		>
			<button class="accordion-header" @click="toggle(idx)">
				<svg
					class="accordion-chevron"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
				>
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M9 5l7 7-7 7"
					/>
				</svg>
				<span class="accordion-title">{{ section.title }}</span>
			</button>
			<div v-if="openSections[idx]" class="accordion-body" v-html="section.html"></div>
		</div>
	</div>
</template>

<script setup>
import { reactive, computed } from "vue";
import { marked } from "marked";
import DOMPurify from "dompurify";

const props = defineProps({
	body: { type: String, default: "" },
});

const sections = computed(() => {
	if (!props.body) return [];
	// Split on ## headers
	const parts = props.body.split(/^## /m).filter(Boolean);
	return parts.map((part) => {
		const newlineIdx = part.indexOf("\n");
		if (newlineIdx === -1) {
			return { title: part.trim(), html: "" };
		}
		const title = part.slice(0, newlineIdx).trim();
		const content = part.slice(newlineIdx + 1).trim();
		return {
			title,
			html: content ? DOMPurify.sanitize(marked.parse(content)) : "",
		};
	});
});

// First section open by default
const openSections = reactive({});
sections.value.forEach((_, idx) => {
	openSections[idx] = idx === 0;
});

function toggle(idx) {
	openSections[idx] = !openSections[idx];
}
</script>

<style scoped>
.accordion-block {
	margin: 0.75rem 0;
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	overflow: hidden;
}

.accordion-section + .accordion-section {
	border-top: 1px solid var(--ql-border);
}

.accordion-header {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	width: 100%;
	padding: 0.75rem 1rem;
	background: var(--ql-surface);
	border: none;
	cursor: pointer;
	text-align: left;
	font-size: 0.875rem;
	font-weight: 600;
	color: var(--ql-text);
	transition: background 0.15s;
}

.accordion-header:hover {
	background: var(--ql-subtle);
}

.accordion-chevron {
	width: 1rem;
	height: 1rem;
	flex-shrink: 0;
	color: var(--ql-text-muted);
	transition: transform 0.2s ease;
}

.accordion-open .accordion-chevron {
	transform: rotate(90deg);
}

.accordion-title {
	flex: 1;
}

.accordion-body {
	padding: 0 1rem 0.75rem;
	font-size: 0.8125rem;
	line-height: 1.6;
	color: var(--ql-text);
}

.accordion-body :deep(p) {
	margin: 0 0 0.5rem;
}
.accordion-body :deep(p:last-child) {
	margin-bottom: 0;
}
.accordion-body :deep(strong) {
	font-weight: 600;
}
.accordion-body :deep(ul),
.accordion-body :deep(ol) {
	margin: 0.375rem 0;
	padding-left: 1.25rem;
}

.accordion-body :deep(ul) {
	list-style: disc;
}

.accordion-body :deep(ol) {
	list-style: decimal;
}
.accordion-body :deep(li) {
	margin-bottom: 0.25rem;
}
.accordion-body :deep(code) {
	padding: 0.0625rem 0.25rem;
	background: var(--ql-subtle);
	border-radius: 0.25rem;
	font-size: 0.8em;
}
</style>
