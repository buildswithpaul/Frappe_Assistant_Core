<template>
	<div class="users-tabs" role="tablist">
		<button
			v-for="tab in tabs"
			:key="tab.id"
			:class="['tab-btn', { active: modelValue === tab.id }]"
			role="tab"
			:aria-selected="modelValue === tab.id"
			@click="$emit('update:modelValue', tab.id)"
		>
			{{ tab.label }}
			<span v-if="tab.id === 'invites' && inviteCount > 0" class="tab-badge">
				{{ inviteCount }}
			</span>
		</button>
	</div>
</template>

<script setup>
defineProps({
	modelValue: { type: String, default: "members" },
	inviteCount: { type: Number, default: 0 },
});

defineEmits(["update:modelValue"]);

const tabs = [
	{ id: "members", label: "Members" },
	{ id: "invites", label: "Invites" },
	{ id: "activity", label: "Activity" },
];
</script>

<style scoped>
.users-tabs {
	display: flex;
	gap: 0.125rem;
	border-bottom: 1px solid var(--ql-border);
	margin-top: 1.5rem;
}

.tab-btn {
	display: inline-flex;
	align-items: center;
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
}

.tab-btn:hover {
	color: var(--ql-text);
}

.tab-btn.active {
	color: var(--ql-accent);
	border-bottom: 2px solid var(--ql-accent);
}

.tab-badge {
	margin-left: 6px;
	padding: 0 6px;
	border-radius: 9999px;
	font-size: 0.66rem;
	font-weight: 600;
	background: var(--ql-accent-soft);
	color: var(--ql-accent);
}
</style>
