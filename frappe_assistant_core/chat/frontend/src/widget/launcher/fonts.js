import inter400 from "@/assets/fonts/inter-400.woff2?url";
import inter500 from "@/assets/fonts/inter-500.woff2?url";
import inter600 from "@/assets/fonts/inter-600.woff2?url";
import inter700 from "@/assets/fonts/inter-700.woff2?url";
import serif500 from "@/assets/fonts/source-serif-4-500.woff2?url";
import serif600 from "@/assets/fonts/source-serif-4-600.woff2?url";

// Fonts declared inside a shadow root are ignored, so the widget's faces are
// declared on the page under names no Desk rule uses.
const FACES = [
	["FAC Inter", inter400, 400],
	["FAC Inter", inter500, 500],
	["FAC Inter", inter600, 600],
	["FAC Inter", inter700, 700],
	["FAC Source Serif 4", serif500, 500],
	["FAC Source Serif 4", serif600, 600],
];

export function installFontFaces() {
	if (document.getElementById("fac-widget-fonts")) return;
	const style = document.createElement("style");
	style.id = "fac-widget-fonts";
	style.textContent = FACES.map(
		([family, url, weight]) =>
			`@font-face{font-family:"${family}";src:url("${url}") format("woff2");font-weight:${weight};font-style:normal;font-display:swap}`,
	).join("\n");
	document.head.appendChild(style);
}
