// Shows a FAC Page record at /app/fac-pages/<name>: a Shared page inside a shadow root with the
// mockup kit, a personal page ("Only me") inside a sandboxed frame that reads as the user and asks
// before a change, and a draft inside a sandboxed iframe that runs no code.
(function () {
	// Desk's build version (v15 and v16 set it in the page template), so a rebuilt kit is refetched.
	const KIT_CSS_URL = `/assets/frappe_assistant_core/css/mockup_kit.css?v=${window._version_number || ""}`;
	// fac.chart, built from the chat's pageCharts module (vite.pagecharts.config.js).
	const CHARTS_URL = `/assets/frappe_assistant_core/js/fac_page_charts.js?v=${window._version_number || ""}`;
	// A personal page's frame and bridge, built from the chat's pageFrameHost module
	// (vite.pageframehost.config.js).
	const FRAME_HOST_URL = `/assets/frappe_assistant_core/js/fac_page_frame_host.js?v=${window._version_number || ""}`;
	// The page's box: its style and its script's elements paint inside it and nowhere else, so a
	// fixed element cannot cover Desk. Paint containment makes the box the
	// containing block of fixed elements and clips them. It is set on a wrapper, outside the shadow
	// host, where the page's own :host rules cannot undo it. Desk already clips a page sideways at
	// its scroller, and clip, unlike auto, keeps the page's sticky headers sticking to it.
	const PAGE_FRAME_STYLE = "contain: layout paint; isolation: isolate; overflow: clip;";
	// The fac handed to the shown page's script, and how to dispose the charts it drew.
	let shown = null;
	// The personal page's frame shown, disposed when the user moves on.
	let shown_frame = null;

	// fac_page_draft_srcdoc and fac_page_draft_frame, inlined by render_include on page load.
	// {% include "frappe_assistant_core/assistant_core/page/fac_pages/fac_page_draft.js" %}

	frappe.pages["fac-pages"].on_page_load = function (wrapper) {
		const page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __("FAC Page"),
			single_column: true,
		});
		wrapper.fac_page = { page, request: 0 };
	};

	// Fetch on every show, so an edited page is current when the user comes back to it.
	frappe.pages["fac-pages"].on_page_show = function (wrapper) {
		const state = wrapper.fac_page;
		const request = ++state.request;
		const slug = frappe.get_route()[1];

		if (!slug) {
			state.page.set_title(__("FAC Page"));
			show_message(state.page, __("Pick a page to show."));
			return;
		}

		// A later show may start another request; only the latest one may draw.
		const is_latest = () => request === state.request;
		frappe.call({
			method: "frappe_assistant_core.api.fac_page.get_page",
			type: "GET",
			args: { slug },
			callback(r) {
				if (is_latest()) render(state.page, slug, r.message, is_latest);
			},
			error() {
				if (is_latest()) show_message(state.page, __("This page could not be shown."));
			},
		});
	};

	function render(page, name, data, is_latest) {
		dispose_shown();
		page.set_title(data.title);
		// Only a page that says it is not a draft runs, so a response missing the flag fails closed.
		if (data.draft !== false) {
			render_draft(page, data, is_latest);
			return;
		}
		page.main.empty();
		// Only a page that says it is Shared runs in Desk itself; any other runs in the frame.
		if (data.visibility === "Shared") render_shared(page, data, is_latest);
		else render_personal(page, data, is_latest);
	}

	// A Shared page, published through the go-live card that showed its code.
	function render_shared(page, data, is_latest) {
		const script = data.script || "";
		// Only a script that names fac can draw a chart, so only such a page pays for the bundle.
		const ready = /\bfac\b/.test(script) ? load_script(CHARTS_URL, "charts") : Promise.resolve();
		ready.then(() => {
			if (!is_latest()) return;
			shown = make_fac();
			const frame = document.createElement("div");
			frame.className = "fac-page-frame";
			frame.style.cssText = PAGE_FRAME_STYLE;
			const host = document.createElement("div");
			frame.append(host);
			page.main.empty().append(frame);
			// @import must lead the stylesheet; the page's own style follows so it can override the kit.
			const css = `@import url("${KIT_CSS_URL}");\n${data.style || ""}`;
			frappe.create_shadow_element(
				host,
				`<div class="fac-page-root">${data.html || ""}</div>`,
				css,
				with_fac(script)
			);
		});
	}

	// A personal page runs at once, in a frame with no login of its own: see pageFrameHost.js.
	function render_personal(page, data, is_latest) {
		Promise.all([load_script(FRAME_HOST_URL, "frame host"), load_kit()]).then(([, kit_css]) => {
			if (!is_latest()) return;
			const host = window.fac_page_frame_host;
			if (!host) {
				show_message(page, __("This page could not be shown."));
				return;
			}
			const prompts = document.createElement("div");
			prompts.className = "fac-page-write-prompts";
			const box = document.createElement("div");
			box.className = "fac-page-frame";
			box.style.cssText = PAGE_FRAME_STYLE;
			shown_frame = host.createPageFrame({
				page: data,
				kitCss: kit_css,
				user: frappe.session.user,
				version: window._version_number || "",
				transport: host.fetchTransport(() => frappe.csrf_token),
				askWrite: (description) => ask_write(prompts, description),
				onHeight: (height) => (shown_frame.element.style.height = `${Math.max(height, 200)}px`),
			});
			shown_frame.element.style.cssText = "display:block;width:100%;height:480px;border:0;";
			box.append(shown_frame.element);
			page.main.empty().append(prompts, box);
		});
	}

	// One change at a time, in plain words; the description quotes the page, so it is text only.
	// Changes still waiting when the user moves on are refused.
	let prompt_chain = Promise.resolve();
	let open_prompts = [];
	function ask_write(prompts, description) {
		const answer = prompt_chain.then(() => show_prompt(prompts, description));
		prompt_chain = answer.catch(() => {});
		return answer;
	}

	function show_prompt(prompts, description) {
		return new Promise((resolve) => {
			if (!prompts.isConnected) return resolve(false);
			const bar = document.createElement("div");
			bar.className = "fac-page-write-prompt alert alert-warning";
			bar.setAttribute("role", "alertdialog");
			const message = document.createElement("span");
			message.className = "fac-page-write-message";
			message.textContent = description;
			const deny = make_button(__("Don't allow"), "btn btn-default btn-xs fac-page-write-deny");
			const allow = make_button(__("Allow"), "btn btn-primary btn-xs fac-page-write-allow");
			const decide = (allowed) => {
				bar.remove();
				open_prompts = open_prompts.filter((open) => open !== decide);
				resolve(allowed);
			};
			open_prompts.push(decide);
			deny.addEventListener("click", () => decide(false));
			allow.addEventListener("click", () => decide(true));
			bar.append(message, " ", deny, " ", allow);
			prompts.append(bar);
			// A long page may be scrolled past the prompt; bring it into view.
			bar.scrollIntoView({ block: "nearest" });
		});
	}

	function dispose_shown() {
		dispose_shown_charts();
		open_prompts.forEach((decide) => decide(false));
		prompt_chain = Promise.resolve();
		if (shown_frame) shown_frame.dispose();
		shown_frame = null;
	}

	function load_kit() {
		return fetch(KIT_CSS_URL)
			.then((r) => (r.ok ? r.text() : ""))
			.catch(() => "");
	}

	// Once per Desk session each. frappe.require cannot take the ?v= URL (it reads the extension
	// after the "?"), so a plain script tag loads it. A failed load is retried on the next show; the
	// page still renders, and a script that calls fac.chart fails as it would in the chat panel.
	const loaded = {};
	function load_script(url, key) {
		if (!loaded[key]) {
			loaded[key] = new Promise((resolve) => {
				const script = document.createElement("script");
				script.src = url;
				script.onload = resolve;
				script.onerror = () => {
					loaded[key] = null;
					resolve();
				};
				document.head.appendChild(script);
			});
		}
		return loaded[key];
	}

	// fac.chart as the chat panel offers it, recording each chart so the next render disposes it.
	function make_fac() {
		const handles = [];
		const fac = {
			chart(el, option) {
				const bundle = window.fac_page_charts;
				if (!bundle) throw new Error(__("Charts could not be loaded"));
				const handle = bundle.chart(el, option);
				handles.push(handle);
				// A chart drawn after the user moved on belongs to a page no longer shown.
				if (!shown || shown.fac !== fac) dispose();
				return handle;
			},
		};
		const dispose = () => handles.splice(0).forEach((handle) => handle.dispose());
		return { fac, dispose };
	}

	function dispose_shown_charts() {
		if (shown) shown.dispose();
		shown = null;
	}

	// create_shadow_element runs the script as a global <script>, which sees no variable of ours,
	// so the fac it gets is read from this Desk page's frappe.pages entry when it starts. The chat
	// panel runs it as new Function("root_element", "frappe", "__", "fac", script), so here it runs
	// as a function of fac as well: the same scoping, and no global named fac.
	function with_fac(script) {
		frappe.pages["fac-pages"].fac = shown.fac;
		return `(function (fac) {\n${script}\n})(frappe.pages["fac-pages"].fac);`;
	}

	// The sandboxed frame cannot load the kit itself (its CSP allows no fetches), so it is inlined.
	function render_draft(page, data, is_latest) {
		// Clear now, so the previous page does not stay on screen while the kit loads.
		page.main.empty();
		load_kit().then((kit_css) => {
			if (!is_latest()) return;
			page.main
				.empty()
				.append(
					$('<p class="text-muted"></p>').text(__("Draft. Scripts run once the page is published.")),
					fac_page_draft_frame({ html: data.html, style: data.style, kit_css })
				);
		});
	}

	function make_button(label, class_name) {
		const button = document.createElement("button");
		button.type = "button";
		button.className = class_name;
		button.textContent = label;
		return button;
	}

	function show_message(page, message) {
		page.main.empty().append($('<p class="text-muted"></p>').text(message));
	}
})();
