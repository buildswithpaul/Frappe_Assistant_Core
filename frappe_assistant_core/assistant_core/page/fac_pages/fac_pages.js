// Shows a FAC Page record at /app/fac-pages/<name>: a published page inside a shadow root with
// the mockup kit, a draft inside a sandboxed iframe that runs no code.
(function () {
	// Desk's build version (v15 and v16 set it in the page template), so a rebuilt kit is refetched.
	const KIT_CSS_URL = `/assets/frappe_assistant_core/css/mockup_kit.css?v=${window._version_number || ""}`;
	// fac.chart, built from the chat's pageCharts module (vite.pagecharts.config.js).
	const CHARTS_URL = `/assets/frappe_assistant_core/js/fac_page_charts.js?v=${window._version_number || ""}`;
	let charts_loaded = null;
	// The page's box: its style and its script's elements paint inside it and nowhere else, so a
	// fixed element cannot cover the review bar or Desk. Paint containment makes the box the
	// containing block of fixed elements and clips them. It is set on a wrapper, outside the shadow
	// host, where the page's own :host rules cannot undo it. Desk already clips a page sideways at
	// its scroller, and clip, unlike auto, keeps the page's sticky headers sticking to it.
	const PAGE_FRAME_STYLE = "contain: layout paint; isolation: isolate; overflow: clip;";
	// The fac handed to the shown page's script, and how to dispose the charts it drew.
	let shown = null;

	// fac_page_draft_srcdoc and fac_page_draft_frame, inlined by render_include on page load.
	// {% include "frappe_assistant_core/assistant_core/page/fac_pages/fac_page_draft.js" %}

	// fac_page_script_review, fac_page_approve_script and fac_page_line_diff, inlined the same way.
	// {% include "frappe_assistant_core/assistant_core/page/fac_pages/fac_page_approval.js" %}

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
		dispose_shown_charts();
		page.set_title(data.title);
		// Only a page that says it is not a draft runs, so a response missing the flag fails closed.
		if (data.draft !== false) {
			render_draft(page, data, is_latest);
			return;
		}
		page.main.empty();
		// A personal page's script runs once the user has seen it: see fac_page_approval.js.
		if (!fac_page_needs_review(data)) {
			render_published(page, data, is_latest, { run_script: true });
			return;
		}
		fac_page_script_review(frappe.session.user, name, data).then((review) => {
			if (!is_latest()) return;
			const run = () =>
				fac_page_approve_script(frappe.session.user, name, data.script).then(() => {
					if (!is_latest()) return;
					dispose_shown_charts();
					render_published(page, data, is_latest, { run_script: true });
				});
			render_published(page, data, is_latest, {
				run_script: !review,
				review_bar: review && make_review_bar(review, data.script, run),
			});
		});
	}

	// The page as get_page sent it; without run_script, its html and style only, under review_bar.
	function render_published(page, data, is_latest, { run_script, review_bar }) {
		const script = run_script ? data.script || "" : "";
		const html = run_script ? data.html || "" : strip_inline_code(data.html || "");
		// Only a script that names fac can draw a chart, so only such a page pays for the bundle.
		const ready = /\bfac\b/.test(script) ? load_charts() : Promise.resolve();
		ready.then(() => {
			if (!is_latest()) return;
			shown = make_fac();
			const frame = document.createElement("div");
			frame.className = "fac-page-frame";
			frame.style.cssText = PAGE_FRAME_STYLE;
			const host = document.createElement("div");
			frame.append(host);
			page.main.empty();
			if (review_bar) page.main.append(review_bar);
			page.main.append(frame);
			// @import must lead the stylesheet; the page's own style follows so it can override the kit.
			const css = `@import url("${KIT_CSS_URL}");\n${data.style || ""}`;
			frappe.create_shadow_element(
				host,
				`<div class="fac-page-root">${html}</div>`,
				css,
				with_fac(script)
			);
		});
	}

	// get_page already serves a personal page's html through an allowlist; while its script is held,
	// this keeps only allowlisted tags and attributes here as well, so nothing in the html runs
	// before Run new version. Forms and buttons stay, because the page's script may wire them.
	const HELD_TAGS = new Set(
		(
			"a abbr article aside b blockquote br button caption code col colgroup dd del details div dl dt " +
			"em fieldset figcaption figure footer form h1 h2 h3 h4 h5 h6 header hr i img input ins kbd label " +
			"legend li main mark meter nav ol optgroup option p pre progress q s section select small span " +
			"strong sub summary sup table tbody td textarea tfoot th thead time tr u ul " +
			"svg g path circle ellipse line polyline polygon rect text tspan defs lineargradient " +
			"radialgradient stop title desc"
		).split(" ")
	);
	const HELD_ATTRIBUTES = new Set(
		(
			"class id style title role name type value placeholder for colspan rowspan href src alt width " +
			"height checked disabled selected readonly required multiple min max step rows cols maxlength " +
			"open datetime target rel action method " +
			"viewbox xmlns d cx cy r rx ry x y x1 y1 x2 y2 points fill stroke stroke-width " +
			"stroke-linecap stroke-linejoin transform opacity fill-opacity offset stop-color " +
			"text-anchor font-size font-weight dominant-baseline gradientunits"
		).split(" ")
	);
	const URL_ATTRIBUTES = new Set(["href", "src", "action"]);
	// javascript: runs code, and data: can carry a document that does.
	const CODE_SCHEMES = /^(?:javascript|vbscript|data):/;

	function strip_inline_code(html) {
		const template = document.createElement("template");
		template.innerHTML = html;
		for (const el of template.content.querySelectorAll("*")) {
			if (!HELD_TAGS.has(el.localName.toLowerCase())) {
				el.remove();
				continue;
			}
			for (const { name, value } of [...el.attributes]) {
				const attribute = name.toLowerCase();
				const allowed =
					HELD_ATTRIBUTES.has(attribute) || /^(?:data|aria)-[\w-]+$/.test(attribute);
				// A browser ignores tabs, newlines and other control characters in a URL's scheme.
				const scheme = value.replace(/[\u0000-\u0020]/g, "").toLowerCase();
				if (!allowed || (URL_ATTRIBUTES.has(attribute) && CODE_SCHEMES.test(scheme))) {
					el.removeAttribute(name);
				}
			}
		}
		return template.innerHTML;
	}

	// Once per Desk session. frappe.require cannot take the ?v= URL (it reads the extension after
	// the "?"), so a plain script tag loads it. A failed load is retried on the next show; the page
	// still renders, and a script that calls fac.chart fails as it would in the chat panel.
	function load_charts() {
		if (!charts_loaded) {
			charts_loaded = new Promise((resolve) => {
				const script = document.createElement("script");
				script.src = CHARTS_URL;
				script.onload = resolve;
				script.onerror = () => {
					charts_loaded = null;
					resolve();
				};
				document.head.appendChild(script);
			});
		}
		return charts_loaded;
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
		fetch(KIT_CSS_URL)
			.then((r) => (r.ok ? r.text() : ""))
			.catch(() => "")
			.then((kit_css) => {
				if (!is_latest()) return;
				page.main
					.empty()
					.append(
						$('<p class="text-muted"></p>').text(__("Draft. Scripts run once the page is published.")),
						fac_page_draft_frame({ html: data.html, style: data.style, kit_css })
					);
			});
	}

	// What the chat panel's PageCodeReview shows: why the script waits, View changes and Run new version.
	function make_review_bar(review, script, run) {
		const bar = document.createElement("div");
		bar.className = "fac-page-review alert alert-warning";
		bar.title = __("Until you run it, Download PDF and FACO's screenshots show the page without this code.");
		const message = document.createElement("span");
		message.className = "fac-page-review-message";
		message.textContent =
			review.state === "first" ? __("This page has code FACO wrote.") : __("FACO changed this page's code.");
		const toggle = make_button(__("View changes"), "btn btn-default btn-xs fac-page-review-toggle");
		const run_button = make_button(__("Run new version"), "btn btn-primary btn-xs fac-page-review-run");
		const diff = document.createElement("pre");
		diff.className = "fac-page-review-diff";
		diff.hidden = true;
		diff.style.cssText = "max-height:40vh;overflow:auto;margin:8px 0 0;";
		toggle.addEventListener("click", () => {
			// Built on first look: most opens are a Run new version without one.
			if (!diff.childElementCount) fill_diff(diff, review.approved, script);
			diff.hidden = !diff.hidden;
			toggle.textContent = diff.hidden ? __("View changes") : __("Hide changes");
		});
		run_button.addEventListener("click", () => {
			run_button.disabled = true;
			run();
		});
		bar.append(message, " ", toggle, " ", run_button, diff);
		return bar;
	}

	function fill_diff(diff, approved, script) {
		const marks = { same: " ", removed: "-", added: "+" };
		const colours = { same: "", removed: "var(--red-600)", added: "var(--green-600)" };
		for (const line of fac_page_line_diff(approved, script)) {
			const row = document.createElement("span");
			row.className = `fac-page-review-line is-${line.type}`;
			row.style.cssText = `display:block;white-space:pre;color:${colours[line.type]};`;
			row.textContent = `${marks[line.type]} ${line.text}`;
			diff.append(row);
		}
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
