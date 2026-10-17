<template>
	<div class="frs">
		<button
			v-for="card in cards"
			:key="card.text"
			type="button"
			class="frs-card"
			@click="$emit('pick', card.text)"
		>
			<span class="frs-preview" :class="`frs-preview--${card.kind}`" aria-hidden="true">
				<template v-if="card.kind === 'see'">
					<i v-for="h in BAR_HEIGHTS" :key="h" :style="{ height: `${h}%` }"></i>
				</template>
				<template v-else-if="card.kind === 'find'">
					<i v-for="w in ROW_WIDTHS" :key="w" :style="{ width: `${w}%` }"></i>
				</template>
				<template v-else>
					<i v-for="w in EMAIL_WIDTHS" :key="w" :style="{ width: `${w}%` }"></i>
				</template>
			</span>
			<span v-if="card.label" class="frs-label">{{ card.label }}</span>
			<span class="frs-text">{{ card.text }}</span>
		</button>
	</div>
</template>

<script setup>
import { computed } from "vue";
import { __ } from "@/utils/i18n";

const props = defineProps({ tiles: { type: Array, default: () => [] } });
defineEmits(["pick"]);

const BAR_HEIGHTS = [38, 62, 48, 86, 70];
const ROW_WIDTHS = [92, 78, 86, 64];
const EMAIL_WIDTHS = [48, 100, 90, 56];

const KINDS = ["see", "find", "do"];
const KIND_LABELS = [
	{ kind: "see", label: () => __("See it") },
	{ kind: "find", label: () => __("Find it") },
	{ kind: "do", label: () => __("Do it") },
];

// One tile per kind, matched on what the starter produces. `tiles` is the full
// starter list in server order: the first tile per kind wins, and a
// personalized tile without a kind never takes a labelled slot. A missing kind is filled from the remaining tiles, shown
// without a label and previewed as its own kind when it has one.
const cards = computed(() => {
	const picked = KIND_LABELS.map(({ kind, label }) => {
		const tile = props.tiles.find((t) => t.kind === kind);
		return tile ? { kind, label: label(), tile } : { kind, label: "", tile: null };
	});
	const used = new Set(picked.map((c) => c.tile).filter(Boolean));
	const spare = props.tiles.filter((t) => !used.has(t));
	return picked
		.map((c) => {
			if (c.tile) return c;
			const tile = spare.shift() || null;
			return { ...c, kind: KINDS.includes(tile?.kind) ? tile.kind : "find", tile };
		})
		.filter((c) => c.tile)
		.map((c) => ({ kind: c.kind, label: c.label, text: c.tile.description }));
});
</script>

<style scoped>
.frs { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--ql-space-3); }
.frs-card {
	display: flex; flex-direction: column; gap: var(--ql-space-2); min-height: 44px;
	padding: var(--ql-space-3); text-align: left; cursor: pointer;
	background: var(--ql-surface); border: 1px solid var(--ql-border); border-radius: var(--ql-radius-xl);
	font-family: var(--ql-font-sans); color: var(--ql-text); transition: border-color 0.15s ease;
}
.frs-card:hover { border-color: var(--ql-border-hover); }
.frs-card:focus-visible { outline: 2px solid var(--ql-accent); outline-offset: 2px; }
.frs-label {
	font-size: var(--ql-label-size); font-weight: 600; text-transform: uppercase;
	letter-spacing: var(--ql-label-tracking); color: var(--ql-accent);
}
.frs-text { font-size: 13.5px; line-height: 1.35; }
.frs-preview {
	display: flex; gap: 5px; height: 56px; padding: var(--ql-space-2);
	background: var(--ql-subtle); border-radius: var(--ql-radius-md);
}
.frs-preview i { display: block; background: var(--ql-border-hover); border-radius: 2px; }
.frs-preview--see { align-items: flex-end; }
.frs-preview--see i { flex: 1; background: var(--ql-accent); opacity: 0.55; }
.frs-preview--see i:nth-child(4) { opacity: 1; }
.frs-preview--find, .frs-preview--do { flex-direction: column; justify-content: center; gap: 6px; }
.frs-preview--find i, .frs-preview--do i { height: 6px; }
.frs-preview--do i:first-child { background: var(--ql-gold); }
@media (max-width: 719px) {
	.frs { grid-template-columns: 1fr; }
}
</style>
