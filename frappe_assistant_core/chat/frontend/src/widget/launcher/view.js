import css from "./launcher.css?inline";

const ROBOT = `
	<div class="faco-robot" data-mood="idle">
		<div class="robot-antenna"><div class="robot-antenna-tip"></div></div>
		<div class="robot-arm robot-arm-left"></div>
		<div class="robot-arm robot-arm-right"></div>
		<div class="robot-head"><div class="robot-screen">
			<div class="robot-brow robot-brow-left"></div><div class="robot-brow robot-brow-right"></div>
			<div class="robot-eye robot-eye-left"></div><div class="robot-eye robot-eye-right"></div>
			<div class="robot-mouth"></div>
		</div></div>
		<div class="robot-body"></div>
		<div class="robot-shadow"></div>
	</div>`;

export function createLauncherView(doc) {
	const host = doc.createElement("div");
	host.id = "fac-widget-launcher";
	doc.body.appendChild(host);
	const root = host.attachShadow({ mode: "open" });
	root.innerHTML = `<style>${css}</style>
		<div class="faco-widget">
			<div class="faco-tooltip"><span class="faco-tooltip-icon"></span><span class="faco-tooltip-text"></span></div>
			<button class="faco-toggle-btn" type="button" aria-label="Open assistant">${ROBOT}
				<span class="faco-approval-badge" aria-hidden="true"></span>
			</button>
		</div>`;
	const widgetEl = root.querySelector(".faco-widget");
	const button = root.querySelector(".faco-toggle-btn");
	const robot = root.querySelector(".faco-robot");
	let dot = null;
	return {
		host,
		root,
		widgetEl,
		button,
		robot,
		tooltip: root.querySelector(".faco-tooltip"),
		setMood: (mood) => (robot.dataset.mood = mood || "idle"),
		setOpen: (open) => widgetEl.classList.toggle("faco-open", !!open),
		setAttention: (on) => widgetEl.classList.toggle("faco-awaiting-approval", !!on),
		setDot(on) {
			if (on && !dot) {
				dot = doc.createElement("span");
				dot.className = "faco-spotlight-dot";
				dot.setAttribute("aria-hidden", "true");
				button.appendChild(dot);
			} else if (!on && dot) {
				dot.remove();
				dot = null;
			}
		},
		destroy: () => host.remove(),
	};
}
