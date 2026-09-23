<template>
	<div class="loading-state">
		<FacoRobot size="md" float show-arms show-shadow mood="thinking" />
		<p class="loading-text">{{ text }}</p>
	</div>
</template>

<script setup>
import FacoRobot from "@/components/common/FacoRobot.vue";

defineProps({
	text: { type: String, default: "Loading..." },
});
</script>

<style scoped>
.loading-state {
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	height: 100%;
	gap: 1.5rem;
}

.loading-text {
	font-size: 0.875rem;
	color: var(--ql-text-muted);
}
</style>
