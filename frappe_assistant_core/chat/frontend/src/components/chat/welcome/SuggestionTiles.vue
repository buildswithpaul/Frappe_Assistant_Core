<template>
	<div class="st">
		<div class="st-label">{{ hasPersonalized ? "For you" : "Or try one of these" }}</div>
		<div class="st-grid">
			<button
				v-for="(tile, i) in tiles"
				:key="tile.name || tile.description"
				type="button"
				class="st-tile"
				@click="$emit('pick', tile.description)"
			>
				<span class="st-icon" :class="i % 2 === 1 ? 'tone-gold' : 'tone-accent'" aria-hidden="true">
					{{ glyphFor(tile, i) }}
				</span>
				<span class="st-body">
					<span class="st-title">{{ tile.description }}</span>
					<span v-if="tile.subtext" class="st-sub">{{ tile.subtext }}</span>
				</span>
			</button>
		</div>
	</div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({ tiles: { type: Array, default: () => [] } });
defineEmits(["pick"]);

const GLYPHS = ["₹", "⊕", "◷", "↗"];
const CATEGORY_GLYPHS = {
	finance: "₹", data: "▤", docs: "✎", analysis: "↗", workflow: "⚙", general: "◷",
};
function glyphFor(tile, i) {
	if (tile.personalized) return "✦";
	return CATEGORY_GLYPHS[tile.category] || GLYPHS[i % GLYPHS.length];
}
const hasPersonalized = computed(() => props.tiles.some((t) => t.personalized));
</script>

<style scoped>
.st { text-align: left; }
.st-label {
	font-size: 10px; font-weight: 600; text-transform: uppercase;
	letter-spacing: 0.08em; color: var(--ql-text-muted); margin-bottom: 9px;
}
.st-grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 8px; }
.st-tile {
	display: flex; align-items: flex-start; gap: 9px;
	background: var(--ql-surface); border: 1px solid var(--ql-border);
	border-radius: 10px; padding: 10px 12px; cursor: pointer; text-align: left;
	transition: border-color 0.15s ease;
}
.st-tile:hover { border-color: var(--ql-border-hover); }
.st-icon {
	width: 28px; height: 28px; border-radius: 8px; flex-shrink: 0;
	display: inline-flex; align-items: center; justify-content: center; font-size: 13px;
}
.st-icon.tone-accent { background: var(--ql-accent-soft); color: var(--ql-accent); }
.st-icon.tone-gold { background: var(--ql-gold-soft); color: var(--ql-warning); }
.st-body { min-width: 0; }
.st-title {
	display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
	overflow: hidden; font-size: 12.5px; font-weight: 500; line-height: 1.35;
	color: var(--ql-text);
}
.st-sub {
	display: block; font-size: 11px; color: var(--ql-text-muted); margin-top: 2px;
	white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
</style>
