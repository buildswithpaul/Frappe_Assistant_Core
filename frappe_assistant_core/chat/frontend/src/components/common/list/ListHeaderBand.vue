<template>
	<div class="ql-header-band">
		<div class="ql-header-text">
			<h1 class="ql-header-title">{{ title }}</h1>
			<p v-if="stat" class="ql-header-stat">{{ stat }}</p>
		</div>
		<div class="ql-header-actions">
			<slot name="actions" />
		</div>
	</div>
</template>

<script setup>
defineProps({
	title: { type: String, required: true },
	stat: { type: String, default: "" },
});
</script>

<style scoped>
.ql-header-band {
	display: flex;
	align-items: center;
	gap: 16px;
	margin-bottom: 16px;
}
.ql-header-text {
	min-width: 0;
}
.ql-header-title {
	font-family: var(--ql-font-display, Georgia, "Source Serif 4", serif);
	font-size: 22px;
	line-height: 1.15;
	letter-spacing: -0.01em;
	color: var(--ql-text);
	margin: 0;
}
.ql-header-stat {
	font-size: 12px;
	color: var(--ql-text-muted);
	margin: 2px 0 0;
}
.ql-header-actions {
	margin-left: auto;
	display: flex;
	align-items: center;
	gap: 8px;
	min-width: 0;
}
/* On phones the title + actions can't share a row — let the band wrap so the
   actions (filter chips, buttons) flow to a second line instead of overflowing
   the viewport. The actions themselves stay left-aligned once wrapped. */
@media (max-width: 767px) {
	.ql-header-band {
		flex-wrap: wrap;
		gap: 12px;
	}
	.ql-header-actions {
		margin-left: 0;
		flex-wrap: wrap;
	}
}
</style>
