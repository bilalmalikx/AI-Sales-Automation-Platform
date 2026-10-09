# Salesway frontend prototype

Independent plain HTML, CSS, and JavaScript prototype. No build step, no backend dependency, and no custom cursor.

Run from the repository root:

    python3 -m http.server 4173 --directory prototype

Open http://localhost:4173. Navigate with the sidebar. Changes persist in browser local storage; Settings → Reset demo workspace restores sample data.

Complete demo path: add/import leads → create a campaign with selected leads → activate campaign → run AI workflow for an assigned lead → edit and approve draft → demo send → inbox reply → demo meeting → CRM stage → analytics.

All research, incoming conversations, sending and calendar actions are simulated. No external messages are sent. Charts use illustrative values. CSV imports and exports, editing, validation, local persistence and theme switching operate on real local data.

Design: local Figtree variable font, Porcelain Indigo / Midnight Ink semantic themes, with Match System appearance, collapsible desktop sidebar, responsive drawer, keyboard-accessible custom dropdowns, workspace search, accessible native dialogs, reduced-motion support, 3-second introduction, normal system cursor.
