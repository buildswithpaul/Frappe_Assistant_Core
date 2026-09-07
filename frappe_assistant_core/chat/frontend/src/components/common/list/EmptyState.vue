<template>
	<div class="ql-empty">
		<div class="ql-empty-hero">
			<FacoRobot size="sm" float show-arms />
		</div>
		<h3 class="ql-empty-title">{{ title }}</h3>
		<p v-if="description" class="ql-empty-desc">{{ description }}</p>
		<button v-if="cta" type="button" class="ql-empty-cta" @click="$emit('cta')">
			{{ cta }}
		</button>
		<slot name="footnote" />
	</div>
</template>

<script setup>
import FacoRobot from "@/components/common/FacoRobot.vue";

defineProps({
	title: { type: String, required: true },
	description: { type: String, default: "" },
	cta: { type: String, default: "" },
});
defineEmits(["cta"]);
</script>

<style scoped>
.ql-empty {
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	text-align: center;
	padding: 64px 32px;
	min-height: 400px;
}
.ql-empty-hero {
	margin-bottom: 24px;
}
.ql-empty-title {
	font-family: var(--ql-font-display, Georgia, "Source Serif 4", serif);
	font-size: 20px;
	color: var(--ql-text);
	margin: 0 0 8px;
}
.ql-empty-desc {
	font-size: 15px;
	color: var(--ql-text-secondary);
	max-width: 420px;
	line-height: 1.6;
	margin: 0 0 24px;
}
.ql-empty-cta {
	display: inline-flex;
	align-items: center;
	gap: 8px;
	padding: 12px 24px;
	font-size: 15px;
	font-weight: 600;
	color: #fff;
	background: var(--ql-accent);
	border: none;
	border-radius: 12px;
	cursor: pointer;
	transition: background 0.2s ease;
}
.ql-empty-cta:hover {
	background: var(--ql-accent-hover);
}
</style>
