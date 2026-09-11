import { baseCall, getCall } from "../_core";

const BASE = "frappe_assistant_core.chat.api.routing_preferences";

export const routingPreferences = {
	list: () => getCall(`${BASE}.list_routing_preferences`),

	create: (matchKind, matchValue, targetTier) =>
		baseCall(`${BASE}.create_routing_preference`, {
			match_kind: matchKind,
			match_value: matchValue,
			target_tier: targetTier,
		}),

	setStatus: (preferenceId, status) =>
		baseCall(`${BASE}.set_routing_preference_status`, {
			preference_id: preferenceId,
			status,
		}),

	setMode: (preferenceId, ruleMode) =>
		baseCall(`${BASE}.set_routing_preference_mode`, {
			preference_id: preferenceId,
			rule_mode: ruleMode,
		}),

	remove: (preferenceId) =>
		baseCall(`${BASE}.delete_routing_preference`, {
			preference_id: preferenceId,
		}),

	forecast: (matchKind, matchValue, targetTier) =>
		baseCall(`${BASE}.forecast_routing_preference`, {
			match_kind: matchKind,
			match_value: matchValue,
			target_tier: targetTier,
		}),
};
