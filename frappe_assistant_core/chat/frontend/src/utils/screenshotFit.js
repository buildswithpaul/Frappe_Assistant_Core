/**
 * How big a screenshot FACO sends to a model may be, shared by every capture: the page beside the
 * chat (useSpaBrowserTools), a personal page drawn in its frame (pageFrame/capture) and the Desk
 * widget (widget/desk/browserTools).
 *
 * A provider rejects the whole request over one oversized image: a tall page captured at 1.5x came
 * back over 8000 px and Anthropic refused it, ending the turn (Redmine #34698).
 */
import { __ } from "@/utils/i18n";

// Anthropic and Bedrock refuse an image over 8000 px a side. 7680 leaves room for the rounding
// html2canvas and the frame do when they size the canvas.
export const SCREENSHOT_MAX_EDGE_PX = 7680;
// About 8 megapixels. A provider shrinks anything larger before the model reads it (Claude's
// largest tier reads about 3.75 MP), so more pixels only add upload and encode time; a JPEG this
// size also stays well under Bedrock's 3.75 MB per image.
export const SCREENSHOT_MAX_PIXELS = 8_000_000;
// Below half size, 14 px body text comes out at 7 px and can't be read. A page that would need
// less is cropped instead: its top is kept at half size.
export const SCREENSHOT_MIN_SCALE = 0.5;

/**
 * The scale to draw a page at, and how much of its height to keep, so the picture fits.
 *
 * Scaling comes first, so the whole page is shown; the page is cropped only when it would have
 * to shrink past SCREENSHOT_MIN_SCALE.
 *
 * @param {{width: number, height: number, scale: number}} page the page's size in CSS px, and the
 *   scale it would be drawn at with no limit
 * @returns {{scale: number, height: number}} the scale to draw at and the CSS height to keep
 */
export function fitScreenshot({ width, height, scale }) {
	const w = Math.max(1, Number(width) || 1);
	const h = Math.max(1, Number(height) || 1);
	const wanted = Math.max(Number(scale) || 1, 0.01);
	const whole = Math.min(
		wanted,
		SCREENSHOT_MAX_EDGE_PX / w,
		SCREENSHOT_MAX_EDGE_PX / h,
		Math.sqrt(SCREENSHOT_MAX_PIXELS / (w * h)),
	);
	if (whole >= Math.min(wanted, SCREENSHOT_MIN_SCALE)) return { scale: whole, height: h };
	// A page this wide must shrink past the floor anyway; only its height is cut.
	const cropped = Math.min(wanted, SCREENSHOT_MIN_SCALE, SCREENSHOT_MAX_EDGE_PX / w);
	const kept = Math.min(SCREENSHOT_MAX_EDGE_PX / cropped, SCREENSHOT_MAX_PIXELS / (w * cropped * cropped));
	return { scale: cropped, height: Math.max(1, Math.min(h, Math.floor(kept))) };
}

/**
 * What the tool result says about a picture that was scaled or cut, so FACO knows the bottom of
 * the page may be missing. Empty when the picture shows the whole page at the usual scale.
 *
 * @param {{pageWidth: number, pageHeight: number, width: number, height: number, scale: number}} shot
 *   the page's CSS size, the picture's pixel size and the scale it would have had with no limit
 */
export function describeScreenshotFit({ pageWidth, pageHeight, width, height, scale }) {
	if (!(pageWidth > 0 && pageHeight > 0 && width > 0 && height > 0)) return {};
	const drawn = width / pageWidth;
	const keptHeight = Math.min(pageHeight, Math.round(height / drawn));
	// A little either way is canvas rounding, or the copy html2canvas lays out, not a crop.
	const cropped = keptHeight < pageHeight - Math.max(2, pageHeight * 0.01);
	const scaled = drawn < (Number(scale) || 1) - 0.01;
	if (!cropped && !scaled) return {};
	const page = { width: Math.round(pageWidth), height: Math.round(pageHeight) };
	const percent = Math.round(drawn * 100);
	const note = cropped
		? __(
				"The page is {0} px tall, too tall for one picture: it shows only the top {1} px ({2}% of the page), at {3}% size. The rest of the page is not in the picture.",
				[page.height, keptHeight, Math.round((keptHeight / pageHeight) * 100), percent],
		  )
		: __(
				"The page is {0}×{1} px: the picture shows all of it, scaled to {2}% to fit the model's size limit, so small text may be hard to read.",
				[page.width, page.height, percent],
		  );
	return {
		scaled,
		cropped,
		original_size: page,
		...(cropped ? { kept_height: keptHeight } : {}),
		size_note: note,
	};
}
