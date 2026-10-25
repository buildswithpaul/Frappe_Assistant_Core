import { describeDraftBuilder } from "@/utils/__tests__/facPageDraftCases";
import { fac_page_draft_frame, fac_page_draft_srcdoc } from "./facPageDraft";

describeDraftBuilder("SPA module", { srcdoc: fac_page_draft_srcdoc, frame: fac_page_draft_frame });
