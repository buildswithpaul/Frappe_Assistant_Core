<template>
	<div ref="rootEl" class="link-picker" :class="{ open: isOpen }">
		<input
			ref="inputEl"
			v-model="query"
			:placeholder="placeholder"
			class="link-picker-input"
			autocomplete="off"
			spellcheck="false"
			@focus="onFocus"
			@input="onInput"
			@keydown.down.prevent="move(1)"
			@keydown.up.prevent="move(-1)"
			@keydown.enter.prevent="selectActive"
			@keydown.esc="close"
			@keydown.tab="close"
		/>
		<button
			v-if="query && !disabled"
			type="button"
			class="link-picker-clear"
			title="Clear"
			@click="clear"
		>
			×
		</button>
		<span class="link-picker-caret" aria-hidden="true">▾</span>

		<Teleport to="body">
			<div
				v-if="isOpen"
				ref="listEl"
				class="link-picker-list"
				:style="listStyle"
				role="listbox"
			>
				<div v-if="remoteLoading && filtered.length === 0" class="link-picker-empty">
					Searching…
				</div>
				<div v-else-if="filtered.length === 0" class="link-picker-empty">
					{{ emptyText }}
				</div>
				<div
					v-for="(opt, idx) in filtered"
					:key="opt.value"
					class="link-picker-option"
					:class="{ active: idx === activeIdx }"
					role="option"
					:aria-selected="idx === activeIdx"
					@mousedown.prevent="pick(opt)"
					@mouseenter="activeIdx = idx"
				>
					<div class="link-picker-label">
						<span v-html="highlight(opt.label)"></span>
					</div>
					<div v-if="opt.description" class="link-picker-sub">
						{{ opt.description }}
					</div>
				</div>
				<div v-if="hasMore" class="link-picker-overflow">
					More matches available. Keep typing to narrow.
				</div>
			</div>
		</Teleport>
	</div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { logger } from "@/utils/logger";

const props = defineProps({
	modelValue: { type: String, default: "" },
	// Static mode: pass the full list as `options` and the picker does local
	// substring filtering. Use for small lists (e.g. fields of one DocType).
	options: { type: Array, default: () => [] }, // [{value, label, description}]
	// Remote mode: pass a `fetcher(query)` that returns a Promise<{options, total}>.
	// The picker debounces calls and treats the result as authoritative for
	// the current query. Use for large lists (e.g. all DocTypes).
	fetcher: { type: Function, default: null },
	placeholder: { type: String, default: "Start typing…" },
	emptyText: { type: String, default: "No matches" },
	disabled: { type: Boolean, default: false },
	// Visible rows cap for static mode.
	maxResults: { type: Number, default: 200 },
	// Debounce for fetcher calls (remote mode).
	debounceMs: { type: Number, default: 180 },
});

const emit = defineEmits(["update:modelValue", "change"]);

const rootEl = ref(null);
const inputEl = ref(null);
const listEl = ref(null);
const query = ref(props.modelValue || "");
const isOpen = ref(false);
const activeIdx = ref(0);
const listStyle = ref({});

watch(
	() => props.modelValue,
	(v) => {
		if (v !== query.value) query.value = v || "";
	}
);

// --- Remote mode state (fed by the fetcher) ---
const remoteOptions = ref([]);
const remoteHasMore = ref(false);
const remoteLoading = ref(false);
let fetchSeq = 0; // guards against out-of-order responses
let debounceTimer = null;

const isRemote = computed(() => typeof props.fetcher === "function");

// --- Local substring matching (static mode) ---
function localMatches(q) {
	const opts = props.options || [];
	if (!q) return opts;
	const scored = [];
	for (const opt of opts) {
		const label = (opt.label || "").toLowerCase();
		if (!label.includes(q)) continue;
		let score = 0;
		if (label.startsWith(q)) score = 3;
		else if (new RegExp(`\\b${escapeRegex(q)}`).test(label)) score = 2;
		else score = 1;
		scored.push({ opt, score });
	}
	scored.sort((a, b) => b.score - a.score || a.opt.label.localeCompare(b.opt.label));
	return scored.map((s) => s.opt);
}

// `filtered` = what's rendered. In remote mode, trust the server;
// in static mode, apply local filter + cap.
const filtered = computed(() => {
	if (isRemote.value) return remoteOptions.value;
	const q = (query.value || "").trim().toLowerCase();
	return localMatches(q).slice(0, props.maxResults);
});

// Whether to render the "Keep typing to narrow…" hint at the bottom.
// Must be false when the list is empty, otherwise we contradict ourselves.
const hasMore = computed(() => {
	if (filtered.value.length === 0) return false;
	if (isRemote.value) return remoteHasMore.value;
	const q = (query.value || "").trim().toLowerCase();
	return localMatches(q).length > filtered.value.length;
});

function runFetcher(q) {
	if (!isRemote.value) return;
	const mySeq = ++fetchSeq;
	remoteLoading.value = true;
	Promise.resolve(props.fetcher(q))
		.then((res) => {
			if (mySeq !== fetchSeq) return; // stale
			const opts = (res && res.options) || [];
			remoteOptions.value = opts;
			remoteHasMore.value = !!(res && res.hasMore);
			activeIdx.value = 0;
		})
		.catch((err) => {
			if (mySeq !== fetchSeq) return;
			logger.error("LinkPicker fetcher failed", err);
			remoteOptions.value = [];
			remoteHasMore.value = false;
		})
		.finally(() => {
			if (mySeq === fetchSeq) remoteLoading.value = false;
		});
}

function scheduleFetch(q) {
	if (debounceTimer) clearTimeout(debounceTimer);
	debounceTimer = setTimeout(() => runFetcher(q), props.debounceMs);
}

function escapeRegex(s) {
	return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function highlight(label) {
	const q = (query.value || "").trim();
	if (!q) return escapeHtml(label);
	const re = new RegExp(`(${escapeRegex(q)})`, "ig");
	return escapeHtml(label).replace(re, "<mark>$1</mark>");
}

function escapeHtml(s) {
	return String(s ?? "")
		.replace(/&/g, "&amp;")
		.replace(/</g, "&lt;")
		.replace(/>/g, "&gt;")
		.replace(/"/g, "&quot;")
		.replace(/'/g, "&#039;");
}

function onFocus() {
	if (props.disabled) return;
	openList();
	// Prime the list on focus in remote mode if we haven't loaded yet.
	if (isRemote.value && remoteOptions.value.length === 0 && !remoteLoading.value) {
		runFetcher(query.value.trim());
	}
}

function onInput() {
	emit("update:modelValue", query.value);
	activeIdx.value = 0;
	openList();
	if (isRemote.value) {
		scheduleFetch(query.value.trim());
	}
}

async function openList() {
	isOpen.value = true;
	await nextTick();
	positionList();
}

function positionList() {
	if (!inputEl.value) return;
	const rect = inputEl.value.getBoundingClientRect();
	listStyle.value = {
		position: "fixed",
		top: `${rect.bottom + 4}px`,
		left: `${rect.left}px`,
		width: `${rect.width}px`,
		zIndex: 10000,
	};
}

function close() {
	isOpen.value = false;
}

function move(delta) {
	if (!isOpen.value) {
		openList();
		return;
	}
	const max = filtered.value.length;
	if (max === 0) return;
	activeIdx.value = (activeIdx.value + delta + max) % max;
}

function selectActive() {
	if (!isOpen.value) return;
	const opt = filtered.value[activeIdx.value];
	if (opt) pick(opt);
}

function pick(opt) {
	query.value = opt.value;
	emit("update:modelValue", opt.value);
	emit("change", opt);
	close();
}

function clear() {
	query.value = "";
	emit("update:modelValue", "");
	emit("change", null);
	inputEl.value?.focus();
}

function onDocClick(ev) {
	if (!rootEl.value || !isOpen.value) return;
	const insideRoot = rootEl.value.contains(ev.target);
	const insideList = listEl.value && listEl.value.contains(ev.target);
	if (!insideRoot && !insideList) close();
}

function onScrollOrResize() {
	if (isOpen.value) positionList();
}

onMounted(() => {
	document.addEventListener("mousedown", onDocClick);
	window.addEventListener("resize", onScrollOrResize);
	window.addEventListener("scroll", onScrollOrResize, true);
});

onBeforeUnmount(() => {
	document.removeEventListener("mousedown", onDocClick);
	window.removeEventListener("resize", onScrollOrResize);
	window.removeEventListener("scroll", onScrollOrResize, true);
	if (debounceTimer) clearTimeout(debounceTimer);
});
</script>

<style scoped>
.link-picker {
	position: relative;
	display: flex;
	align-items: center;
}
.link-picker-input {
	flex: 1;
	padding: 0.5rem 1.75rem 0.5rem 0.625rem;
	border: 1px solid var(--ql-border);
	border-radius: 0.375rem;
	font-size: 0.8125rem;
	background: var(--ql-surface);
	color: var(--ql-text);
	transition: border-color 0.15s ease, box-shadow 0.15s ease;
	outline: none;
}
.link-picker-input:focus {
	border-color: var(--ql-accent);
	box-shadow: 0 0 0 3px color-mix(in srgb, var(--ql-accent) 20%, transparent);
}
.link-picker-input::placeholder {
	color: var(--ql-text-muted);
}
.link-picker-clear {
	position: absolute;
	right: 1.625rem;
	top: 50%;
	transform: translateY(-50%);
	border: none;
	background: transparent;
	color: var(--ql-text-muted);
	cursor: pointer;
	font-size: 1rem;
	line-height: 1;
	padding: 0 0.25rem;
}
.link-picker-clear:hover {
	color: var(--ql-text);
}
.link-picker-caret {
	position: absolute;
	right: 0.625rem;
	top: 50%;
	transform: translateY(-50%);
	color: var(--ql-text-muted);
	pointer-events: none;
	font-size: 0.625rem;
}
</style>

<style>
/* Global styles for the teleported list (cannot be scoped because of Teleport) */
.link-picker-list {
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	color: var(--ql-text);
	border-radius: 0.375rem;
	box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25);
	max-height: 20rem;
	overflow-y: auto;
	padding: 0.25rem 0;
}
.link-picker-empty {
	padding: 0.75rem 0.875rem;
	color: var(--ql-text-secondary);
	font-size: 0.8125rem;
	text-align: center;
}
.link-picker-option {
	padding: 0.4375rem 0.75rem;
	cursor: pointer;
	font-size: 0.8125rem;
	color: var(--ql-text);
	display: flex;
	flex-direction: column;
	gap: 0.125rem;
}
.link-picker-option.active {
	background: color-mix(in srgb, var(--ql-accent) 14%, transparent);
	color: var(--ql-text);
}
.link-picker-option:hover:not(.active) {
	background: var(--ql-subtle);
}
.link-picker-label {
	line-height: 1.25;
}
.link-picker-label mark {
	background: color-mix(in srgb, var(--ql-accent) 25%, transparent);
	color: inherit;
	padding: 0;
	border-radius: 2px;
	font-weight: 600;
}
.link-picker-sub {
	font-size: 0.6875rem;
	color: var(--ql-text-secondary);
}
.link-picker-overflow {
	padding: 0.5rem 0.75rem;
	font-size: 0.6875rem;
	color: var(--ql-text-muted);
	text-align: center;
	font-style: italic;
	border-top: 1px solid var(--ql-border);
	background: var(--ql-subtle);
}
</style>
