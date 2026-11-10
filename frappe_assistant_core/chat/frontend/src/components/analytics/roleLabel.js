const CREW_PREFIX = "crew:";

export function roleLabel(role) {
	if (role === "orchestrator") return "Lead";
	if (role === "helper") return "Helper";
	if (typeof role === "string" && role.startsWith(CREW_PREFIX)) {
		return `Crew · ${role.slice(CREW_PREFIX.length)}`;
	}
	return role;
}

export function roleClass(role) {
	if (typeof role === "string" && role.startsWith(CREW_PREFIX)) return "crew";
	return role;
}
