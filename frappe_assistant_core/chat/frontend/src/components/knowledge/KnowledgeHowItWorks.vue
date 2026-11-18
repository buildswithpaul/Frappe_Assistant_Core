<script setup>
// The empty Knowledge page explains itself: four steps light up in turn, so a first
// visit shows why to upload instead of an empty list with an Upload button.
import { __ } from "@/utils/i18n";

const STEPS = [
	() => __("Upload a document"),
	() => __("FAC reads it"),
	() => __("You ask a question"),
	() => __("Answer + the page it used"),
];
</script>

<template>
	<ol class="khw" data-test="knowledge-how-it-works" :aria-label="__('How Knowledge works')">
		<li v-for="(label, i) in STEPS" :key="i" :style="{ '--i': i }">
			<span class="khw-n">{{ i + 1 }}</span>{{ label() }}
		</li>
	</ol>
</template>

<style scoped>
.khw {
	display: grid;
	grid-template-columns: repeat(4, minmax(0, 1fr));
	gap: 8px;
	width: 100%;
	max-width: 560px;
	margin: 0 auto 24px;
	padding: 0;
	list-style: none;
}
.khw li {
	display: flex;
	flex-direction: column;
	align-items: center;
	gap: 6px;
	padding: 10px 6px;
	border: 1px solid var(--ql-border);
	border-radius: 10px;
	font-size: 12.5px;
	line-height: 1.3;
	color: var(--ql-text-secondary);
	animation: khw-on 0.4s ease both;
	animation-delay: calc(0.3s + var(--i) * 0.45s);
}
.khw-n {
	display: grid;
	place-items: center;
	width: 22px;
	height: 22px;
	border-radius: 50%;
	background: var(--ql-accent-soft);
	color: var(--ql-accent);
	font-weight: 700;
	font-size: 12px;
}
@keyframes khw-on {
	from { opacity: 0.3; border-color: var(--ql-border); }
	to { opacity: 1; border-color: var(--ql-accent); }
}
@media (max-width: 560px) {
	.khw { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (prefers-reduced-motion: reduce) {
	.khw li { animation: none; border-color: var(--ql-accent); }
}
</style>
