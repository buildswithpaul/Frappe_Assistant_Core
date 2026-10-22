<template>
	<header class="hh">
		<div class="hh-text">
			<template v-if="firstRun">
				<h1 class="hh-greeting">{{ __("Welcome, {0}. I work inside your ERPNext.", [displayName]) }}</h1>
				<p class="hh-sub">
					{{ __("I can see whatever you can see, and I ask before I change anything.") }}
				</p>
			</template>
			<template v-else>
				<div class="hh-date">{{ dateLabel }}</div>
				<h1 class="hh-greeting">{{ greetingLine }}</h1>
			</template>
		</div>
		<span v-if="chipLabel" class="hh-chip">{{ chipLabel }}</span>
	</header>
</template>

<script setup>
import { computed } from "vue";
import { formatDateLabel } from "@/components/chat/welcomeGreeting";
import { __ } from "@/utils/i18n";

const props = defineProps({
	greetingLine: { type: String, required: true },
	displayName: { type: String, required: true },
	lensLabel: { type: String, default: "" },
	company: { type: String, default: "" },
	firstRun: { type: Boolean, default: false },
});

const dateLabel = computed(() => formatDateLabel(new Date()));

// The chip needs a company; the lens alone says nothing about scope.
const chipLabel = computed(() => {
	if (!props.company) return "";
	return props.lensLabel ? __("{0} · {1}", [props.lensLabel, props.company]) : props.company;
});
</script>

<style scoped>
.hh {
	display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between;
	gap: var(--ql-space-2) var(--ql-space-4);
}
/* The basis lets the chip drop below the greeting when the container is narrow (the widget). */
.hh-text { flex: 1 1 18rem; min-width: 0; }
.hh-date {
	font-size: var(--ql-label-size); font-weight: 600; text-transform: uppercase;
	letter-spacing: var(--ql-label-tracking); color: var(--ql-text-muted);
}
.hh-greeting {
	margin: var(--ql-space-1) 0 0;
	font-family: var(--ql-font-display); font-size: 30px; font-weight: 500;
	line-height: 1.15; letter-spacing: -0.01em; text-wrap: balance; color: var(--ql-text);
}
.hh-sub { margin: var(--ql-space-2) 0 0; font-size: 15px; color: var(--ql-text-secondary); }
.hh-chip {
	flex: none; padding: var(--ql-space-1) var(--ql-space-3);
	font-size: 12px; font-weight: 500; color: var(--ql-text-secondary);
	background: var(--ql-subtle); border: 1px solid var(--ql-border); border-radius: 999px;
	white-space: nowrap; max-width: 100%; overflow: hidden; text-overflow: ellipsis;
}
@media (max-width: 719px) {
	.hh { flex-direction: column; align-items: flex-start; gap: var(--ql-space-2); }
	/* In a column the 18rem basis becomes a height and leaves a gap above the chip. */
	.hh-text { flex: none; }
	.hh-greeting { font-size: 24px; }
	.hh-chip { max-width: 100%; }
}
</style>
