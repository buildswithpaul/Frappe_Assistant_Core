<template>
	<span class="role-badge" :class="roleClass">{{ role }}</span>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
	role: { type: String, default: "Member" },
});

const roleClass = computed(
	() =>
		({
			Owner: "role-owner",
			Admin: "role-admin",
			Member: "role-member",
		})[props.role] || "role-member"
);
</script>

<style scoped>
.role-badge {
	display: inline-flex;
	padding: 1px 8px;
	border-radius: 9999px;
	font-size: 0.68rem;
	font-weight: 600;
	white-space: nowrap;
}

/* Owner = gold: the one place gold marks non-money — authority / account holder. */
.role-owner {
	background: var(--ql-gold-soft);
	color: #8a6d12;
}

.role-admin {
	background: var(--ql-accent-soft);
	color: var(--ql-accent);
}

.role-member {
	background: var(--ql-subtle);
	color: var(--ql-text-secondary);
}

[data-theme="dark"] .role-owner {
	color: #e3c869;
}
</style>
