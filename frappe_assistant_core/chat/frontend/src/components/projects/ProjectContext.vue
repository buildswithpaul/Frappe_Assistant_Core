<template>
	<aside class="project-context" :aria-label="__('Project context')">
		<ProjectInstructions :model-value="instructions" :save-fn="saveInstructions" />
		<ProjectDocuments v-if="documentsEnabled" :project-id="projectId" />
		<ProjectMemory v-if="memoryEnabled" :project-id="projectId" />
	</aside>
</template>

<script setup>
import ProjectInstructions from "@/components/projects/ProjectInstructions.vue";
import ProjectDocuments from "@/components/projects/ProjectDocuments.vue";
import ProjectMemory from "@/components/projects/ProjectMemory.vue";
import { __ } from "@/utils/i18n";

defineProps({
	projectId: { type: String, required: true },
	instructions: { type: String, default: "" },
	// Async persist; rejecting keeps the instructions editor open.
	saveInstructions: { type: Function, required: true },
	documentsEnabled: { type: Boolean, default: false },
	memoryEnabled: { type: Boolean, default: false },
});
</script>

<style scoped>
.project-context {
	display: flex;
	flex-direction: column;
	gap: 1rem;
	min-width: 0;
}
</style>
