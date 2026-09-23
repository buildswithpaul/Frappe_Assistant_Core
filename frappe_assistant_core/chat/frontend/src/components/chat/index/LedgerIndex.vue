<template>
	<nav aria-label="Conversation index" class="ledger-index" :class="`mode-${mode}`" @keydown="onKeydown">
		<template v-if="mode === 'full'">
			<div class="index-head">
				<span class="index-label">Index · {{ exchangeCount }} exchanges</span>
				<button class="index-collapse" aria-label="Collapse index" @click="$emit('collapse')">‹</button>
			</div>
			<div v-if="pinned.length" class="index-section-label">Pinned</div>
			<div v-for="p in pinned" :key="p.messageId" class="index-pin-chip">
				<button class="index-pin-jump" @click="$emit('jump-pin', p.messageId)">⚲ {{ p.heading }}</button>
				<button
					class="index-pin-remove"
					:aria-label="`Unpin ${p.heading}`"
					@click="$emit('unpin', p.messageId)"
				>✕</button>
			</div>
			<div class="index-section-label">Outline</div>
		</template>
		<button
			v-if="mode === 'spine'"
			class="spine-expand"
			aria-label="Expand index"
			@click="$emit('collapse')"
		>›</button>
		<div class="index-outline" :class="{ spine: mode === 'spine' }">
			<template v-for="entry in entries" :key="entry.key">
				<div v-if="entry.kind === 'divider'" class="index-divider" aria-hidden="true">
					<i></i><span v-if="mode === 'full'">context summarized</span><i></i>
				</div>
				<IndexEntry
					v-else
					:entry="entry"
					:active="entry.index === activeIndex"
					:spine="mode === 'spine'"
					@jump="$emit('jump', entry.index)"
				/>
			</template>
		</div>
	</nav>
</template>

<script setup>
import { computed } from "vue";
import IndexEntry from "./IndexEntry.vue";

const props = defineProps({
	entries: { type: Array, default: () => [] },
	activeIndex: { type: Number, default: -1 },
	mode: { type: String, default: "full" },
	pinned: { type: Array, default: () => [] },
});
defineEmits(["jump", "jump-pin", "unpin", "collapse"]);

const exchangeCount = computed(() => props.entries.filter((e) => e.kind === "exchange").length);

function onKeydown(e) {
	if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
	const buttons = [...e.currentTarget.querySelectorAll(".index-entry, .spine-tick")];
	const i = buttons.indexOf(document.activeElement);
	if (i === -1) return;
	e.preventDefault();
	const next = buttons[i + (e.key === "ArrowDown" ? 1 : -1)];
	if (next) next.focus();
}
</script>

<style scoped>
.ledger-index {
	padding: 24px 14px 24px 20px;
	overflow-y: auto;
	height: 100%;
}
.ledger-index.mode-spine {
	padding: 24px 0;
}

.index-head {
	display: flex;
	align-items: center;
	justify-content: space-between;
	margin-bottom: 10px;
}
.index-label,
.index-section-label {
	font-size: 10px;
	text-transform: uppercase;
	letter-spacing: 0.08em;
	color: var(--ql-text-muted);
}
.index-section-label {
	margin: 12px 0 6px 14px;
}

.index-collapse {
	border: none;
	background: transparent;
	color: var(--ql-text-muted);
	cursor: pointer;
	font-size: 13px;
	line-height: 1;
	padding: 2px 6px;
	border-radius: 4px;
}
.index-collapse:hover {
	background: var(--ql-subtle);
	color: var(--ql-text);
}

.spine-expand {
	display: block;
	margin: 0 auto 10px;
	border: none;
	background: transparent;
	color: var(--ql-text-muted);
	cursor: pointer;
	font-size: 13px;
	line-height: 1;
	padding: 2px 6px;
	border-radius: 4px;
}
.spine-expand:hover {
	background: var(--ql-subtle);
	color: var(--ql-text);
}

.index-outline {
	border-left: 2px solid var(--ql-border);
	padding-left: 4px;
}
.index-outline.spine {
	border-left: none;
	display: flex;
	flex-direction: column;
	align-items: center;
	padding-left: 0;
}

.index-divider {
	display: flex;
	align-items: center;
	gap: 6px;
	padding: 6px 8px 6px 14px;
	font-size: 10px;
	color: var(--ql-text-muted);
}
.index-divider i {
	flex: 1;
	height: 1px;
	background: var(--ql-border);
	font-style: normal;
}

.index-pin-chip {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 4px;
	margin: 0 0 4px 14px;
	padding: 3px 6px;
	font-size: 11.5px;
	border: 1px solid var(--ql-border);
	border-radius: 7px;
	background: var(--ql-bg);
}
.index-pin-jump {
	border: none;
	background: transparent;
	color: var(--ql-text-secondary);
	cursor: pointer;
	text-align: left;
	flex: 1;
	padding: 0;
	font-size: inherit;
}
.index-pin-remove {
	border: none;
	background: transparent;
	color: var(--ql-text-muted);
	cursor: pointer;
	padding: 0 2px;
	font-size: 10px;
}
.index-pin-remove:hover {
	color: var(--ql-text);
}
</style>
