export async function checkAccess() {
	try {
		const r = await window.frappe.call({
			method: "frappe_assistant_core.chat.api.settings.access.can_use_faco",
			type: "GET",
			args: {},
		});
		return r.message || { can_use: false, show_widget: false };
	} catch {
		return { can_use: false, show_widget: false, reason: "Error checking access" };
	}
}

// The diagnostics kill switch resolves here, ahead of the show_widget early return, so a
// non-member or admin-disabled user still gets the operator's decision. It is persisted
// only when the field came back: checkAccess()'s catch omits it, and that fail-open
// "enabled" must not overwrite a real persisted "off". This is the ONLY writer; a second
// one (reading get_widget_settings) once re-enabled diagnostics over a correct "off".
export function applyDiagnosticsSwitch(access) {
	if (!window.FACODiagnostics) return;
	const present = access.enable_browser_diagnostics !== undefined;
	window.FACODiagnostics.setEnabled(access.enable_browser_diagnostics !== false, present);
}
