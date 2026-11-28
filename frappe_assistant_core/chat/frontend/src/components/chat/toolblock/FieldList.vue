<template>
	<dl class="field-list">
		<template v-for="(field, i) in fields" :key="i">
			<dt>{{ field.label }}</dt>
			<dd>{{ field.value }}</dd>
		</template>
	</dl>
</template>

<script setup>
defineProps({
	// `{label, value}` pairs, as toolView builds them.
	fields: { type: Array, required: true },
});
</script>

<style scoped>
.field-list {
	display: grid;
	grid-template-columns: fit-content(40%) minmax(0, 1fr);
	gap: 3px 14px;
	margin: 0;
	font-size: 12px;
}
dt {
	overflow-wrap: anywhere;
	color: var(--ql-text-muted);
}
dd {
	margin: 0;
	overflow-wrap: anywhere;
	color: var(--ql-text);
}
</style>
