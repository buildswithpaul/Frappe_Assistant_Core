// Shows a FAC Page record at /app/fac-pages/<slug>, inside a shadow root with the mockup kit.
(function () {
	const KIT_CSS_URL = "/assets/frappe_assistant_core/css/mockup_kit.css";

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
				if (is_latest()) render(state.page, r.message);
			},
			error() {
				if (is_latest()) show_message(state.page, __("This page could not be shown."));
			},
		});
	};

	function render(page, data) {
		page.set_title(data.title);
		const host = document.createElement("div");
		page.main.empty();
		// A draft arrives without its script, so the preview runs no code until it is published.
		if (data.draft) {
			page.main.append(
				$('<p class="text-muted"></p>').text(__("Draft. Its script runs once the page is published."))
			);
		}
		page.main.append(host);
		// @import must lead the stylesheet; the page's own style follows so it can override the kit.
		const css = `@import url("${KIT_CSS_URL}");\n${data.style || ""}`;
		frappe.create_shadow_element(
			host,
			`<div class="fac-page-root">${data.html || ""}</div>`,
			css,
			data.script || ""
		);
	}

	function show_message(page, message) {
		page.main.empty().append($('<p class="text-muted"></p>').text(message));
	}
})();
