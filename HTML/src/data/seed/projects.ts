/* Customers, people and projects. All names are fictional. */
import type { Customer, Milestone, Person, PhaseState, Project, ProjectPhase } from "@/types";
import { day } from "../time";

export const CUSTOMERS: Customer[] = [
  { id: "c-alnoor", name: "Al Noor Trading", sector: "Trading and distribution", city: "Dubai", country: "UAE" },
  { id: "c-meridian", name: "Meridian Port Logistics", sector: "Logistics", city: "Dubai", country: "UAE" },
  { id: "c-oasis", name: "Oasis Ridge Healthcare", sector: "Healthcare", city: "Abu Dhabi", country: "UAE" },
  { id: "c-saffron", name: "Saffron Bay Hospitality", sector: "Hospitality", city: "Sharjah", country: "UAE" },
];

export const PEOPLE: Person[] = [
  { id: "u-rania", name: "Rania Al Mansoori", title: "Founder and CEO", role: "owner" },
  { id: "u-omar", name: "Omar Siddiqui", title: "Delivery Manager", role: "project_manager" },
  { id: "u-sara", name: "Sara Khalil", title: "Project Manager", role: "project_manager" },
  { id: "u-priya", name: "Priya Nair", title: "Technical Reviewer", role: "reviewer" },
  { id: "u-daniel", name: "Daniel Weber", title: "Head of IT, Meridian Port Logistics", role: "customer_approver", customerId: "c-meridian" },
  { id: "u-huda", name: "Huda Rahman", title: "Operations Director, Oasis Ridge Healthcare", role: "customer_approver", customerId: "c-oasis" },
];

/** All 13 phases: completed before `active`, `state` at `active` with `progress`, upcoming after. */
function lifecycle(active: number, state: PhaseState, progress: number, startedDaysAgo: number): ProjectPhase[] {
  return Array.from({ length: 13 }, (_, index) => {
    const phase = index + 1;
    if (phase < active) {
      const completedAt = day(-(startedDaysAgo + (active - phase) * 6));
      return { phase, state: "completed" as const, progress: 100, startedAt: day(-(startedDaysAgo + (active - phase) * 6 + 6)), completedAt, gateApprovedBy: "u-rania" };
    }
    if (phase === active) return { phase, state, progress, startedAt: day(-startedDaysAgo) };
    return { phase, state: "upcoming" as const, progress: 0 };
  });
}

function milestones(projectId: string, items: [string, number, number, boolean][]): Milestone[] {
  return items.map(([title, phase, dueDays, done], n) => ({ id: `${projectId}-m${n + 1}`, title, phase, due: day(dueDays), done }));
}

export const PROJECTS: Project[] = [
  {
    id: "p-spo", code: "ANT-SPO", name: "SharePoint Online Migration", customerId: "c-alnoor", service: "sharepoint_migration", status: "active",
    managerId: "u-omar", startDate: day(-64), targetDate: day(38), budgetAed: 420_000, spentAed: 268_000,
    summary: "Migrating 1.8 TB of on-premises SharePoint 2016 content (42 site collections) to SharePoint Online with permissions clean-up.",
    phases: lifecycle(9, "active", 58, 12),
    milestones: milestones("p-spo", [
      ["Requirements baseline approved", 7, -30, true], ["Migration design approved", 8, -14, true], ["Pilot migration complete", 9, 3, false],
      ["Full migration and cut-over", 9, 21, false], ["UAT sign-off", 11, 34, false],
    ]),
  },
  {
    id: "p-intranet", code: "MPL-INT", name: "Enterprise Intranet Modernization", customerId: "c-meridian", service: "intranet", status: "active",
    managerId: "u-sara", startDate: day(-88), targetDate: day(24), budgetAed: 560_000, spentAed: 431_000,
    summary: "A modern SharePoint intranet with news, departmental hubs, people search and a Teams app for 1,400 staff.",
    phases: lifecycle(10, "active", 64, 9),
    milestones: milestones("p-intranet", [
      ["Design baseline approved", 8, -38, true], ["Build complete", 9, -10, true], ["Regression testing complete", 10, 4, false],
      ["Customer UAT", 11, 12, false], ["Go-live", 12, 24, false],
    ]),
  },
  {
    id: "p-power", code: "ORH-PPA", name: "Power Platform Automation", customerId: "c-oasis", service: "power_platform", status: "active",
    managerId: "u-omar", startDate: day(-31), targetDate: day(55), budgetAed: 290_000, spentAed: 96_000,
    summary: "Power Apps and Power Automate for patient-referral intake and approvals, replacing email and spreadsheet tracking.",
    phases: lifecycle(8, "awaiting_approval", 82, 8),
    milestones: milestones("p-power", [
      ["Requirements baseline approved", 7, -9, true], ["Design and backlog approved", 8, 2, false], ["Build complete", 9, 30, false], ["UAT sign-off", 11, 48, false],
    ]),
  },
  {
    id: "p-docai", code: "ORH-ADP", name: "Azure AI Document Processing", customerId: "c-oasis", service: "ai", status: "on_hold",
    managerId: "u-sara", startDate: day(-20), targetDate: day(90), budgetAed: 380_000, spentAed: 22_000,
    holdReason: "Waiting for the customer's purchase order; the award cannot be validated until it arrives.",
    summary: "Azure AI Document Intelligence to extract claims data from scanned forms, with human review of low-confidence fields.",
    phases: lifecycle(5, "blocked", 40, 6),
    milestones: milestones("p-docai", [["Proposal accepted", 4, -8, true], ["Purchase order validated", 5, -1, false], ["Kickoff", 6, 10, false]]),
  },
  {
    id: "p-spse", code: "MPL-SSE", name: "SharePoint Subscription Edition Upgrade", customerId: "c-meridian", service: "sharepoint_migration", status: "active",
    managerId: "u-omar", startDate: day(-102), targetDate: day(9), budgetAed: 310_000, spentAed: 276_000,
    summary: "Upgrading the on-premises farm from SharePoint 2019 to Subscription Edition with zero-downtime patching.",
    phases: lifecycle(11, "awaiting_approval", 92, 6),
    milestones: milestones("p-spse", [["QA completion report approved", 10, -7, true], ["UAT complete", 11, 1, false], ["Production upgrade", 12, 9, false]]),
  },
  {
    id: "p-workflow", code: "SBH-EWM", name: "Enterprise Workflow Modernization", customerId: "c-saffron", service: "automation", status: "active",
    managerId: "u-sara", startDate: day(-14), targetDate: day(80), budgetAed: 340_000, spentAed: 41_000,
    summary: "Replacing paper and email approvals (purchasing, leave, maintenance requests) across 9 hotels with governed workflows.",
    phases: lifecycle(7, "active", 35, 5),
    milestones: milestones("p-workflow", [["Kickoff complete", 6, -6, true], ["Requirements baseline approved", 7, 8, false], ["Design approved", 8, 22, false]]),
  },
  {
    id: "p-ess", code: "SBH-ESS", name: "Employee Self-Service Portal", customerId: "c-saffron", service: "intranet", status: "completed",
    managerId: "u-omar", startDate: day(-190), targetDate: day(-40), budgetAed: 240_000, spentAed: 229_000,
    summary: "A self-service portal for leave, payslips and HR requests, live since October.",
    phases: Array.from({ length: 13 }, (_, i) => ({ phase: i + 1, state: "completed" as const, progress: 100, startedAt: day(-190 + i * 11), completedAt: day(-180 + i * 11), gateApprovedBy: "u-rania" })),
    milestones: milestones("p-ess", [["Go-live", 12, -52, true], ["Project closed", 13, -40, true]]),
  },
];
