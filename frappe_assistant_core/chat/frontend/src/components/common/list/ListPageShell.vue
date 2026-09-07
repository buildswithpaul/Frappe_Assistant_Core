<template>
	<div ref="shellRef" class="ql-list-shell">
		<div class="ql-list-inner">
			<slot name="header" />
			<div v-if="$slots.toolbar" class="ql-list-toolbar">
				<slot name="toolbar" />
			</div>
			<div v-if="grid" class="ql-list-grid" :style="gridStyle">
				<slot />
			</div>
			<template v-else>
				<slot />
			</template>
		</div>
	</div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from "vue";
import { columnsForWidth } from "./gridColumns";

defineProps({
	// When true (default), default-slot children are laid out in the
	// responsive card grid. Set false for pages that supply their own grid
	// component (e.g. KnowledgeDocumentGrid) so we don't nest grid-in-grid.
	grid: { type: Boolean, default: true },
});

const shellRef = ref(null);
const innerWidth = ref(1200);
let ro = null;

const columns = computed(() => columnsForWidth(innerWidth.value));
const gridStyle = computed(() => ({
	gridTemplateColumns: `repeat(${columns.value}, minmax(0, 1fr))`,
}));

onMounted(() => {
	ro = new ResizeObserver((entries) => {
		for (const e of entries) innerWidth.value = e.contentRect.width;
	});
	if (shellRef.value) ro.observe(shellRef.value);
});
onBeforeUnmount(() => {
	if (ro) ro.disconnect();
});

// Exposed so a page using grid=false can still read the computed column count.
defineExpose({ columns });
</script>

<style scoped>
.ql-list-shell {
	flex: 1;
	overflow-y: auto;
	overflow-x: hidden;
	padding: 24px;
	background: var(--ql-bg);
}
.ql-list-inner {
	max-width: 1200px;
	margin: 0 auto;
	width: 100%;
	min-width: 0;
}
.ql-list-toolbar {
	margin-bottom: 16px;
}
.ql-list-grid {
	display: grid;
	gap: 12px;
}
@media (max-width: 767px) {
	.ql-list-shell {
		padding: 16px 12px;
	}
}
</style>
