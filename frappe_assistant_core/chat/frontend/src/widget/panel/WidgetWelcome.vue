<template>
	<div class="ww">
		<h3>{{ t("Hi! I'm FACO") }}</h3>
		<p>{{ t("Your Frappe Assistant Copilot. I can help you with:") }}</p>
		<ul>
			<li>{{ t("Understanding forms and data") }}</li>
			<li>{{ t("Creating and managing documents") }}</li>
			<li>{{ t("Answering questions about Frappe") }}</li>
			<li>{{ t("Navigating the system") }}</li>
		</ul>
		<p v-if="contextLine" class="ww-context">{{ contextLine }}</p>
	</div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from "vue";
import { detectContext, contextDisplayText } from "../desk/pageContext.js";
import { t } from "./i18n.js";

const contextLine = ref("");
const update = () => (contextLine.value = contextDisplayText(detectContext()) || "");
onMounted(() => {
	update();
	window.frappe?.router?.on("change", update);
});
onUnmounted(() => window.frappe?.router?.off?.("change", update));
</script>

<style scoped>
.ww {
	padding: 24px 20px;
	color: var(--ql-text-secondary);
}
h3 {
	margin: 0 0 8px;
	font-family: var(--ql-font-display);
	font-size: 18px;
	font-weight: 600;
	color: var(--ql-text);
}
p {
	margin: 0 0 8px;
}
ul {
	margin: 0 0 12px;
	padding-left: 20px;
	list-style: disc;
}
.ww-context {
	display: inline-block;
	padding: 4px 10px;
	border-radius: 999px;
	background: var(--ql-accent-soft);
	color: var(--ql-accent);
	font-size: 12px;
}
</style>
