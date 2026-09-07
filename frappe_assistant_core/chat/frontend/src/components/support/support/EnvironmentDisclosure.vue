<template>
	<div class="env-disclosure">
		<button type="button" class="env-toggle" @click="expanded = !expanded">
			<span>{{ expanded ? "▾" : "▸" }} What we'll attach</span>
		</button>
		<dl v-if="expanded" class="env-list">
			<template v-for="(value, key) in environment" :key="key">
				<dt>{{ key }}</dt>
				<dd>{{ value }}</dd>
			</template>
		</dl>
		<p v-if="expanded" class="env-note">
			This helps us debug. Nothing else is sent unless you include it above.
		</p>
	</div>
</template>

<script setup>
import { ref } from "vue";

defineProps({
	environment: { type: Object, required: true },
});

const expanded = ref(false);
</script>

<style scoped>
.env-disclosure {
	margin: 0.75rem 0;
	font-size: 0.85rem;
}
.env-toggle {
	background: none;
	border: none;
	cursor: pointer;
	color: var(--ql-text-muted);
	padding: 0;
}
.env-list {
	display: grid;
	grid-template-columns: max-content 1fr;
	gap: 0.25rem 0.75rem;
	margin: 0.5rem 0;
}
.env-list dt {
	font-weight: 600;
	color: var(--ql-text-muted);
}
.env-list dd {
	margin: 0;
	color: var(--ql-text-secondary);
	word-break: break-word;
}
.env-note {
	color: var(--ql-text-muted);
	margin: 0.25rem 0 0;
}
</style>
