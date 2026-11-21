# Phase 12 — Interview Questions and Answers

This question bank covers **Phase 12: Agent Console**. The answers separate work implemented in P12-1 through P12-4 from later ticket workflow actions that belong to Phase 13.

Related reading:

- [Phase 12 plain-language explanation](../explain_codebase/phase12_explained.md)
- [Phase 12 system-design evolution](../design_evolution/Phase12_Project_System_Design_Evolution.md)
- [Phase 12 infrastructure evolution](../Infra_design_evolution/Phase12_Infra_design_evolution.md)
- [Phase 12 task status](../../TASK.md)
- [Phase 12 plan](../../PLAN_PHASE.md)

## 30-second overview

### 1. Can you summarize Phase 12?

**A:** “Phase 12 gives CloudDesk a browser console. It adds a Next.js app shell, shared navigation, a typed API client, demo login and session restoration, role-aware layout behavior, and read-only dashboard and support-detail pages.”

### 2. What problem did Phase 12 solve?

**A:** “The backend could already perform support operations, but users needed a consistent browser interface for sign-in, navigation, reading tickets and customers, viewing knowledge, and monitoring escalations and workflow events.”

### 3. Which four subtasks make up Phase 12?

**A:** “P12-1 created the Next.js app shell and navigation, P12-2 created the typed API client, P12-3 created login and role-aware layout behavior, and P12-4 created the read-only list and detail pages.”

### 4. Is Phase 12 the complete support-agent screen?

**A:** “No. It completes the console shell and read-only pages. The detailed three-column ticket action screen and approve, reject, reply, request-information, and escalate controls belong to Phase 13.”

### 5. Does Phase 12 move business rules into the frontend?

**A:** “No. Frontend role rules improve navigation and hide unavailable controls, but FastAPI remains responsible for authentication, authorization, validation, workflow decisions, and data access.”

### 6. Which frontend framework does Phase 12 use?

**A:** “Next.js 15 using the App Router, TypeScript, React, and Tailwind CSS.”

### 7. Which backend framework serves the frontend?

**A:** “FastAPI serves the `/api/v1/*` routes and health routes.”

### 8. What is the main frontend architecture pattern?

**A:** “Next.js presents pages and layout, `ApiClient` communicates with FastAPI, React context manages the user session, and read pages consume typed API responses.”

### 9. Is Docker networking part of Phase 12?

**A:** “No. Next.js and FastAPI run as separate local processes in Phase 12. Docker files and Compose networking belong to a later delivery phase.”

### 10. What is the strongest one-sentence Phase 12 summary?

**A:** “Phase 12 creates the CloudDesk browser console by joining a Next.js shell, role-aware authentication, a typed API client, and read-only operational pages around the existing FastAPI backend.”

## P12-1 — App shell and navigation

### 11. What does P12-1 create?

**A:** “It creates the Next.js app shell, shared navigation, responsive layout, route structure, placeholder pages, and current-user console frame.”

### 12. Where is the app-wide layout defined?

**A:** “In `frontend/app/layout.tsx`.”

### 13. What is the role of `AuthProvider` in the layout?

**A:** “It restores or creates the browser session and exposes the user, role, loading state, sign-in, sign-out, and role convenience fields to the application.”

### 14. What is the role of `LoginGate`?

**A:** “It prevents protected route content from being rendered when no authenticated user is available and redirects unsigned-out users to `/login`."

### 15. Where is the shared navigation declared?

**A:** “In `frontend/components/layout/nav.ts`."

### 16. Why declare navigation once?

**A:** “It avoids duplicated menu definitions and gives every layout component a consistent route and label source.”

### 17. Which primary routes are declared?

**A:** “Dashboard, tickets, customers, knowledge, escalations, agents, audit, settings, and API health.”

### 18. What does `AppShell` contain?

**A:** “A desktop sidebar, CloudDesk branding, role-aware navigation, a sticky header, user identity, sign-out control, and the current route content.”

### 19. How does the layout behave on small screens?

**A:** “The fixed desktop sidebar is hidden and the main content remains available without a desktop-width layout.”

### 20. What is a Next.js dynamic route in this project?

**A:** “A route such as `/tickets/[id]`, `/customers/[id]`, or `/knowledge/[id]` that displays one record identified by a URL parameter.”

### 21. What does P12-1 add on the backend side?

**A:** “P12-1 does not add backend business behavior. It provides the frontend route and layout structure around existing backend APIs.”

### 22. Is standalone Next.js output part of P12-1?

**A:** “The project config sets `output: "standalone"`, which prepares the frontend for a later container deployment. It does not itself create a Docker container.”

## P12-2 — Typed API client

### 23. Where is the frontend API client implemented?

**A:** “In `frontend/lib/api.ts`."

### 24. Why is a typed API client important?

**A:** “It centralizes HTTP requests, authentication, headers, base URLs, error handling, and response contract types so pages do not duplicate fetch behavior.”

### 25. What is the frontend contract source?

**A:** “`frontend/lib/types.ts`, mirrored from the route and payload definitions in `docs/API_CONTRACT.md`."

### 26. What does `ApiClient.request<T>()` do?

**A:** “It builds headers, reads the access token, sends the fetch request, parses JSON or text, handles 401 and HTTP errors, and returns the requested TypeScript response shape.”

### 27. What is `NEXT_PUBLIC_API_BASE_URL`?

**A:** “It is the public frontend API base URL. The default is `http://localhost:8000`."

### 28. Why is it safe to use a `NEXT_PUBLIC_*` API URL?

**A:** “It identifies the public API address, not a secret. It must not contain database passwords, JWT signing secrets, service-role keys, or provider keys.”

### 29. Where is the bearer token stored?

**A:** “In browser `localStorage` under `clouddesk_access_token`."

### 30. Does the browser store a service-role key?

**A:** “No. It stores only the normal user access token.”

### 31. Which header carries the bearer token?

**A:** “`Authorization: Bearer <token>`."

### 32. Which header carries request correlation?

**A:** “`X-Request-ID`."

### 33. How are missing browser request IDs handled?

**A:** “The client uses `crypto.randomUUID()` when available and a timestamp/random fallback otherwise.”

### 34. What does `X-Request-ID` provide?

**A:** “It provides a correlation value for browser requests, backend logs, and later audit troubleshooting.”

### 35. Is the request ID generated from the user or ticket?

**A:** “No. It is a random client-side or server-created correlation identifier for the HTTP request.”

### 36. What content header is used for JSON request bodies?

**A:** “`Content-Type: application/json`."

### 37. What happens on HTTP 401?

**A:** “The client clears the stored token and redirects the browser to `/login?reason=expired`."

### 38. What happens on HTTP 403?

**A:** “The client raises `ApiError` with status 403. It does not silently retry or make the role valid.”

### 39. What is `ApiError`?

**A:** “An application error class containing a readable message, HTTP status, and original response detail.”

### 40. What is `NetworkError`?

**A:** “An error class used when the fetch call fails because the API cannot be reached or another TypeError-level network failure occurs.”

### 41. What is the difference between 401 and 403?

**A:** “401 means the request has no valid usable session. 403 means the session is valid enough but the user's role is not permitted.”

### 42. What does the client do on 204 No Content?

**A:** “It returns `undefined as T` instead of trying to parse a JSON body.”

### 43. How are JSON and text responses handled?

**A:** “The client reads the response text, parses JSON when possible, and otherwise retains plain text before constructing an API error or typed response.”

### 44. Which API groups does `ApiClient` cover?

**A:** “Auth, health, tickets, workflow status/events, customers, knowledge, approvals, and escalations.”

### 45. How does `issueDemoToken()` work?

**A:** “It posts the demo email to `/api/v1/auth/demo-token`, receives the access token, and stores it through the configured token setter.”

### 46. How does `me()` work?

**A:** “It calls `/api/v1/auth/me` with the stored bearer token and returns the current profile and role.”

### 47. How are ticket filters serialized?

**A:** “The client builds an URL query string with status, category, severity, limit, and offset when values are provided.”

### 48. Why encode dynamic IDs?

**A:** “`encodeURIComponent()` prevents a dynamic ticket or customer ID from breaking the URL path.”

### 49. Does the API client execute support policy?

**A:** “No. It sends requests and interprets transport responses. Backend services and RBAC enforce policy.”

### 50. Why is the typed client testable?

**A:** “It supports custom base URLs, token functions, and fetch implementations, allowing unit tests to inspect requests without a live backend.”

## P12-3 — Login and role-aware layout

### 51. Which demo accounts are available in the login form?

**A:** “`admin@clouddesk.demo`, `sam.agent@clouddesk.demo`, and `vic.viewer@clouddesk.demo`."

### 52. What happens when a user submits demo login?

**A:** “The frontend issues a demo token, stores it, calls `/auth/me` for the profile, stores the profile in React context, and redirects to `/dashboard`."

### 53. What is `AuthProvider` responsible for?

**A:** “It owns browser session state and exposes sign-in, sign-out, current user, loading status, and role convenience fields.”

### 54. What fields does authentication context expose?

**A:** “User profile, loading state, sign-in, sign-out, `canAct`, `isAdmin`, and `isViewer`."

### 55. What does `canAct` mean?

**A:** “The role is at least agent level, so agent-style actions should be permitted in the frontend.”

### 56. Does `canAct` make an action authorized?

**A:** “No. It controls frontend presentation. FastAPI must still validate the role and action policy.”

### 57. How does session restoration work?

**A:** “On application load, `AuthProvider` checks local storage, calls `/auth/me` if a token exists, stores the profile, or clears the session and redirects to login.”

### 58. What happens if `/auth/me` fails?

**A:** “The provider clears the token and user state and redirects protected routes to `/login`."

### 59. What is `LoginGate` responsible for?

**A:** “It keeps protected route content hidden during session restoration or after sign-out and allows `/login` to remain public.”

### 60. Does `LoginGate` replace backend authentication?

**A:** “No. It only controls browser rendering. Backend routes still require a valid JWT and role.”

### 61. Why are login search parameters inside Suspense?

**A:** “The login form reads `reason=expired` with `useSearchParams()`, so a Suspense boundary prevents static prerender issues in Next.js.”

### 62. What is the frontend role hierarchy?

**A:** “Viewer level 1, agent level 2, and admin level 3.”

### 63. What role can act on support cases?

**A:** “Agent and admin roles.”

### 64. What role can configure settings?

**A:** “Only admin.”

### 65. What can a viewer do in the console conceptually?

**A:** “Read permitted tickets, customers, knowledge, and audit areas according to backend route rules, but not perform agent actions.”

### 66. How does role-aware navigation work?

**A:** “`RoleAwareNav` filters `navItems` based on the current profile role before rendering links.”

### 67. Which navigation items are role-sensitive?

**A:** “Settings is admin-only. Audit is hidden from viewers and shown to agents and admins.”

### 68. Is a hidden menu item proof that an API cannot be called?

**A:** “No. Hiding it is presentation behavior. FastAPI's route authorization is the enforcement boundary.”

### 69. What happens on sign-out?

**A:** “The frontend removes the access token, clears the user context, and redirects to `/login`."

### 70. Is sign-out server-stateful in this implementation?

**A:** “No. It removes the browser token and session state; the demo JWT itself is not revoked by a server session store in this Phase 12 flow.”

### 71. Should a viewer see approve or reject controls?

**A:** “No. The final ticket screen will use `canAct` or equivalent role checks and pending approval status to prevent such controls.”

### 72. How is role enforcement defense-in-depth?

**A:** “Frontend rules reduce confusing navigation and accidental calls, while backend role checks reject any direct unauthorized API request.”

## P12-4 — Read-only list and detail pages

### 73. What does P12-4 implement?

**A:** “It implements read-only dashboard, ticket, customer, knowledge, escalation, and detail pages backed by the typed API client.”

### 74. Is P12-4 a final ticket action screen?

**A:** “No. It includes read-only ticket detail and workflow events but not the three-column action interface."

### 75. What does the dashboard show?

**A:** “Ticket count, customer count, and open escalation count."

### 76. How does the dashboard obtain counts?

**A:** “It calls ticket, customer, and escalation list APIs concurrently and uses the returned item lengths."

### 77. Does the dashboard use a dedicated backend endpoint in P12-4?

**A:** “No. It aggregates existing list endpoint results in the frontend."

### 78. What does the ticket list show?

**A:** “Ticket number, subject, category, severity, status, updated date, and detail link."

### 79. What controls are absent from the ticket list?

**A:** “Run workflow, approval, rejection, reply, request-information, and escalation controls."

### 80. What does the customer list show?

**A:** “Name, email, company, plan, and a link to customer detail."

### 81. What does customer detail combine?

**A:** “Subscriptions, workspaces, safe memory notes, and ticket history."

### 82. What does knowledge list show?

**A:** "Category, title, slug, summary, and a link to article detail."

### 83. What does knowledge detail show?

**A:** “Article title, category, tags, summary, and Markdown content."

### 84. What does the escalation page show?

**A:** “Team, reason, status, created date, and link to the related ticket."

### 85. What does the read-only ticket detail show?

**A:** “Ticket number, subject, status, severity, customer, channel, category, workspace, messages, workflow status, and workflow events."

### 86. How are workflow events presented?

**A:** “As a chronological operational event list with event type, node name, and timestamp when available.”

### 87. Are raw prompts or hidden reasoning displayed?

**A:** “No. The read view excludes hidden prompts and reasoning and shows safe workflow activity only.”

### 88. Can P12-4 pages execute account or refund actions?

**A:** “No. They are read-only and contain no consequential action controls.”

## Shared read-page behavior

### 89. What loading state is used?

**A:** “The `LoadingState` component displays a readable loading message instead of a blank page.”

### 90. What is an empty state?

**A:** “An empty state explains that the API succeeded but there are currently no records to display.”

### 91. What is `NetworkErrorBanner`?

**A:** “A red, readable alert with an optional Retry button for network or API error recovery.”

### 92. How are API errors shown?

**A:** “Through readable error detail text or a retry banner, rather than raw response objects.”

### 93. What is `StatusPill`?

**A:** “A small colored label that presents status or severity values consistently.”

### 94. How are status colors chosen?

**A:** “Resolved/completed/approved are success, waiting/pending/paused are warning, critical/escalated/rejected are danger, and unknown ordinary values are neutral.”

### 95. Is the color logic a backend policy decision?

**A:** “No. It is presentation logic. The backend owns severity and status values."

### 96. How are technical labels formatted?

**A:** “Underscores become spaces and words receive title capitalization, such as `waiting_on_approval` becoming `Waiting On Approval`."

### 97. How are dates formatted?

**A:** “A browser locale date-and-time formatter is used, with `—` for missing or invalid values.”

### 98. How does `usePolling` work?

**A:** "It loads data immediately, stores data/loading/error state, sets an interval, reloads periodically, and clears the interval on unmount."

### 99. Which pages poll and how often?

**A:** “Dashboard, tickets, customers, escalations, and customer detail poll every 10 seconds; ticket detail every 2 seconds; knowledge list and detail every 30 seconds.”

### 100. Why poll ticket detail every 2 seconds?

**A:** “It gives a near-live workflow-progress view without a WebSocket implementation.”

### 101. What is a trade-off of polling?

**A:** “It is simple but creates periodic API traffic and can be stale between requests. WebSockets or server-sent events could provide more efficient real-time updates later.”

### 102. Why clear intervals on page unmount?

**A:** “It prevents inactive pages from continuing network requests or updating unmounted components.”

### 103. Can read-page polling access secrets or hidden prompts?

**A:** “No. It calls API routes that return only the safe workflow state and event fields allowed by the backend.”

## Testing and validation

### 104. Which frontend test framework is used?

**A:** “Vitest with Testing Library and jsdom.”

### 105. What does the app-shell test prove?

**A:** “The CloudDesk brand, primary navigation, and supplied page content render.”

### 106. What does the navigation test prove?

**A:** “The console routes are declared once and role hierarchy is viewer < agent < admin.”

### 107. What does role-aware navigation test prove?

**A:** “Settings is admin-only, and Audit is hidden from viewers but visible to agents and admins.”

### 108. What do API-client tests prove?

**A:** “Demo-token storage, request IDs, ticket query filters, 404 API errors, network failures, and approval POST request bodies.”

### 109. What do read-page component tests prove?

**A:** “Status labels, warning tones, loading and empty states, label formatting, and invalid-date fallback behavior.”

### 110. How many frontend tests are in the current Phase 12 implementation?

**A:** “The implementation is reported as 16 frontend tests passing locally across API, app shell, navigation, auth, role, and read-page suites.”

### 111. What validation commands are used?

**A:** “`npm test`, `npm run lint`, and `npm run build`."

### 112. What does the Next.js build prove?

**A:** “The frontend source compiles, type-checks, lint-validates, and its App Router pages can be generated or rendered.”

### 113. Does the build prove live backend integration?

**A:** “No. It proves frontend compilation and contracts; live API behavior requires FastAPI and demo data to run."

### 114. Does the frontend test suite prove real JWT security?

**A:** “No. It proves client behavior. Backend JWT and RBAC tests remain the real security evidence.”

## Infrastructure and routing

### 115. What is the implemented local process topology?

**A:** “Next.js runs as a frontend process on port 3000 and FastAPI runs as a backend process on port 8000.”

### 116. How does Next.js reach FastAPI locally?

**A:** “The browser uses `NEXT_PUBLIC_API_BASE_URL`, defaulting to `http://localhost:8000`."

### 117. Is the API client browser-only or server-only?

**A:** “The API client supports browser token and fetch behavior and is used by client components. It is not a service-role backend connection.”

### 118. What is the browser allowed to connect to directly?

**A:** “The Next.js frontend and public FastAPI API. It should not connect directly to SQL, Redis, Qdrant, or AI provider secrets.”

### 119. Why are there no Docker components in Phase 12?

**A:** “Phase 12 is application functionality. Container images and Compose networking are delivery work in a later phase.”

### 120. What future container topology is likely?

**A:** “Browser traffic reaches the frontend container, frontend calls the backend container through HTTP or Compose networking, and backend reaches Redis, Qdrant, and PostgreSQL or another data service.”

### 121. What does `output: "standalone"` do?

**A:** “It prepares a standalone Next.js server bundle for a future deployment or container image.”

### 122. Does standalone output create a Docker image?

**A:** “No. It only affects Next.js build output.”

### 123. What route is `/api/health` in the frontend?

**A:** "A Next.js route placeholder/health route is defined, while backend health status comes from `/health`, `/health/live`, and `/health/ready`."

### 124. What is CORS's role in local frontend networking?

**A:** “FastAPI CORS rules permit configured browser origins such as localhost:3000 to call the API.”

### 125. Which header does CORS expose?

**A:** “It exposes `X-Request-ID` to browser code.”

### 126. What should a future Compose network use for backend addressing?

**A:** "It should use environment-specific frontend API configuration or service routing, not hard-coded localhost once browser and server boundaries move to containers."

## Architecture and trade-offs

### 127. Why use a common app shell?

**A:** “It gives every console page the same navigation, identity, layout, and route behavior rather than duplicating the frame.”

### 128. Why use React context for authentication?

**A:** “It lets layout and route components consume one signed-in profile and loading state without passing props through every page."

### 129. Why use a login gate?

**A:** “It improves the user experience by hiding protected content during loading or sign-out and directing users to login."

### 130. Why keep role checks in FastAPI?

**A:** “The browser can be modified by the user. Only server-side validation can enforce whether a request is allowed.”

### 131. Why use a typed API client instead of direct fetch calls?

**A:** “It centralizes URL, query, headers, token, parsing, error, and contract behavior across pages."

### 132. What is the trade-off of storing JWT in localStorage?

**A:** “It is easy for an SPA to use, but a cross-site scripting attack could read it. A production design should consider CSP, secure cookie options, token lifetimes, and revocation."

### 133. Why does the project use polling instead of WebSockets?

**A:** "It is simpler for the current console and allows read endpoints to provide periodic updates without a real-time backend connection."

### 134. What is a trade-off of polling every 2 seconds?

**A:** “It makes ticket detail feel live but increases API requests and load. WebSockets or server-sent events may be better as scale grows.”

### 135. Why display status pills?

**A:** "They turn technical status values into fast visual cues, but they do not change the value returned by the backend."

### 136. Why format technical labels?

**A:** "It improves support-agent readability while the underlying API continues to use stable machine values."

### 137. Why use loading and empty states?

**A:** "They distinguish waiting, no-data, and error conditions instead of leaving a blank or misleading page."

### 138. Why use network error banners?

**A:** “They tell the user that the backend may be unreachable and offer retry without exposing low-level implementation details.”

### 139. Why are read pages separate from action pages?

**A:** “Read and write responsibilities have different security and workflow implications. Read pages can be built once, while the action page also needs approval and policy controls.”

### 140. What is a design risk from hiding viewer actions only in the frontend?

**A:** “A viewer could send a direct API request or modify browser code. Backend role checks must reject it.”

### 141. What is a design risk from adding dashboard aggregation in the frontend?

**A:** “Three separate API calls can be slower or inconsistent if one changes during loading. A dedicated dashboard route could be more efficient later.”

### 142. What is a design risk from polling multiple pages?

**A:** “It can increase request volume, rate-limit usage, and backend load. Intervals should be tuned and polling should stop on unmount.”

### 143. What is a design risk from storing current user profile in React context only?

**A:** “The context is presentation state and can disappear on refresh. Session restoration from the token and `/auth/me` recreates it.”

### 144. What is the relationship between frontend role and backend role?

**A:** “They should mirror the same names and hierarchy, but the backend response and route validation remain the source of truth.”

### 145. What does `canAct` include?

**A:** “It is true for agent and admin roles and false for viewer.”

### 146. Should viewer pages call agent-only endpoints?

**A:** “No. Navigation and page behavior should avoid known agent-only actions, and backend RBAC should reject direct calls.”

## Remaining work and honest status

### 147. Is P12 complete?

**A:** “Yes for the console shell and read-only list/detail pages. The complete ticket action workflow remains in Phase 13.”

### 148. What is implemented in P12-1?

**A:** “Next.js App Router shell, shared navigation, layout, route placeholders, and responsive console frame.”

### 149. What is implemented in P12-2?

**A:** “Typed API client, mirrored types, bearer-token storage, request IDs, 401 handling, and API/network errors.”

### 150. What is implemented in P12-3?

**A:** “Demo login, session restore, login gate, sign-out, role hierarchy, and role-aware navigation."

### 151. What is implemented in P12-4?

**A:** “Dashboard, ticket, customer, knowledge, escalation, and read-only detail views with loading, empty, error, status, formatting, and polling behavior.”

### 152. What is still missing after P12?

**A:** “The final three-column ticket detail workflow, run-workflow control, approval/rejection controls, reply composer, request-info, escalation action, and full workflow progress UI.”

### 153. Which Phase 13 subtasks depend on P12?

**A:** “P13-1 needs the app shell and detail layout, P13-2 needs read pages and polling foundations, P13-3 needs authentication and API methods, and P13-4 needs frontend test infrastructure.”

### 154. Is live browser-to-backend integration verified locally?

**A:** “The frontend builds and unit tests pass locally. Live API integration depends on the FastAPI server, demo users, database seed, and browser environment running together.”

### 155. Is real Docker deployment complete?

**A:** “No. Dockerfiles, Compose, container networking, health checks, and cloud deployment are later work.”

### 156. Is cloud frontend deployment complete?

**A:** “No cloud account or frontend deployment is claimed in Phase 12.”

### 157. What is the final status sentence for an interview?

**A:** “Phase 12 is complete for the Next.js console shell and read-only support views, while the ticket action interface and container delivery remain Phase 13 or later.”

## Quick interview drills

### 158. Explain P12 in one sentence.

**A:** “It gives CloudDesk a signed-in, role-aware browser console for reading support data.”

### 159. Explain P12-1 in one sentence.

**A:** “It establishes the reusable Next.js layout and shared route navigation.”

### 160. Explain P12-2 in one sentence.

**A:** “It centralizes every frontend API call with typed responses, bearer authentication, request IDs, and error handling.”

### 161. Explain P12-3 in one sentence.

**A:** “It restores or creates a demo user session and hides role-specific navigation in the app shell.”

### 162. Explain P12-4 in one sentence.

**A:** “It replaces placeholders with API-backed read-only dashboard and support-detail pages.”

### 163. What is the frontend role boundary?

**A:** "UX and navigation only; FastAPI is the authorization authority."

### 164. What is the API client's role boundary?

**A:** "HTTP transport and response typing only; business rules remain in FastAPI."

### 165. What is the most important technical trade-off?

**A:** “The frontend is modular and easy to inspect, but periodic polling and browser-held JWT state require production tuning for scale and security.”

### 166. What is the 30-second non-technical answer?

**A:** “Phase 12 gives CloudDesk a proper support-agent screen. Users sign in, see only navigation appropriate to their role, and open dashboard, ticket, customer, knowledge, and escalation information. A common API layer sends secure requests to FastAPI and shows loading or error information clearly. This phase does not yet include the final ticket action buttons.”

### 167. What is the 60-second technical answer?

**A:** “Phase 12 adds a Next.js 15 App Router frontend around the existing FastAPI backend. P12-1 created `AppShell`, shared navigation, and App Router routes. P12-2 created `ApiClient` and mirrored response types, with bearer-token storage, request IDs, query serialization, 401 handling, and typed network/API errors. P12-3 added `AuthProvider`, `LoginGate`, demo login, session restoration, and viewer/agent/admin navigation visibility. P12-4 added API-backed dashboard, ticket, customer, knowledge, escalation, and detail views with shared polling and UI states. FastAPI remains the security and policy authority. Docker networking and the final ticket action screen remain outside this phase.”

### 168. What is the final interview status statement?

**A:** “The Phase 12 console shell and read-only pages are implemented and locally validated. It is not yet the full action-enabled ticket screen or a container-deployed frontend.”
