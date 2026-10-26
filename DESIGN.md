---
name: "Pharma Analyse / Assistant pharmacie — existing frontend"
description: "Descriptive implementation baseline captured on 2026-10-25; not a quality endorsement or redesign direction."
colors:
  primary: "#216b60"
  primary-foreground: "#ffffff"
  background: "#f7f9f6"
  foreground: "#304536"
  secondary: "#eaf0e7"
  secondary-foreground: "#37563c"
  muted: "#edf2e9"
  muted-foreground: "#667565"
  accent: "#edf3e8"
  accent-foreground: "#2d5035"
  border: "#d8e2d5"
  destructive: "#a14731"
  ring: "#4b805a"
  platform-primary: "#17674f"
  platform-background: "#f5f8f7"
  platform-foreground: "#183c34"
  platform-border: "#d8e4df"
  platform-control-border: "#9db7ab"
  platform-button-border: "#a9c4ba"
  platform-muted: "#4d6b61"
  platform-danger: "#9f2929"
  platform-error-background: "#fff0ef"
  platform-focus: "#31806a"
  table-header: "#f0f5f2"
  assistant-heading: "#203e33"
  assistant-emphasis: "#36786e"
  assistant-muted: "#5f6e62"
  assistant-user-bubble: "#e9f0e9"
  assistant-notice-background: "#edf3e9"
  assistant-warning-background: "#faf8ef"
  assistant-warning-foreground: "#765834"
  chart-blue: "#315ca8"
  chart-ochre: "#986515"
  chart-purple: "#854c8f"
  chart-cyan: "#307c86"
  chart-red: "#a33e40"
  chart-olive: "#5f6536"
  chart-slate-purple: "#655e86"
typography:
  body:
    fontFamily: "'Segoe UI', system-ui, -apple-system, BlinkMacSystemFont, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.5
  platform-headline:
    fontSize: "clamp(1.8rem, 4.5vw, 3rem)"
    fontWeight: 700
    lineHeight: 1.15
    letterSpacing: "-0.035em"
  platform-title:
    fontSize: "1.2rem"
    fontWeight: 650
  platform-body:
    fontSize: "16px"
    lineHeight: 1.65
  platform-label:
    fontSize: "0.95rem"
  platform-navigation:
    fontSize: "0.9rem"
  assistant-display:
    fontFamily: "Georgia, 'Times New Roman', serif"
    fontSize: "clamp(38px, 4.3vw, 54px)"
    fontWeight: 400
    lineHeight: 1.15
    letterSpacing: "-1.8px"
  assistant-answer:
    fontSize: "14px"
    lineHeight: 1.85
  assistant-eyebrow:
    fontSize: "10px"
    fontWeight: 650
    letterSpacing: "1.7px"
  table-body:
    fontSize: "0.85rem"
  technical:
    fontFamily: "monospace"
    fontSize: "0.8rem"
rounded:
  sm: "6px"
  md: "8px"
  lg: "12px"
  xl: "18px"
  platform-field: "0.45rem"
  platform-panel: "1rem"
  assistant-example: "13px"
  assistant-medication: "14px"
  assistant-composer: "15px"
spacing:
  tailwind-unit: "0.25rem"
  half-rem: "0.5rem"
  three-quarter-rem: "0.75rem"
  one-rem: "1rem"
  one-and-half-rem: "1.5rem"
  two-rem: "2rem"
  platform-gutter: "1.25rem"
  assistant-card-gap: "12px"
components:
  platform-primary:
    backgroundColor: "{colors.platform-primary}"
    textColor: "{colors.primary-foreground}"
    rounded: "{rounded.md}"
    padding: "0.75rem 1rem"
  platform-button:
    backgroundColor: "{colors.primary-foreground}"
    textColor: "{colors.platform-foreground}"
    rounded: "{rounded.md}"
    padding: "0.65rem 1rem"
  platform-danger:
    backgroundColor: "{colors.platform-danger}"
    textColor: "{colors.primary-foreground}"
    rounded: "{rounded.md}"
  platform-input:
    backgroundColor: "{colors.primary-foreground}"
    textColor: "{colors.platform-foreground}"
    rounded: "{rounded.platform-field}"
    padding: "0.65rem"
  platform-panel:
    backgroundColor: "{colors.primary-foreground}"
    rounded: "{rounded.platform-panel}"
    padding: "clamp(1.2rem, 3vw, 2rem)"
  assistant-send:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.primary-foreground}"
    rounded: "10px"
    size: "39px"
  assistant-medication:
    backgroundColor: "{colors.primary-foreground}"
    rounded: "{rounded.assistant-medication}"
    padding: "23px 24px 19px"
  assistant-composer:
    backgroundColor: "{colors.primary-foreground}"
    rounded: "{rounded.assistant-composer}"
    padding: "12px 12px 12px 17px"
---

# Design Record: Pharma Analyse / Assistant pharmacie

## Overview

This is a descriptive record of the frontend in `apps/web/`, captured on **2026-10-25**. It records implemented values, layout patterns and states. It does not endorse their quality, establish a new creative direction, or make every incidental value a requirement for a future redesign. A separate comprehensive UI/UX critique is pending. Product facts remain in [PRODUCT.md](PRODUCT.md).

There are two related but distinct presentations. The platform uses a pale green-gray page, white bordered panels, green sans-serif headings, native form controls and long vertical task pages. The assistant uses a lighter green-tinted page, a centered serif welcome heading with an italic second line, compact example prompts, message bubbles, source-aware result cards and a bottom composer. Both use rounded rectangles and green accents. Neither has a user-facing theme switch; the root declares a light color scheme, although shared component definitions contain some dark-mode utility variants.

**Key Characteristics:**

- Platform panels and forms define most screen structure; the assistant has its own narrower conversation layout.
- Platform styling is predominantly direct CSS; assistant controls combine shared Tailwind/Radix primitives with direct CSS overrides.
- Most grouping uses borders and pale surfaces; small shadows occur on assistant interaction surfaces and shared dialogs.
- Navigation is a wrapping text-link header, with local tabs and back links inside task pages.
- Type, spacing, corner radii and color values vary by surface. There is no single enforced scale covering the whole application.

### Sources and verification boundary

The primary sources are [global tokens](apps/web/src/app/styles/index.css), [assistant/global CSS](apps/web/src/app/styles/app.css), and the [platform](apps/web/src/app/styles/platform.css), [dataset](apps/web/src/app/styles/datasets.css), [analytics](apps/web/src/app/styles/analytics.css), [dashboard/sharing](apps/web/src/app/styles/dashboards.css) and [administration](apps/web/src/app/styles/administration.css) stylesheets. These were read alongside [route composition](apps/web/src/app/App.tsx), feature markup and [shared UI primitives](apps/web/src/shared/ui/).

Live read-only captures and computed styles cover `/`, `/connexion` and the empty `/assistant` at **1440 × 1000** and **390 × 844** in headless Edge. They are retained locally under `artifacts/design-document/`, including `computed-styles.json`. No form was submitted, account created, hosted inference requested, or application container started/stopped for this record.

Authenticated layouts were inspected through current source and retained CP2–CP5 desktop/mobile captures under `artifacts/platform-cp2/` through `artifacts/platform-cp5/`. Assistant conversation cards were inspected in retained R7 captures under `artifacts/cleanup/r7/` and checked against current markup/CSS. Those older captures are supporting evidence, not fresh authenticated verification: for example, the R7 assistant capture predates the current platform-link strip. These ignored artifacts may be absent in another checkout; source paths above remain the reproducible authority. This pass does not re-certify every interaction or accessibility result.

The frontmatter follows the [DESIGN.md format](https://raw.githubusercontent.com/google-labs-code/design.md/main/docs/spec.md). Its names map extracted values for documentation; they do not introduce CSS tokens into the application. Component entries are partial visual summaries; the prose records cascade and responsive exceptions. No creative metaphor, synthetic color ramp or invented design rule has been added. `.impeccable/design.json` contains companion documentation previews and extensions, not runtime application code.

## Colors

### Primary

The global `primary` is muted teal, used by shared default buttons, the assistant mark and send control. The platform separately hard-codes a darker green, recorded as `platform-primary`, for primary actions, links, selected dataset tabs and most analytical marks. These are separate incumbent values; one does not replace the other.

### Secondary and supporting surfaces

The global `secondary`, `muted` and `accent` families are pale greens with separate text colors. Shared component variants consume them. Assistant message bubbles, notices and warning panels also have direct colors rather than consistently referring to these variables. `assistant-emphasis` colors the italic welcome line.

### Neutral

The shared page/background and text colors differ from the platform shell's `platform-background` and `platform-foreground`. Platform panels and most assistant result cards are white. Platform borders, native-field borders and plain-button borders are distinct shades. Tables have a pale green header row. Muted platform copy and assistant annotations likewise have different values.

### Feedback and focus

- Platform error panels use `platform-danger` text on `platform-error-background`; destructive dataset buttons use the same red as a solid fill.
- Shared destructive buttons/invalid-field utilities use the separate global `destructive` value. Assistant error/recovery blocks use warm cream and brown rather than the platform's red panel treatment. Informational notices use pale green.
- The global focus outline is green (`#277958`, 3px, 4px offset); the platform overrides that hue with `platform-focus`. Shared primitives also define a 3px translucent ring from `ring`. The composer uses its own border and shadow on focus-within. These are different mechanisms, not one unified focus token.

### Data visualization

Bars, lines, histogram bins and scatter points use `platform-primary`. The pie/donut sequence is that green followed by `chart-blue`, `chart-ochre`, `chart-purple`, `chart-cyan`, `chart-red`, `chart-olive` and `chart-slate-purple`, cycling by group index. Legend swatches follow that sequence. Axes use a separate gray-green (`#70877d`); SVG label fill is dark green (`#214e40`). No stable category-to-color mapping is established beyond displayed order.

## Typography

The main stack is **Segoe UI, system-ui, -apple-system, BlinkMacSystemFont, sans-serif**, without a bundled webfont. The assistant welcome display alone uses **Georgia, Times New Roman, serif**, including an italic emphasized line. Technical hashes/identifiers have a monospace treatment. There is no declared modular type ratio.

The table describes roles in the current CSS. Rem-to-pixel examples assume the observed root size of 16px; inherited properties remain inherited rather than becoming new per-role tokens.

| Role | Current size / weight / rhythm | Placement and exceptions |
| --- | --- | --- |
| Base body | `body` frontmatter; regular | Live body computes to 16px with 24px line height. |
| Platform main heading | `platform-headline`; max text width 760px | Computes to 48px at 1440px and 28.8px at 390px. Margin is `.5rem 0 1.5rem`. |
| Platform section heading | `platform-title`; bottom margin `.75rem` | Live h2 line height is 28.8px through inheritance. |
| Platform paragraphs | `platform-body`; maximum width 760px; margin `.8rem 0` | Lead text is `1.15rem`; eyebrows are `.85rem`, weight 650. |
| Platform brand | `1.2rem`, weight 750 | Navigation is `.9rem`; both remain sans-serif. |
| Platform field labels | `platform-label` | Auth/form-card labels add weight 600. General panel labels do not independently set that weight. |
| Tables / captions | Table body `.85rem`; captions `.8rem`; header weight 650 | Cells preserve whitespace and wrap long content. |
| Assistant welcome | `assistant-display` | Wide/tall viewport display reaches 54px. Width, height and later cascade overrides are listed under Layout. |
| Assistant eyebrow | `assistant-eyebrow`, uppercase in content | Mobile uses 8px and 1.4px tracking. |
| Assistant explanatory copy | 14px, line height 1.85 | 12px on mobile; the short-desktop rule uses 13px and 1.7. |
| User message | 14px, line height 1.75 | 13px on mobile. |
| Assistant answer | `assistant-answer` | 13px on mobile. Answers carrying `dir="rtl"` use 17px/1.9 before the later mobile font-size override; this does not localize the surrounding interface. |
| Medication heading / prices | Heading 19px/650; unit price 23px/600; total 22px/600 | Heading becomes 17px and prices 19px on mobile. Monetary totals use tabular numerals and negative letter spacing. |
| Assistant metadata | Mostly 10–12px | Final mobile overrides restore source/date/price-label, limitations and composer metadata to 10px, example-question text to 11px. Earlier 8–9px declarations are not the final values for those selectors. |
| Analytical KPI / admin total | KPI `1.65rem`/700; admin total `1.8rem`/650 | Platform paragraph rules still affect KPI paragraph margins and line height. |
| Technical text | `technical` | Used for source hashes and administrative identifiers. |

## Layout

### Platform shell and page structure

- The shell fills at least `100svh`. Its header is a non-sticky flex row: brand on the left, wrapping text links/actions on the right, white background and a bottom border. Header inline padding uses `max(1.2rem, calc((100vw - 1120px)/2))`.
- Main content is centered with an outer maximum width of **1040px**, inclusive of padding under the global border-box reset. Inline padding is **1.25rem**. Block padding is `clamp(1.5rem, 5vw, 4rem)` before the mobile override. At 1440px, the content starts 220px from the viewport edge and the inner width is 1000px.
- Most pages are a heading/intro followed by stacked white panels. Panels use fluid padding `clamp(1.2rem, 3vw, 2rem)` and block margins `1.3rem`. Auth/form cards have a **550px** maximum outer width. Login/registration cards specifically use automatic inline margins; profile/import forms do not all inherit that centering behavior.
- Action rows wrap with a `1.5rem` gap and margins `1.8rem 0 2.4rem`. Data and analysis lists use repeated panels with title links, metadata and page controls, rather than an application sidebar.

### Forms, exploration and analytical pages

General control grids use `repeat(auto-fit, minmax(190px, 1fr))`, a `1rem` gap and bottom alignment. Column-definition editors use a separate **210px** minimum. Metadata fields stop at **650px**. Import steps are a wrapping text list, followed by configuration, preview, column conventions, metadata and validation/publication panels; the step labels do not hide the other sections as a paged wizard.

Exploration places search, filter builder, active-filter chips, sort/page-size controls and the data table in a vertical flow. Table wrappers scroll on overflow. Cells have **100px** minimum and **330px** maximum widths, preserved whitespace, arbitrary-word wrapping and top alignment. Pagination is a wrapping row with space-between alignment. Analytical pages similarly stack sources, calculation controls, templates, results and explicit save sections, with bordered nested fieldsets.

KPI cards use auto-fitting columns with a **180px** minimum; admin summary cards use a **170px** minimum. SVG charts expand to container width with automatic height. Most analytical charts use a `900 × 390` viewBox; pie/donut uses `500 × 300`, and bar height depends on group count. Bar-chart scroll regions have a **600px** maximum height. Tables remain available alongside charts.

### Dashboard and sharing layout

The desktop dashboard is a **12-column** grid with **80px** automatic rows and a **1rem** gap. Widget widths are configured as spans of **4, 6 or 12** columns; heights use **3–12** grid rows. Widgets have a fixed header region and an independently scrolling body. Nested platform result panels remove their outer border/margins and reduce padding inside widgets. Edit mode exposes configuration, duplication, order and size controls.

Sharing is an inline panel within the resource screen. Its email form wraps; its expanding label has a minimum of `min(100%, 240px)`. Recipient lists wrap long content. Original-owner authorization reviews can use a scrolling configuration region with a **24rem** maximum height. These are not separate full-screen sharing dialogs.

### Assistant layout

The assistant shell is a `100dvh` flex column. A centered strip links to the platform above the assistant header. The desktop header inner container is **1264px** maximum, **88px** high with **48px** inline padding. The conversation has an **828px** maximum outer width and **28px** inline padding, yielding **772px** inner width at desktop. The composer inner container also stops at **772px**.

The welcome state is centered, with three equal example cards separated by **12px**. The header, large welcome block and composer form the page's major vertical regions. The composer is in normal flow in the welcome state; in a conversation it is sticky at bottom with z-index 10. Its textarea grows from **52px** to **148px** and has its own borderless styling inside the outer composer surface.

The message list is vertical with a **31px** gap. User bubbles align right with an **84%** maximum width; assistant responses use the full conversation width, with a **32px** content inset after the assistant label. Medication/pharmacy results and candidate lists are vertically stacked. A floating “Derniers messages” control appears above the composer when the conversation is scrolled away from the end.

### Responsive rules and cascade order

| Condition | Implemented effect |
| --- | --- |
| Body minimum | `min-width: 320px`; widths below that are not a separately designed layout. |
| Platform at `max-width: 650px` | Header becomes a left-aligned column; nav links still wrap rather than becoming a drawer. Main top padding becomes `1.5rem`. Form/column-editor grids and KPI grids become one column. Analysis fieldset/chart padding shrinks. Tables retain their scroll containers. |
| Dashboard at `max-width: 899px` | Grid becomes a vertical flex stack; widgets have at least `18rem` height and body height is capped at `42rem`. Pointer drag/resize handles are hidden; explicit order/size buttons remain. Pointer-gesture code activates from 900px. |
| Assistant at `min-width: 1500px` | Header inner maximum grows to 1400px; welcome top padding becomes `13vh`, unless a later height rule overrides it. |
| Assistant at `max-width: 800px` | Header becomes 76px high with 25px inline padding; context tagline disappears; welcome h1 becomes 46px and top padding 65px. |
| Assistant at `max-width: 560px` | Header becomes 70px high with 18px padding; mark shrinks to 32px, second word of the brand hides, and the new-conversation button shrinks. Welcome h1 becomes 37px with -1.5px tracking. Examples stack as short horizontal cards; conversation padding becomes 18px. User bubbles expand to 90%; response inset disappears. Composer outer padding becomes `12px 15px 15px`; send control shrinks from 39px to 35px. Refinement select/button stacks vertically. |
| Assistant at `min-width: 561px` and `max-height: 800px` | A later short-viewport rule uses a 72px header, 42px welcome h1, compact vertical margins and 112px-minimum example cards. This wins over overlapping earlier width rules. |
| Later assistant mobile corrections | Composer metadata, limitations, source/date/price labels and welcome footnote end at 10px; example-question text ends at 11px. The character-count/Enter hint remains hidden on mobile. |
| Shared utilities | Tailwind defaults include `sm: 40rem` and `md: 48rem`; the Radix dialog changes alignment/footer at `sm`. These differ from the direct-CSS 560/650/800/899px thresholds. |
| Reduced motion | A global media rule disables CSS animations, transitions and smooth scrolling with `!important`; the chat scroll action also checks the preference. |

### Spacing vocabulary

The frontmatter lists repeated observed spacings and Tailwind's quarter-rem unit, not a newly standardized scale. Platform spacing is mostly fractional rem values; assistant spacing largely uses individual pixel values. Examples include `1rem` grid gaps, `.65rem` field padding, `.8rem` feedback padding and 12/18/20/24px assistant insets. Irregular values and surface-specific adjustments remain part of the baseline.

## Elevation & Depth

Platform pages, panels, form cards, tables and dashboards mostly use one-pixel borders, white surfaces and pale headers without shadows. The assistant adds small, low-opacity shadows to the composer, prompt hover and jump control. The reset dialog uses the shared library's larger shadow over a black half-opacity overlay. There are no implemented gradients, backdrop blur or glass layers in these surfaces.

| Source role | Current shadow / layer |
| --- | --- |
| Prompt-card hover | `0 3px 9px #15392108` with a border/background change. |
| Composer at rest | `0 3px 16px #244d3110`. |
| Composer focus-within | `0 0 0 2px #3c785011`, with border `#6b9577`; it replaces the resting shadow. |
| Jump-to-latest control | `0 2px 8px #254b2210`. |
| Shared outline button / textarea defaults | Tailwind shadow-xs: `0 1px 2px 0 rgb(0 0 0 / 0.05)`; chat-specific controls can override it to none. |
| Shared reset dialog | Tailwind shadow-lg: `0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)`. Content and overlay use z-index 50. |
| Keyboard skip link | Fixed at top-left with z-index 100, revealed on focus. |

## Shapes

The shared theme declares `sm/md/lg/xl` radii in the frontmatter, but direct CSS does not uniformly consume them. Platform buttons use half-rem corners, fields use `.45rem`, nested fieldsets generally `.6rem`, and outer panels `1rem`. Tables and charts have smaller half-rem corners. Dashboard widgets use 12px corners and clipped overflow.

The assistant uses 13px prompt cards, 14px medication cards, 12px pharmacy cards, an 11px candidate row and a 15px composer. The user bubble has asymmetric **16px 16px 4px 16px** corners. Marks, send controls, badges and the jump button have their own values. Mobile reduces several card radii rather than rescaling one common token. Dose badges override the shared pill shape with 6px corners; general Badge primitives retain a full-pill default.

Most controls have thin solid borders; highlighted information is expressed through fill, text and separators. Lucide line icons supply the assistant's cross mark, pill, map pin, phone, arrows, status and action symbols. There is no photographic or illustration asset system in the inspected screens.

## Components

### Buttons and action links

**Platform:** plain native buttons have a white fill, green-gray outline, half-rem radius and inherited typography. Primary actions may be links or buttons; both use the same solid-green visual treatment. Dataset destructive actions use the separate solid red. Disabled platform buttons have `.6` opacity and a wait cursor. The platform CSS does not define a general custom hover-color change for plain/primary buttons; do not infer one from assistant utilities.

**Assistant/shared:** `Button` defines default, destructive, outline, secondary, ghost and link variants. Its base is inline flex, 14px medium text, gap 8px and shared-md rounding. Default size is 36px high, with compact 24/32px and large 40px options plus icon sizes. Utility hover states change fill opacity/accent; focus uses a ring, and disabled state prevents pointer interaction with half opacity. Not every defined variant is necessarily displayed in every workflow.

Assistant CSS overrides particular shared controls: the new-conversation outline is 38px high (33px mobile) with no shadow; candidate choices are full-width multi-line rows with separate label/price areas; send is a square teal icon button with a pale disabled fill; “Présentations suivantes” is a small ghost action. Example-card hover changes border, background and shadow over **140ms**.

### Panels, cards and repeated lists

Platform outer panels use the frontmatter panel radius/padding and a thin platform border. Auth cards cap their width and center only through the auth-specific class. Dataset/analysis/dashboard lists repeat those panels, with the title as the main link and ownership/version/status in paragraph text. Empty states use the same panel vocabulary. Deletion and access reviews are commonly inline sections with confirmation controls.

Assistant medication cards arrange title/icon and dosage badge in a row, then substance, presentation/form, a separated price block and source/date footer. Optional quantity totals align opposite the unit price. Pharmacy cards use address and contact rows, a telephone link when available, and a source/date line. Differences and limitations appear as smaller text or a pale warning inset, not a decorative side stripe.

### Fields and selection controls

Platform inputs, selects and textareas use native elements with a white fill, one-pixel control border, `.45rem` corners and `.65rem` padding. Although the earlier form-card input rule declares `.75rem`, the later dataset stylesheet's equally specific main-input rule wins: live auth inputs compute to **10.4px** padding at a 16px root. Auth labels/inputs inherit 600 weight. Textareas have a 65px minimum height and vertical resize. Checkboxes are native; the dataset checkbox styling sets a **1.1rem** box and horizontal label layout. Select arrows and date pickers use browser-native presentation.

Field groups use visible labels, optional help text, legends and explicit action buttons. Disabled fieldsets lock related controls. Error feedback generally appears at section/form level; native required/type validation and shared `aria-invalid` utilities are also present. The chat composer removes its inner textarea border/ring and puts focus feedback on its enclosing surface.

### Chips, badges and local selectors

Active dataset filters are small outlined wrapping rectangles (`.4rem` radius and padding, `.85rem` text) with inline removal buttons. They are distinct from dosage badges and the shared Badge primitive. Dataset view tabs are wrapping native buttons; the active button has solid-green fill and white text. Administrative section tabs are links, with the active item bold and underlined. These patterns do not share one tab component implementation.

### Navigation

- **Global platform header:** brand links home. Visitor links are Assistant pharmacie, Connexion and Créer un compte. Signed-in navigation adds Mon espace, Mes données, Mes analyses, Mes tableaux de bord, Mon profil, optional Administration and a logout button. Links wrap on narrow widths. The global header does not set an active-page marker/style for its current route.
- **Local navigation:** task pages use text back links; dataset views use button tabs; administration uses URL-linked section tabs. The version selector is a native select. Pagination uses preceding/following buttons with a page or result count between them.
- **Routing:** React Router defines separate datasets, analyses, dashboards, profile and administration paths. Dataset version/view selection and admin section selection use query parameters. Protected destinations redirect to login and preserve the supported local destination. Unknown routes show an in-shell heading and return-home link. The platform scrolls to top when its pathname changes.
- **Assistant:** a separate top strip links to Pharma Analyse · Accueil and Mon espace. Its own header links the brand to the conversation anchor and offers Nouvelle conversation. A skip link targets the conversation; the platform's skip link targets its main content.

### Tables, charts and dashboard widgets

Data tables use collapsed borders, a pale header, left-aligned 650-weight header cells and `.6rem .75rem` cell padding. Missing values use italic muted text. Original/interpreted cell views are explicit. Scrollable wrappers are keyboard-focusable and labeled. Hashes and long identifiers wrap instead of defining wider page columns.

Chart figures are white bordered containers with a caption, SVG description and exact tabular results. Pie/donut has wrapping color legends with one-rem swatches; scatter uses semi-transparent green dots; bar labels truncate visually with full text in SVG titles. Hover information uses native SVG titles rather than a custom tooltip component. Result conventions and additional details use expandable native details sections.

Dashboard widgets have a pale header, clipped rounded outline and scrolling result body. Editing exposes explicit buttons plus desktop pointer/keyboard handles. Handles have grab/grabbing cursors, disabled text selection and `touch-action: none`; direction keys support their implemented order/size controls. Mobile uses stacked cards with the handles hidden. Widget loading and errors are independent text/feedback regions, and stale results are cleared rather than displayed under changed settings.

### Feedback, disclosure and confirmation

Platform loading and operation states are mostly inline `role="status"` text; errors use `role="alert"` and the red-tinted block. Some error states offer reload/retry controls. Unsaved changes, successful saves, suspension and read-only ownership are communicated in text near the heading or relevant section. There is no common toast or skeleton component in the inspected workflows.

The assistant has in-flow waiting text/spinner/dots, green notices, cream recovery warnings, cooldown timers, and explicit edit/retry/verification actions. Source details use Radix Collapsible; medication/pharmacy source links and collection dates are part of the result card hierarchy. French interface labels coexist with automatic text direction on the question field and answer content.

Resetting the assistant uses a Radix AlertDialog with centered fixed content, a half-black overlay, 24px padding, shared-lg corners and a close fit to the viewport (`calc(100% - 2rem)`, default desktop cap 32rem). Its small variant caps at 20rem. Header text is centered below the shared `sm` breakpoint and left-aligned above it; footer actions change from reversed column to right-aligned row. Platform confirmations also use inline review sections and browser-native `window.confirm` prompts; they are not all instances of this dialog.

Motion is local: prompt/composer transitions are 140ms; thinking dots breathe over 1.4s with .2/.4s stagger; the spinner uses the shared one-second linear rotation. Dialog classes declare a 200ms duration and fade/zoom animation names; these declarations alone do not establish that an external animation plugin is installed. Disclosure arrows rotate with state. Reduced-motion overrides apply globally. No page-transition choreography is implemented in the inspected source.

## Do's and Don'ts

These are instructions for using this **record**, not a quality score or newly adopted visual standards.

### Do

- **Do** distinguish the platform and assistant values, including their separate accent colors, typography and control systems.
- **Do** follow current source order and specificity when reconstructing a state; retain the final mobile corrections and the short-viewport override in baseline comparisons.
- **Do** identify whether evidence is a current live capture, current source or an older retained screenshot.
- **Do** keep source/version labels, exact table alternatives, state feedback and keyboard paths visible when evaluating the existing design.

### Don't

- **Don't** treat this inventory as an endorsement, redesign brief or instruction to preserve every visual choice indefinitely.
- **Don't** invent a creative north star, palette ramp, universal spacing scale, active-navigation treatment, dark theme or component state that the current implementation does not establish.
- **Don't** turn an old screenshot into evidence of current global navigation or fresh authenticated verification.
- **Don't** change application code, styles, components or functionality as part of this documentation pass. Design decisions follow the separate UI/UX critique requested by the user.
