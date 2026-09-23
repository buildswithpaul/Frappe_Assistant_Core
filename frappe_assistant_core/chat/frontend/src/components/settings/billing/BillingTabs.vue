<template>
	<div class="billing-tabs">
		<button
			v-for="tab in tabs"
			:key="tab.id"
			:class="['tab-btn', { active: modelValue === tab.id }]"
			@click="$emit('update:modelValue', tab.id)"
		>
			{{ tab.label }}
		</button>
	</div>
</template>

<script setup>
defineProps({
	modelValue: { type: String, required: true },
});

defineEmits(["update:modelValue"]);

const tabs = [
	{ id: "plans", label: "Plans" },
	{ id: "credits", label: "Credits" },
	{ id: "details", label: "Billing Details" },
	{ id: "payment", label: "Payment Method" },
	{ id: "invoices", label: "Invoices" },
	{ id: "settings", label: "Settings" },
];
</script>

<style scoped>
.billing-tabs {
	display: flex;
	gap: 0.125rem;
	border-bottom: 1px solid var(--ql-border);
	margin-top: 1.5rem;
	overflow-x: auto;
	-webkit-overflow-scrolling: touch;
	scrollbar-width: none;
}

.billing-tabs::-webkit-scrollbar {
	display: none;
}

.tab-btn {
	padding: 0.625rem 1rem;
	font-size: 0.8125rem;
	font-weight: 500;
	color: var(--ql-text-secondary);
	background: none;
	border: none;
	border-bottom: 2px solid transparent;
	cursor: pointer;
	transition: all 0.15s ease;
	margin-bottom: -1px;
	flex-shrink: 0;
	white-space: nowrap;
}

.tab-btn:hover {
	color: var(--ql-text);
}

.tab-btn.active {
	color: var(--ql-accent);
	border-bottom: 2px solid var(--ql-accent);
}
</style>
