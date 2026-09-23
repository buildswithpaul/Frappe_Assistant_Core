<template>
	<button type="button" class="ql-add-slot" @click="$emit('click')">
		<span class="ql-add-plus">＋</span>
		<span class="ql-add-label">{{ label }}</span>
	</button>
</template>

<script setup>
defineProps({ label: { type: String, default: "Add" } });
defineEmits(["click"]);
</script>

<style scoped>
.ql-add-slot {
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	gap: 4px;
	min-height: 84px;
	border: 1.5px dashed var(--ql-border-hover);
	border-radius: 10px;
	background: transparent;
	color: var(--ql-text-muted);
	cursor: pointer;
	transition: border-color 0.15s ease, color 0.15s ease;
}
.ql-add-slot:hover {
	border-color: var(--ql-accent);
	color: var(--ql-accent);
}
.ql-add-plus {
	font-size: 18px;
	line-height: 1;
}
.ql-add-label {
	font-size: 11px;
}
</style>
