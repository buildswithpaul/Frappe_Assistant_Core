import { defineStore } from "pinia";
import { ref } from "vue";
import { api } from "@/api/client";
import { useChatStore } from "@/stores/chatStore";

export const useProjectsStore = defineStore("projects", () => {
	const projects = ref([]);

	function hydrate(list) {
		projects.value = list || [];
	}

	async function load() {
		hydrate(await api.projects.list());
	}

	function byId(id) {
		return projects.value.find((p) => p.name === id) || null;
	}

	async function create(title, instructions = "") {
		const project = await api.projects.create(title, instructions);
		projects.value = [project, ...projects.value];
		return project;
	}

	async function update(id, patch) {
		const updated = await api.projects.update(id, patch);
		// update_project returns no conversation_count, so merge rather than replace.
		projects.value = projects.value.map((p) => (p.name === id ? { ...p, ...updated } : p));
		if (patch.title != null) {
			const chat = useChatStore();
			chat.sessions
				.filter((s) => s.project === id)
				.forEach((s) => chat.patchSession(s.session_id, { project_title: updated.title }));
		}
		return updated;
	}

	async function remove(id) {
		await api.projects.remove(id);
		projects.value = projects.value.filter((p) => p.name !== id);
		const chat = useChatStore();
		if (chat.pendingProject?.projectId === id) chat.setPendingProject(null, null);
		chat.sessions
			.filter((s) => s.project === id)
			.forEach((s) => chat.patchSession(s.session_id, { project: null, project_title: null }));
	}

	return { projects, hydrate, load, byId, create, update, remove };
});
