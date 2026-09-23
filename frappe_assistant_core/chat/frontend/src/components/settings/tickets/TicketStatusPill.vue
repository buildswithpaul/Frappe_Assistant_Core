<template>
	<span class="pill" :class="cls">{{ status }}</span>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({ status: { type: String, default: "" } });

const cls = computed(
	() =>
		({
			Open: "amber",
			Replied: "blue",
			Resolved: "green",
			Closed: "grey",
		}[props.status] || "grey")
);
</script>

<style scoped>
.pill {
	font-size: 0.75rem;
	padding: 0.1rem 0.5rem;
	border-radius: 999px;
	font-weight: 600;
	display: inline-block;
}
.amber {
	background: #fef0c7;
	color: #b54708;
}
.blue {
	background: #d1e9ff;
	color: #175cd3;
}
.green {
	background: #d1fadf;
	color: #027a48;
}
.grey {
	background: #eaecf0;
	color: #475467;
}
</style>
