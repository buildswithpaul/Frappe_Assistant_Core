<template>
	<div class="pn" role="status">
		<span class="pn-text">
			💡 {{ count }} industry pack{{ count === 1 ? "" : "s" }} available — tailored prompts and skills.
		</span>
		<button type="button" class="pn-cta" @click="$emit('enable')">Enable</button>
		<button type="button" class="pn-dismiss" aria-label="Dismiss" @click="$emit('dismiss')">×</button>
	</div>
</template>

<script setup>
defineProps({ count: { type: Number, required: true } });
defineEmits(["enable", "dismiss"]);
</script>

<style scoped>
.pn {
	display: flex; align-items: center; gap: 10px;
	font-size: 12.5px; color: var(--ql-text-muted); text-align: left;
	padding: 6px 2px;
}
.pn-text { flex: 1; min-width: 0; }
.pn-cta {
	background: none; border: none; padding: 0; cursor: pointer;
	color: var(--ql-accent); font-weight: 600; font-size: 12.5px;
}
.pn-cta:hover { color: var(--ql-accent-hover); }
.pn-dismiss {
	background: none; border: none; cursor: pointer; padding: 0 4px;
	color: var(--ql-text-muted); font-size: 15px; line-height: 1;
}
.pn-dismiss:hover { color: var(--ql-text); }
</style>
