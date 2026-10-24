// Shows a FAC Page record at /app/fac-pages/<slug>, inside a shadow root with the mockup kit.
(function () {
	const KIT_CSS_URL = "/assets/frappe_assistant_core/css/mockup_kit.css";

	frappe.pages["fac-pages"].on_page_load = function (wrapper) {
		const page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __("FAC Page"),
			single_column: true,
		});
		wrapper.fac_page = { page, slug: undefined };
	};

	frappe.pages["fac-pages"].on_page_show = function (wrapper) {
		const state = wrapper.fac_page;
		const slug = frappe.get_route()[1] || null;
		if (slug === state.slug) return;
		state.slug = slug;

		if (!slug) {
			state.page.set_title(__("FAC Page"));
			show_message(state.page, __("Pick a page to show."));
			return;
		}

		frappe.call({
			method: "frappe_assistant_core.api.fac_page.get_page",
			type: "GET",
			args: { slug },
			callback(r) {
				// The route may have moved on while this request was in flight.
				if (state.slug !== slug) return;
				render(state.page, r.message);
			},
			error() {
				if (state.slug !== slug) return;
				// Forget the slug so the next visit asks again instead of keeping this failure.
				state.slug = undefined;
				show_message(state.page, __("This page could not be shown."));
			},
		});
	};

	function render(page, data) {
		page.set_title(data.title);
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

	function show_message(page, message) {
		page.main.empty().append($('<p class="text-muted"></p>').text(message));
	}
})();
