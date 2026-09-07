<template>
	<div v-if="open" class="slash-menu" role="listbox" aria-label="Templates">
		<div v-if="pinnedMatches.length > 0" class="menu-section">
			<div class="section-label">Pinned</div>
			<button
				v-for="(t, idx) in pinnedMatches"
				:key="`p-${t.name}`"
				:ref="(el) => setRowRef(el, idx)"
				class="menu-row"
				:class="{ 'menu-row-active': activeIndex === idx }"
				role="option"
				:aria-selected="activeIndex === idx"
				@mouseenter="activeIndex = idx"
				@mousedown.prevent="pick(t)"
			>
				<span class="row-icon">{{ iconFor(t) }}</span>
				<span class="row-body">
					<span class="row-title">{{ t.title || t.name }}</span>
					<span v-if="t.description" class="row-desc">{{ t.description }}</span>
				</span>
				<span class="row-enter" aria-hidden="true">⏎</span>
			</button>
		</div>

		<div v-for="group in packGroups" :key="`pg-${group.key}`" class="menu-section">
			<div class="section-label">
				<span class="section-icon">{{ group.icon }}</span>
				{{ group.label }}
			</div>
			<button
				v-for="(t, i) in group.items"
				:key="`pk-${t.name}`"
				:ref="(el) => setRowRef(el, group.startIndex + i)"
				class="menu-row"
				:class="{ 'menu-row-active': activeIndex === group.startIndex + i }"
				role="option"
				:aria-selected="activeIndex === group.startIndex + i"
				@mouseenter="activeIndex = group.startIndex + i"
				@mousedown.prevent="pick(t)"
			>
				<span class="row-icon">{{ iconFor(t) }}</span>
				<span class="row-body">
					<span class="row-title">{{ t.title || t.name }}</span>
					<span v-if="t.description" class="row-desc">{{ t.description }}</span>
				</span>
				<span class="row-enter" aria-hidden="true">⏎</span>
			</button>
		</div>

		<div v-if="otherMatches.length > 0" class="menu-section">
			<div class="section-label">Other</div>
			<button
				v-for="(t, i) in otherMatches"
				:key="`o-${t.name}`"
				:ref="(el) => setRowRef(el, otherStartIndex + i)"
				class="menu-row"
				:class="{ 'menu-row-active': activeIndex === otherStartIndex + i }"
				role="option"
				:aria-selected="activeIndex === otherStartIndex + i"
				@mouseenter="activeIndex = otherStartIndex + i"
				@mousedown.prevent="pick(t)"
			>
				<span class="row-icon">{{ iconFor(t) }}</span>
				<span class="row-body">
					<span class="row-title">{{ t.title || t.name }}</span>
					<span v-if="t.description" class="row-desc">{{ t.description }}</span>
				</span>
				<span class="row-enter" aria-hidden="true">⏎</span>
			</button>
		</div>

		<div v-if="totalCount === 0" class="menu-empty">
			No templates match <span class="empty-query">{{ query || "…" }}</span>
		</div>

		<div class="menu-footer">
			<span><kbd>↑</kbd><kbd>↓</kbd> navigate</span>
			<span><kbd>⏎</kbd> select</span>
			<span><kbd>esc</kbd> close</span>
			<button
				v-if="showBrowseAll"
				class="browse-all-btn"
				@mousedown.prevent="$emit('browse-all')"
			>
				Browse all →
			</button>
		</div>
	</div>
</template>

<script setup>
import { computed, ref, watch, nextTick } from "vue";
import { useTemplateStore } from "@/stores/templateStore";
import { storeToRefs } from "pinia";

const props = defineProps({
	open: { type: Boolean, default: false },
	query: { type: String, default: "" },
	showBrowseAll: { type: Boolean, default: true },
});

const emit = defineEmits(["pick", "close", "browse-all"]);

const templateStore = useTemplateStore();
const { templates, pinnedNames } = storeToRefs(templateStore);

const activeIndex = ref(0);
const rowRefs = ref([]);

function setRowRef(el, idx) {
	if (el) rowRefs.value[idx] = el;
}

const CATEGORY_ICONS = {
	"data-quality": "🔍",
	documentation: "📄",
	"sales-crm": "📊",
	"hr-payroll": "👥",
	purchasing: "📦",
	manufacturing: "🏭",
};

const PACK_META = {
	manufacturing: { label: "Manufacturing Pack", icon: "🏭" },
	"retail-distribution": { label: "Retail & Distribution Pack", icon: "🛒" },
	services: { label: "Services Pack", icon: "💼" },
	healthcare: { label: "Healthcare Pack", icon: "🩺" },
	construction: { label: "Construction Pack", icon: "🏗️" },
	education: { label: "Education Pack", icon: "🎓" },
};

function iconFor(t) {
	if (t?.pack && PACK_META[t.pack]) return PACK_META[t.pack].icon;
	return CATEGORY_ICONS[t?.category] || "📋";
}

function matchesQuery(t, q) {
	if (!q) return true;
	const needle = q.toLowerCase();
	return (
		(t.title || "").toLowerCase().includes(needle) ||
		(t.name || "").toLowerCase().includes(needle) ||
		(t.description || "").toLowerCase().includes(needle)
	);
}

const pinnedMatches = computed(() => {
	const pinnedSet = new Set(pinnedNames.value);
	return templates.value
		.filter((t) => pinnedSet.has(t.name) && matchesQuery(t, props.query))
		.slice(0, 5);
});

// Templates that aren't pinned and match the query, partitioned into
// "pack groups" (one section per active pack the user has) and "other".
const filteredNonPinned = computed(() => {
	const pinnedSet = new Set(pinnedNames.value);
	return templates.value.filter((t) => !pinnedSet.has(t.name) && matchesQuery(t, props.query));
});

const packGroups = computed(() => {
	const buckets = new Map();
	for (const t of filteredNonPinned.value) {
		if (!t.pack) continue;
		if (!buckets.has(t.pack)) buckets.set(t.pack, []);
		buckets.get(t.pack).push(t);
	}
	const groups = [];
	let runningIndex = pinnedMatches.value.length;
	// Sort pack groups by display order from PACK_META
	const orderedKeys = [...buckets.keys()].sort((a, b) => {
		const ai = Object.keys(PACK_META).indexOf(a);
		const bi = Object.keys(PACK_META).indexOf(b);
		return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
	});
	for (const key of orderedKeys) {
		const items = buckets.get(key).slice(0, 4);
		const meta = PACK_META[key] || { label: key, icon: "📦" };
		groups.push({
			key,
			label: meta.label,
			icon: meta.icon,
			items,
			startIndex: runningIndex,
		});
		runningIndex += items.length;
	}
	return groups;
});

const otherStartIndex = computed(() => {
	const lastGroup = packGroups.value[packGroups.value.length - 1];
	if (lastGroup) return lastGroup.startIndex + lastGroup.items.length;
	return pinnedMatches.value.length;
});

const otherMatches = computed(() => {
	return filteredNonPinned.value.filter((t) => !t.pack).slice(0, 5);
});

const totalCount = computed(() => {
	const packTotal = packGroups.value.reduce((acc, g) => acc + g.items.length, 0);
	return pinnedMatches.value.length + packTotal + otherMatches.value.length;
});

const activeTemplate = computed(() => {
	const idx = activeIndex.value;
	if (idx < pinnedMatches.value.length) return pinnedMatches.value[idx];
	for (const g of packGroups.value) {
		if (idx < g.startIndex + g.items.length) return g.items[idx - g.startIndex];
	}
	return otherMatches.value[idx - otherStartIndex.value];
});

watch(
	() => props.query,
	() => {
		activeIndex.value = 0;
	}
);
watch(
	() => props.open,
	(v) => {
		if (v) activeIndex.value = 0;
	}
);

watch(activeIndex, () => {
	nextTick(() => {
		const el = rowRefs.value[activeIndex.value];
		if (el && el.scrollIntoView) {
			el.scrollIntoView({ block: "nearest" });
		}
	});
});

function move(delta) {
	if (totalCount.value === 0) return;
	activeIndex.value = (activeIndex.value + delta + totalCount.value) % totalCount.value;
}

function pickActive() {
	const t = activeTemplate.value;
	if (t) pick(t);
}

function pick(t) {
	emit("pick", t);
}

defineExpose({ move, pickActive });
</script>

<style scoped>
.slash-menu {
	position: relative;
	left: 0;
	right: 0;
	bottom: calc(100% + 0.375rem);
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.75rem;
	box-shadow: 0 12px 32px rgba(0, 0, 0, 0.12), 0 2px 6px rgba(0, 0, 0, 0.06);
	max-height: 22rem;
	overflow-y: auto;
	z-index: 30;
	padding: 0.375rem;
	animation: menu-pop 0.12s ease-out;
}

@keyframes menu-pop {
	from {
		opacity: 0;
		transform: translateY(4px);
	}
	to {
		opacity: 1;
		transform: translateY(0);
	}
}

.menu-section + .menu-section {
	margin-top: 0.25rem;
	border-top: 1px solid var(--ql-border);
	padding-top: 0.375rem;
}

.section-label {
	display: flex;
	align-items: center;
	gap: 0.375rem;
	font-size: 0.625rem;
	font-weight: 600;
	text-transform: uppercase;
	letter-spacing: 0.05em;
	color: var(--ql-text-muted);
	padding: 0.375rem 0.625rem 0.25rem;
}

.section-icon {
	font-size: 0.875rem;
	line-height: 1;
}

.menu-row {
	display: flex;
	align-items: center;
	gap: 0.625rem;
	width: 100%;
	padding: 0.5rem 0.625rem;
	background: transparent;
	border: none;
	border-radius: 0.5rem;
	color: var(--ql-text);
	text-align: left;
	cursor: pointer;
	transition: background 0.1s ease;
}

.menu-row-active {
	background: var(--ql-subtle);
}

.row-icon {
	font-size: 1rem;
	line-height: 1;
	flex-shrink: 0;
}

.row-body {
	flex: 1;
	min-width: 0;
	display: flex;
	flex-direction: column;
	gap: 0.125rem;
}

.row-title {
	font-size: 0.875rem;
	font-weight: 500;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.row-desc {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.row-enter {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	opacity: 0;
	transition: opacity 0.1s ease;
	flex-shrink: 0;
}

.menu-row-active .row-enter {
	opacity: 1;
}

.menu-empty {
	padding: 1rem 0.75rem;
	font-size: 0.8125rem;
	color: var(--ql-text-muted);
	text-align: center;
}

.empty-query {
	font-family: "SF Mono", "Monaco", "Cascadia Code", monospace;
	color: var(--ql-text);
	padding: 0.0625rem 0.25rem;
	background: var(--ql-subtle);
	border-radius: 0.25rem;
}

.menu-footer {
	display: flex;
	align-items: center;
	gap: 0.75rem;
	padding: 0.5rem 0.625rem 0.375rem;
	margin-top: 0.25rem;
	border-top: 1px solid var(--ql-border);
	font-size: 0.6875rem;
	color: var(--ql-text-muted);
}

.menu-footer kbd {
	display: inline-block;
	padding: 0.0625rem 0.25rem;
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 0.25rem;
	font-family: inherit;
	font-size: 0.6875rem;
	line-height: 1;
	margin-right: 0.125rem;
}

.browse-all-btn {
	margin-left: auto;
	background: transparent;
	border: none;
	color: var(--ql-accent);
	font-size: 0.6875rem;
	font-weight: 500;
	cursor: pointer;
	padding: 0;
}

.browse-all-btn:hover {
	text-decoration: underline;
}

[data-theme="dark"] .slash-menu,
.dark .slash-menu {
	box-shadow: 0 12px 32px rgba(0, 0, 0, 0.5), 0 2px 6px rgba(0, 0, 0, 0.3);
}

[data-theme="dark"] .menu-footer kbd,
.dark .menu-footer kbd {
	background: rgba(0, 0, 0, 0.3);
}
</style>
