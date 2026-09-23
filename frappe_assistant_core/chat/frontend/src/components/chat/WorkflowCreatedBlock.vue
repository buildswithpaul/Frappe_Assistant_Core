<template>
	<div class="workflow-created-block">
		<div class="wcb-body">
			<span class="wcb-check">✓</span>
			<span class="wcb-text">
				{{ block.action === "updated" ? "Updated" : "Created" }}
				<strong>{{ block.workflow_name }}</strong>
				<span class="wcb-status">({{ block.status }})</span>
			</span>
		</div>
		<button class="wcb-open" type="button" @click="openBuilder">Open in builder →</button>
	</div>
</template>

<script setup>
import { useRouter } from "vue-router";

const props = defineProps({ block: { type: Object, required: true } });
const router = useRouter();

function openBuilder() {
	router.push({ name: "agent-builder", params: { id: props.block.docname } });
}
</script>

<style scoped>
.workflow-created-block {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 12px;
	padding: 10px 14px;
	border: 1px solid var(--ql-border);
	border-radius: 10px;
	background: var(--ql-subtle);
	margin: 6px 0;
}
.wcb-body { display: flex; align-items: center; gap: 8px; min-width: 0; color: var(--ql-text); }
.wcb-check { color: var(--ql-accent); font-weight: 700; }
.wcb-text { overflow: hidden; text-overflow: ellipsis; }
.wcb-status { color: var(--ql-text-muted); margin-left: 4px; }
.wcb-open {
	flex: none;
	padding: 6px 12px;
	border: none;
	border-radius: 8px;
	background: var(--ql-accent);
	color: #fff;
	cursor: pointer;
	font-weight: 600;
}
.wcb-open:hover { filter: brightness(1.08); }
</style>
