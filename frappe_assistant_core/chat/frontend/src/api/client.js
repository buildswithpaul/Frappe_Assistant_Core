/**
 * FACO API Client
 *
 * Aggregates per-domain API modules under `domains/` into the public
 * `api` object every Vue component imports as `import { api } from
 * "@/api/client"`. Each domain module owns one nested key
 * (`api.chat`, `api.billing`, `api.users`, …) and only imports the
 * shared transport from `_core.js`.
 *
 * Splitting this file by domain keeps each surface focused and
 * navigable — the previous single-file shape grew past 1,200 lines.
 */

import { baseCall, getCall } from "./_core";

import { analytics } from "./domains/analytics";
import { billing } from "./domains/billing";
import { capabilities } from "./domains/capabilities";
import { chat } from "./domains/chat";
import { documents } from "./domains/documents";
import { files } from "./domains/files";
import { init } from "./domains/init";
import { memories } from "./domains/memories";
import { models } from "./domains/models";
import { notifications } from "./domains/notifications";
import { packs } from "./domains/packs";
import { privacy } from "./domains/privacy";
import { profile } from "./domains/profile";
import { registration } from "./domains/registration";
import { sharedKnowledge } from "./domains/sharedKnowledge";
import { suggestions } from "./domains/suggestions";
import { support } from "./domains/support";
import { templates } from "./domains/templates";
import { tools } from "./domains/tools";
import { user } from "./domains/user";
import { users } from "./domains/users";
import { workflows } from "./domains/workflows";

export const api = {
	// Low-level escape hatches for callers that need to hit an arbitrary
	// whitelisted endpoint without going through a domain helper.
	call: baseCall,
	get: getCall,

	init,
	chat,
	user,
	billing,
	capabilities,
	documents,
	memories,
	profile,
	sharedKnowledge,
	workflows,
	registration,
	suggestions,
	support,
	templates,
	models,
	files,
	users,
	analytics,
	notifications,
	packs,
	privacy,
	tools,
};

export default api;
