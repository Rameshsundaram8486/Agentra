/* The presenter guide: a story of about 17 minutes through the demo, step by step. Each step names the screen, what to do,
   what to say and which Agentra rule it shows. Kept in code next to the screens so it changes with them. */
import type { Role } from "@/types";

export interface GuideStep {
  id: string;
  minutes: number;
  title: string;
  link: string;
  role?: Role; // the role to act as for this step
  doThis: string[];
  say: string;
  rule?: string;
}

export const GUIDE_SETUP = [
  "Open the demo controls (PAUSED in the top bar) and choose Reset demo data, so the story starts from the beginning.",
  "Act as the owner (Rania Al Mansoori) from the profile menu at the top right.",
  "Pick the theme for the room: dark for a screen or projector, light for a bright room or a printout.",
  "Keep the simulation paused until step 2; it runs at 1x, and 2x or 5x shortens the waits.",
];

export const GUIDE_STEPS: GuideStep[] = [
  {
    id: "command", minutes: 2, title: "A company run by agents, governed by people", link: "/", role: "owner",
    doThis: ["Point to the key figures, then the Project Owner Intelligence Briefing: score, findings and recommended priorities.", "Point to Human attention required on the right: 9 decisions waiting, 1 overdue."],
    say: "Every number here is computed from records: projects, agent runs, decisions, risks. The Project Owner Agent watches all of it and says what needs attention. Agents do the work and recommend; people decide.",
    rule: "Findings come from records; recommendations are labelled as the agent's proposals.",
  },
  {
    id: "live", minutes: 1, title: "Start the simulation", link: "/",
    doThis: ["Open the demo controls and choose Start simulation; the badge turns LIVE.", "Watch the activity feed: within about 10 seconds WI-004 v2 passes its sandbox build and tests, and a notification arrives."],
    say: "This is a scripted, deterministic story, so it plays the same way every time. Work that depends on a person waits until that person decides.",
  },
  {
    id: "operations", minutes: 2, title: "Live operations and the AI workforce", link: "/operations",
    doThis: ["Show the pipeline graph: agent stages, human approval gates and the Project Owner Agent's oversight.", "In Failed runs, open the performance test and choose Retry: it runs again.", "Switch to the reviewer and try Pause on a running run: it is refused, with the reason."],
    say: "Agents hand work to each other, and every handoff that matters passes a human gate. Who may control a run is a rule, not a convention.",
    rule: "Only owners and project managers control agent runs.",
  },
  {
    id: "project", minutes: 1, title: "One project, end to end", link: "/projects/p-spo", role: "owner",
    doThis: ["Show the critical banner and its reasons, then the Lifecycle and Development tabs."],
    say: "Health is never typed in. This project is critical because of an open risk, an overdue decision and a failed run, and each reason links to its record.",
  },
  {
    id: "lifecycle", minutes: 1, title: "The 13-phase lifecycle", link: "/lifecycle",
    doThis: ["Point out the MVP band (Phases 7 to 11) and the gate after each phase.", "Select Phase 11 to show the customer sign-off gate."],
    say: "From sales to closure, each phase ends with a human approval. The MVP covers requirements through customer sign-off; the other phases are previews.",
  },
  {
    id: "recommendation", minutes: 2, title: "A person changes an agent's recommendation", link: "/decisions?id=d-platform", role: "owner",
    doThis: ["Read the Business Analyst Agent's recommendation: SharePoint Online.", "Choose Hybrid, add the constraint 'Purchase orders above AED 50,000 stay on premises', then Use the selected option.", "Show the original AI recommendation and the final human decision side by side, then the history and the audit trail."],
    say: "The agent's recommendation is never edited; the human decision is recorded beside it with who, when and why. In a few seconds the agent picks the work up again with the platform the person chose.",
    rule: "Agents never decide; the recommendation is preserved; every outcome is audited.",
  },
  {
    id: "escalation", minutes: 1, title: "An overdue escalation, and who may decide it", link: "/decisions?id=d-cutover", role: "project_manager",
    doThis: ["As the project manager, choose Accept recommendation: it is refused, because only the owner may move the cut-over date.", "Choose Act as owner, then accept.", "Show What this decision changed: the cut-over moved and RSK-001 is now mitigated. The Command Center's figures change too."],
    say: "The roles that may decide are part of each decision, and the refusal says why. A decision changes the plan everywhere at once.",
    rule: "Only the roles named on a decision may decide it.",
  },
  {
    id: "approval", minutes: 1, title: "An approval binds to the exact version", link: "/approvals", role: "reviewer",
    doThis: ["As the reviewer, open Approve change set WI-004 v2 (ready once its sandbox run passed) and approve it.", "Show 'Bound to Change set WI-004 v2, sha256 …'. Optionally, send it back instead: the agent revises it as v3, and v3 needs its own approval."],
    say: "Nothing is approved before its evidence is in, and an approval is for one exact version. A newer version needs a new approval.",
    rule: "Approvals bind to the artifact version and its sha256; no approval without a passing sandbox run.",
  },
  {
    id: "signoff", minutes: 1, title: "The customer signs off UAT", link: "/decisions?id=d-uat-signoff", role: "customer_approver",
    doThis: ["As the customer approver (Daniel Weber), sign off.", "Open the Delivery Lifecycle for this project: Phase 11 completes and the go-live checklist starts (Preview)."],
    say: "Only the customer can record UAT sign-off; the UAT agent prepares the pack but never signs.",
  },
  {
    id: "agents", minutes: 1, title: "The agent workforce", link: "/agents", role: "owner",
    doThis: ["Filter by Working, then open an agent's profile: tools, autonomy, model, runs and console."],
    say: "Twenty-three agents in eight categories, each with a defined job, tools and autonomy. Every model call goes through one gateway with a monthly cap.",
  },
  {
    id: "rca", minutes: 2, title: "Root-cause analysis: facts apart from hypotheses", link: "/owner?incident=inc-3", role: "project_manager",
    doThis: ["Show the observed evidence (confirmed facts) and the probable cause (AI hypothesis, medium confidence).", "As the project manager, Confirm the cause, then Mark resolved.", "Try Verify and close: refused. Switch to the reviewer and close it."],
    say: "The agent proposes a cause; a person confirms it. And the person who resolved an incident cannot close it: someone else verifies.",
    rule: "Independent verification: the resolver may not close the incident.",
  },
  {
    id: "reports", minutes: 1, title: "Reports from records", link: "/reports?report=executive",
    doThis: ["Show the executive report preview, then Download CSV or Print or save as PDF."],
    say: "Reports are built from the records at this moment, never from narrative. Where the records cannot support a figure, the report says so.",
  },
  {
    id: "governance", minutes: 1, title: "Autonomy and governance settings", link: "/admin/agents?agent=qa_tester", role: "owner",
    doThis: ["Show the three autonomy levels and the QA Agent's actions.", "Try to make 'Run approved test suites' conditional: refused, it is medium risk.", "Point to 'Approve, sign off or decide: Never. Not configurable.'"],
    say: "Autonomy is set per action and risk class, and every change is versioned and audited. No setting lets an agent approve.",
    rule: "Autonomy is capped by risk class; approving is never an agent's.",
  },
];

export const GUIDE_QUESTIONS: { q: string; a: string }[] = [
  { q: "Is this connected to real systems?", a: "No. Everything in this demo is simulated in the browser; the 'Demo · simulated' badge stays on every screen. Integrations, usage and sandbox runs are scripted." },
  { q: "Is the real product built?", a: "The Agentra backend enforces these rules for the delivery phases built so far: the workflow engine, approvals bound to versions, guardrails on agent output. The demo uses the same rules but does not call the backend." },
  { q: "Can an agent approve its own work?", a: "No. Only people approve or decide, the author of a document cannot approve it, and that is enforced in code, not by prompt." },
  { q: "What does it cost to run the agents?", a: "Every model call goes through the model gateway, which refuses a call that would exceed the monthly cap. See Model Gateway." },
];

export const GUIDE_RECOVERY = [
  "Anything unexpected: open the demo controls and choose Reset demo data; the story starts again.",
  "A step needs a decision that is not ready yet: let the simulation run a few more seconds, or switch it to 5x.",
  "A refusal appears: read it out. Refusals are part of the story; they show the rules.",
];
