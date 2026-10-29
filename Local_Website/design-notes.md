# Local robot dashboard design notes

## Brief and design

This is a student's local bench workspace. The main tasks are viewing a USB webcam, connecting the robot's MSP430, checking its real replies, and seeing which parts of the proposed robot workflow are still pending. The robot MSP430 remains the main controller; the second MSP430 serves the dock; the Uno handles wheel movement.

The page gives the camera the largest area and keeps connection controls and board readings beside it. A restrained green palette connects the workspace to plant care. System fonts avoid network dependencies. Panels, readable text, a shared spacing scale, native form controls, and visible keyboard focus support use at the lab bench. There is no marketing hero, stock imagery, decorative animation, or invented telemetry.

## Data and interaction boundaries

- Camera access requires Start camera. It requests video only, stays in the browser, and stops its tracks on Stop or page exit. Save image downloads a local PNG; it does not perform pest detection.
- Serial connection requires Connect. The frontend uses only the backend's allowed port and command endpoints. Command feedback distinguishes sending a request from receiving the board reply.
- Board readings appear only while the connection is fresh. Paused, stale, disconnected, or unreachable states show missing values and the last reading time where available.
- The six workflow steps describe the proposed process. No job, drive, spray, or approval command is implemented. Robot sensors and the dock explicitly show Not linked.
- The activity list is built from real backend events using text nodes. Save log downloads those events with an export timestamp.

## Skill collection coverage

The collection was consulted as a coordinated workflow; specialized tools were not installed merely to exercise a skill.

| Skills | Contribution or scope decision |
| --- | --- |
| project-context | Preserved the main-controller architecture and separated verified bench functions from planned robot functions. Parent maintains project context. |
| ui-ux-pro-max | Queried the installed reference data. Applied status visibility, keyboard use, and pause controls. Rejected an off-target landing-page/glass style result for this bright lab workspace. |
| design-taste-frontend | Consulted brief inference and scope. Its entrypoint explicitly excludes dashboards; the marketing and React-specific branches were not adopted. |
| impeccable | Read the craft guidance, ran context discovery and static detection, and fixed the reported disabled-text contrast issue. No generated audit score is claimed. |
| emil-design-eng, frontend-design | Consistent control behavior, limited motion, camera-led hierarchy, and deliberate visual grouping. |
| hallmark | App-screen design and fresh-context implementation/review. Ran static lint; parent performed rendered browser review. No marketing theme or photo treatment was applied. |
| brand-guidelines, theme-factory | Used one project palette. Anthropic branding and preset theme selection do not apply. |
| better-colors, better-ui | Semantic color tokens, contrast, consistent borders/radii, and hover/focus/disabled states. |
| better-layout, rad-spacing | Shared spacing, responsive tracks, proximity, and predictable reading order. No Figma operations. |
| better-accessibility, better-writing | Native labels/buttons, skip link, clear error recovery, live status messages, 44px controls, reduced-motion support, and concise copy. |
| vercel-composition-patterns, shadcn | Reviewed state ownership and component scope. React/shadcn implementation branches do not apply to this native HTML/JS page. |
| gsap-core, gsap-timeline, gsap-scrolltrigger, gsap-plugins, gsap-utils | Evaluated motion needs. No sequenced, scroll-driven, or gesture animation is useful here; no GSAP dependency was added. |
| gsap-performance, gsap-react, gsap-frameworks | Minimal transform-only press feedback and cleanup. No React/Vue/Svelte lifecycle integration is applicable. |
| design-auditor | Scoped review of hierarchy, colors, spacing, accessibility, forms, responsive behavior, states, copy, tokens, and honest status. The Figma/full scoring branches were not run. |
| web-design-guidelines | Fetched current rules and reviewed the changed frontend. Applied native semantics, focus visibility, labels, text wrapping, and explicit states. |
| performance-optimization | No external assets; one non-overlapping state poll; hidden-page polling pauses; events only redraw when changed and are capped at 50 visible entries. No performance benchmark is claimed. |
| seo-audit | Local private app: descriptive title and noindex/nofollow. Public search optimization is inapplicable. |
| debugging-and-error-recovery | Fixed evidenced contrast, stale error, paused connection, and mobile camera width issues. |
| webapp-testing | Parent runs browser/API/hardware checks, permission-denial and synthetic-camera tests, and desktop/mobile render checks. No real camera was activated during development. |

## Executed frontend checks and limitations

- `node --check static/app.js` passed.
- Impeccable static detection returned `[]` after the contrast fix.
- Hallmark static app lint has zero warnings and zero unwaived Reflex findings. Its one remaining `FAIL 19` mistakes the measurement placeholder `—` for a prose dash. The missing-value notation is intentionally retained; it is not a claim of a reading.
- The live-video poster Reflex is documented in the stylesheet: a camera MediaStream has no recorded poster frame, and the visible camera-off panel provides the empty state before access.
- Hallmark's own render tier could not run because `puppeteer-core` is unavailable. Parent's Playwright rendered checks cover the live local page instead.
- Parent's browser review found intrinsic camera width overflow on mobile. Explicit width, shrinkable grid tracks, and minimum widths were corrected; global horizontal clipping was removed so verification can detect remaining overflow.
- Browser and hardware verification results belong in the main README/test report. The frontend does not infer successful physical movement, spraying, docking, or detection from a software acknowledgement.
