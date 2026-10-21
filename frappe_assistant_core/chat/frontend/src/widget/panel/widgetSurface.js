import { configureSurface } from "@/stores/chat/surface";
import { getHost } from "../host/index.js";

function clientSignals() {
	const d = window.FACODiagnostics;
	if (!d) return null;
	const counts = d.counts();
	return counts.console || counts.failed_requests ? JSON.stringify({ recent_errors: counts }) : null;
}

export function configureWidgetSurface() {
	configureSurface({
		name: "widget",
		clientType: getHost().clientType,
		spotlightSurface: "widget",
		clientSignals,
	});
}
