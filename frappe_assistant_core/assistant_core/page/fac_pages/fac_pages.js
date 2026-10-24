// Shows a FAC Page record at /app/fac-pages/<slug>: a published page inside a shadow root with
// the mockup kit, a draft inside a sandboxed iframe that runs no code.
(function () {
	// Desk's build version (v15 and v16 set it in the page template), so a rebuilt kit is refetched.
	const KIT_CSS_URL = `/assets/frappe_assistant_core/css/mockup_kit.css?v=${window._version_number || ""}`;

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
				if (is_latest()) render(state.page, r.message, is_latest);
			},
			error() {
				if (is_latest()) show_message(state.page, __("This page could not be shown."));
			},
		});
	};

	function render(page, data, is_latest) {
		page.set_title(data.title);
		if (data.draft) {
			render_draft(page, data, is_latest);
			return;
		}
		const host = document.createElement("div");
		page.main.empty().append(host);
		// @import must lead the stylesheet; the page's own style follows so it can override the kit.
		const css = `@import url("${KIT_CSS_URL}");\n${data.style || ""}`;
		frappe.create_shadow_element(
			host,
			`<div class="fac-page-root">${data.html || ""}</div>`,
			css,
			data.script || ""
		);
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

	function show_message(page, message) {
		page.main.empty().append($('<p class="text-muted"></p>').text(message));
	}
})();
