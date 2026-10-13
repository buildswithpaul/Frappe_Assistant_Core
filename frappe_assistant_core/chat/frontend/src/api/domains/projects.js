import { baseCall, getCall } from "../_core";

const P = "frappe_assistant_core.chat.api.chat.projects";

export const projects = {
	list: () => getCall(`${P}.get_projects`),
	create: (title, instructions = "") => baseCall(`${P}.create_project`, { title, instructions }),
	update: (project, { title = null, instructions = null } = {}) =>
		baseCall(`${P}.update_project`, {
			project,
			...(title !== null ? { title } : {}),
			...(instructions !== null ? { instructions } : {}),
		}),
	remove: (project) => baseCall(`${P}.delete_project`, { project }),
};
