# Three visual directions for review

All three are proposals. [Open the comparison gallery](index.html), switch between analysis/dashboard/assistant and desktop/mobile, then open a live prototype or full-size capture. The same selected source, grouped mean, group sizes, missingness and medication fixture underpin the comparison. No user persona beyond PRODUCT.md is invented.

| Design decision | A — Registre | B — Traverse | C — Cahier |
| --- | --- | --- | --- |
| Workspace model | Parallel analytical register | Guided task progression | Sectioned analytical report |
| Primary navigation | Horizontal top navigation | Persistent 184px desktop rail | Compact horizontal navigation plus document tabs |
| Configuration | Persistent desktop left parameter column; mobile disclosure | Concise question summary, expandable parameters, explicit source/question/result/save stages | Source and calculation strips; compact configuration before the report |
| Result emphasis | Large aligned plot and exact table, stable parallel context | Broad result stage, chart/table switch and outcome actions | Plot/table matrix within a readable document |
| Dashboard | Flat ruled grid of means, counts, completeness and a clearly fixed-scope IQR reference | Asymmetric three-widget arrangement; compact group/source filter band | Three analytical sections plus a reading-context column |
| Assistant | Desktop conversation and medication dossier; dossier first on mobile | Conversation-led response and separate evidence rail; facts repeated visibly in main response on mobile | Consultation record with structured fact table before follow-up composer |
| Visual character | Cobalt, cool paper, disciplined sans typography, fine rules | Forest/sage, warm canvas, softer independent working surfaces | Warm paper, dark ink, restrained oxblood/ochre, compact serif section headings |
| Density | Highest simultaneous configuration visibility; few container layers | More progressive disclosure; nav costs desktop width | Compact report hierarchy; deeper configurations grow vertically |
| Shared controls | Squared restrained controls; native disclosures | Clear primary actions; segmented chart/table navigation | Text-led actions, visible section anchors and inline inspection |

## A — Registre

**Strengths:** settings and effects can be compared without switching context; precise numeric alignment supports repeated analytical work. Strong chart/table equivalence and a medication dossier that puts identification, package, price and provenance together. Flat ruled surfaces resist dashboard-card repetition.

**Weaknesses/tradeoffs:** the parameter column consumes result width and can lengthen complex comparisons. On a phone the exact table intentionally scrolls horizontally, with visible guidance. Bringing the assistant dossier before the transcript favors factual retrieval but may make a continuing conversation feel secondary. Full primary navigation needs grouped destinations rather than cramming all routes into the prototype's three links.

**Implementation complexity: moderate.** Existing controls can be regrouped incrementally; chart sizing still needs a real responsive layer. High-risk work is preserving dirty state when replacing local tabs/panes and keeping advanced definitions discoverable. No analytical or API change is required.

## B — Traverse

**Strengths:** the route shell scales most naturally to datasets, saved analyses, dashboards and permission-dependent administration. The Source → Question → Result → Save sequence provides an understandable handoff from import to result. A collapsed summary reduces first-use cognitive load while leaving a broad plot and exact table. Conversation and evidence retain distinct purposes in the assistant.

**Weaknesses/tradeoffs:** frequent expert adjustments take an extra disclosure. The desktop rail costs 184px; it becomes a compact labeled navigation band on smaller screens. Independent widget surfaces must remain tied to genuine widget boundaries rather than spreading to every sub-section. The mobile assistant repeats core facts before the lower evidence panel so provenance remains available without forcing a jump.

**Implementation complexity: moderate–high.** Task stages and focus/dirty-state coordination need careful integration. Stage labels must not become new saved entities or automatic requests; all existing deep links and access boundaries must survive. This is an organizational change, not merely a palette change.

## C — Cahier

**Strengths:** the most distinct visual identity; analytical work reads as an attributed record rather than a card dashboard. Method/source context sits naturally beside results. The compact serif/sans contrast separates interpretation from data without oversized headings. The assistant's consultation record prioritizes exactly the selected medication and recorded facts.

**Weaknesses/tradeoffs:** long advanced configurations may create vertical depth. Section anchors and compact summaries need real-user checks to avoid hiding the next action below the fold. Report styling must still accommodate independently editable/resizable dashboard widgets and mixed charts, rather than impose a single document narrative on user-created layouts. The serif face needs testing with long French labels and font substitution on non-Windows devices.

**Implementation complexity: moderate–high.** Section navigation is straightforward; reconciling report composition with arbitrary dashboard arrangements is the largest design constraint. The visual system should style the existing grid, not replace widget geometry semantics. No new export/report feature is proposed.

## Recommendation to consider — no selection made

**Traverse is the strongest starting candidate for the coherent import-to-result workspace**, because its navigation can cover the complete application and its progression makes the next action explicit. Registre is stronger when simultaneous expert configuration is the main criterion; Cahier offers the clearest departure from generic dashboard styling and an especially effective medication record. Choose based on the operating model as well as appearance. A requested combination should be made into one revised coherent proposal before adoption; silently mixing all three would dilute the decision.

## Comparison boundaries

The three required screens in each direction are actual rendered compositions. They are representative, not complete replacements for every production route. Dashboard defaults differ slightly in supporting presentation: A includes an explicitly fixed whole-version IQR reference; B/C prioritize the three common means/counts/missingness views. All three map the complete IQR capability in the blueprint. Local analysis presets differ (A/C mean/sum, B mean/count) to demonstrate controls; the starting comparison is the same grouped mean.

The candidate token/component specs are `direction-{a,b,c}-system.md` and `.json`; their `?view=system` screens show controls and states. No candidate overwrites DESIGN.md, no font downloads/dependencies are introduced, and no future landing-page build default is selected.
