<template>
	<div class="hs">
		<h2 class="hs-heading">{{ __("Ask about your {0}", [__(area || "business")]) }}</h2>
		<ul class="hs-list">
			<li v-for="tile in tiles" :key="tile.name || tile.description">
				<button type="button" class="hs-row" @click="$emit('pick', tile.description)">
					<span class="hs-text">{{ tile.description }}</span>
					<span class="hs-arrow" aria-hidden="true">→</span>
				</button>
			</li>
		</ul>
	</div>
</template>

<script setup>
import { __ } from "@/utils/i18n";

defineProps({
	tiles: { type: Array, default: () => [] },
	// Null until the home endpoint answers; the heading falls back to "business".
	area: { type: String, default: null },
});
defineEmits(["pick"]);
</script>

<style scoped>
.hs { text-align: left; min-width: 0; }
.hs-heading {
	margin: 0 0 var(--ql-space-2);
	font-size: var(--ql-label-size); font-weight: 600; text-transform: uppercase;
	letter-spacing: var(--ql-label-tracking); color: var(--ql-text-muted);
}
.hs-list { margin: 0; padding: 0; list-style: none; border-top: 1px solid var(--ql-border); }
.hs-row {
	display: flex; align-items: center; justify-content: space-between; gap: var(--ql-space-3);
	width: 100%; min-height: 44px; padding: var(--ql-space-2) var(--ql-space-1);
	background: transparent; border: none; border-bottom: 1px solid var(--ql-border);
	font-family: var(--ql-font-sans); font-size: 13.5px; line-height: 1.35; text-align: left;
	color: var(--ql-text); cursor: pointer;
}
.hs-arrow { color: var(--ql-text-muted); transition: color 0.15s ease, transform 0.15s ease; }
.hs-row:hover .hs-arrow { color: var(--ql-accent); transform: translateX(2px); }
.hs-row:focus-visible { outline: 2px solid var(--ql-accent); outline-offset: -2px; }
</style>
