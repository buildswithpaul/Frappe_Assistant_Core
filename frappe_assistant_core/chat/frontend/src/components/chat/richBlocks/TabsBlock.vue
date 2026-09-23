<template>
	<div class="tabs-block">
		<div class="tabs-bar" role="tablist">
			<button
				v-for="(tab, idx) in tabs"
				:key="idx"
				class="tab-btn"
				:class="{ 'tab-active': activeTab === idx }"
				role="tab"
				:aria-selected="activeTab === idx"
				@click="activeTab = idx"
			>
				{{ tab.title }}
			</button>
		</div>
		<div class="tab-panel" role="tabpanel" v-html="tabs[activeTab]?.html || ''"></div>
	</div>
</template>

<script setup>
import { ref, computed } from "vue";
import { marked } from "marked";
import DOMPurify from "dompurify";

const props = defineProps({
	defaultTab: { type: String, default: "" },
	body: { type: String, default: "" },
});

const tabs = computed(() => {
	if (!props.body) return [];
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

// Find default tab by title match, otherwise first tab
const defaultIndex = computed(() => {
	if (!props.defaultTab) return 0;
	const idx = tabs.value.findIndex(
		(t) => t.title.toLowerCase() === props.defaultTab.toLowerCase()
	);
	return idx >= 0 ? idx : 0;
});

const activeTab = ref(defaultIndex.value);
</script>

<style scoped>
.tabs-block {
	margin: 0.75rem 0;
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	overflow: hidden;
}

.tabs-bar {
	display: flex;
	background: var(--ql-surface);
	border-bottom: 1px solid var(--ql-border);
	overflow-x: auto;
}

.tab-btn {
	padding: 0.625rem 1rem;
	font-size: 0.8125rem;
	font-weight: 500;
	color: var(--ql-text-muted);
	background: none;
	border: none;
	border-bottom: 2px solid transparent;
	cursor: pointer;
	white-space: nowrap;
	transition: color 0.15s, border-color 0.15s;
}

.tab-btn:hover {
	color: var(--ql-text);
}

.tab-active {
	color: var(--ql-accent);
	border-bottom-color: var(--ql-accent);
	font-weight: 600;
}

.tab-panel {
	padding: 1rem;
	font-size: 0.8125rem;
	line-height: 1.6;
	color: var(--ql-text);
}

.tab-panel :deep(p) {
	margin: 0 0 0.5rem;
}
.tab-panel :deep(p:last-child) {
	margin-bottom: 0;
}
.tab-panel :deep(strong) {
	font-weight: 600;
}
.tab-panel :deep(ul),
.tab-panel :deep(ol) {
	margin: 0.375rem 0;
	padding-left: 1.25rem;
}

.tab-panel :deep(ul) {
	list-style: disc;
}

.tab-panel :deep(ol) {
	list-style: decimal;
}
.tab-panel :deep(li) {
	margin-bottom: 0.25rem;
}
.tab-panel :deep(code) {
	padding: 0.0625rem 0.25rem;
	background: var(--ql-subtle);
	border-radius: 0.25rem;
	font-size: 0.8em;
}
</style>
