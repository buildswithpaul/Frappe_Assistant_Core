import { createApp } from "vue";
import { createPinia } from "pinia";
import "vue-echarts/dist/csp/style.css";
import "./preflight.css";
import "@/styles/quiet-ledger.css";
import "./panel.css";
import PanelApp from "./PanelApp.vue";
import { createRouterShim } from "./routerShim.js";
import { placePanel } from "./placement.js";
import { TELEPORT_TARGET_KEY } from "@/composables/useTeleportTarget";
import { configureSurface } from "@/stores/chat/surface";
import { mirrorDeskTheme } from "../launcher/theme.js";

function clientSignals() {
	const d = window.FACODiagnostics;
	if (!d) return null;
	const counts = d.counts();
	return counts.console || counts.failed_requests ? JSON.stringify({ recent_errors: counts }) : null;
}

export async function mountPanel(config) {
	configureSurface({
		name: "widget",
		clientType: "widget",
		modelId: "auto",
		spotlightSurface: "widget",
		clientSignals,
	});

	const host = document.createElement("div");
	host.id = "fac-widget-panel";
	host.hidden = true;
	document.body.appendChild(host);
	mirrorDeskTheme(host);
	const root = host.attachShadow({ mode: "open" });

	// Styles land before first paint: wait for every stylesheet.
	await Promise.all(
		(config.css || []).map(
			(href) =>
				new Promise((done) => {
					const link = document.createElement("link");
					link.rel = "stylesheet";
					link.href = href;
					link.onload = link.onerror = () => done();
					root.appendChild(link);
				})
		)
	);

	const overlay = document.createElement("div");
	overlay.className = "fac-overlay";
	const mountEl = document.createElement("div");
	mountEl.className = "fac-panel-root";
	root.append(mountEl, overlay);

	const app = createApp(PanelApp);
	app.use(createPinia());
	app.use(createRouterShim());
	app.provide(TELEPORT_TARGET_KEY, overlay);
	app.mount(mountEl);

	// The launcher can be dragged or the window resized while the panel is open.
	// The launcher button is hidden while open, so remember where it last had a size.
	let anchor = null;
	const place = () => {
		anchor = placePanel(host, anchor) || anchor;
	};
	window.addEventListener("resize", place);

	return {
		open({ anchorRect } = {}) {
			if (anchorRect && anchorRect.width > 0 && anchorRect.height > 0) anchor = anchorRect;
			place();
			host.hidden = false;
		},
		close() {
			host.hidden = true;
		},
		destroy() {
			window.removeEventListener("resize", place);
			app.unmount();
			host.remove();
		},
	};
}
