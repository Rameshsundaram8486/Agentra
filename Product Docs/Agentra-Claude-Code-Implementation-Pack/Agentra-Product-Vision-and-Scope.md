# Agentra — A Company Runs by Agents
## Product Vision, Scope, Operating Model and Implementation Roadmap

## 1. Vision
Agentra is an AI-native company operating platform designed to run an IT services business through specialized AI agents coordinated by governed workflows. Agents perform defined work, the workflow engine controls sequencing and state, and the governance layer enforces permissions, reviews, approvals and auditability.

**Operating principle:** The agents perform the work. The workflow engine coordinates the work. The governance system controls what is allowed. Humans retain oversight of critical decisions.

## 2. MVP Scope
The MVP proves AI-operated project delivery across:
- Phase Seven: Business Analysis and Requirements
- Phase Eight: Solution Architecture and Technical Design
- Phase Nine: Development and Implementation
- Phase Ten: Quality Assurance and Testing
- Phase Eleven: Customer UAT and Sign-Off

Cross-cutting MVP capabilities:
- Project Owner Agent for delivery oversight and failure/RCA coordination
- Executive and detailed reporting for every phase
- Human governance, approvals, auditability and controlled autonomy
- Versioned artifacts and requirements/design/test traceability

## 3. Full Product Scope
The full product expands to:
- Phase One: Sales and Lead Generation
- Phase Two: Meeting Scheduling and Customer Discovery
- Phase Three: Technical and Commercial Proposal
- Phase Four: Customer Presentation and Negotiation
- Phase Five: Project Award and Purchase Order Validation
- Phase Six: Project Kickoff and Governance
- Phase Twelve: Production Go-Live
- Phase Thirteen: Project Closure
- End-to-end Project Owner Agent oversight
- Company-wide reporting, documentation, governance and autonomy

## 4. Agent organization
Business operations agents: Sales/Lead Generation, Market Research, Opportunity/Discovery, Proposal/Estimation.
Delivery agents: Project Manager, Business Analyst, Solution Architect, Developer, QA/Tester, UAT/Release.
Cross-cutting: Company Orchestrator, Project Owner, Knowledge Operations, reporting services and governance services.

Agents are logical roles, not necessarily separate services or model instances. Every implemented agent needs a mission, input/output schema, tools, permissions, risk class, validation, escalation and completion criteria.

## 5. MVP acceptance
The MVP is successful when a representative project can progress from approved requirements through design, implementation, evidence-backed QA, defect remediation and customer UAT/sign-off; failures are traceable and recoverable; every phase produces summary and detailed reports; and approval/permission controls are enforced server-side.

## 6. Development architecture
1. Company Control Center — dashboard, projects, tasks, approvals and artifact review.
2. Application API — validated requests, business services and authorization.
3. Workflow Engine — authoritative states, dependencies, retries, approval gates and resume.
4. Agent Runtime — bounded execution, tools, schemas and output validation.
5. Data & Memory — project records, tasks, artifacts, versions, audit and approved knowledge.
6. Model Gateway — provider-neutral model access, routing, policy, limits and usage tracking.

Use a modular monolith initially. Proposed development stack: Python, FastAPI, HTML/CSS/JavaScript, SQLite for local prototype, Ollama for local model experimentation, Git and pytest. Keep the model gateway provider-neutral and preserve a migration path to PostgreSQL and private cloud GPU inference. Avoid requiring Docker for the first iteration and do not disrupt existing projects.

## 7. Failure handling
On failure, persist evidence, alert Project Owner, classify impact, produce RCA, create corrective actions, retry only when safe/idempotent and within policy, escalate authorization-sensitive decisions, and close only after verification.

## 8. Reporting
Every phase generates an executive summary and a detailed report from persisted workflow records and artifacts. Reports include status, risks, decisions, outputs, versions, traceability, defects, approvals and next actions. Do not invent missing facts.

## 9. Governance
Use least privilege, backend-enforced approvals, version-specific authorization, audit records, bounded tools, isolated code execution and authenticated customer sign-off. Agents cannot approve their own work, fabricate evidence or bypass mandatory gates.

## 10. Roadmap
1. Agree architecture and data model.
2. Build core entities, workflow state machine, audit, artifact versioning and approvals.
3. Implement Phase Seven through Phase Eleven in order.
4. Add Project Owner monitoring, RCA and reporting.
5. Test failures, retries, resumption, permissions and version mismatches.
6. Evaluate MVP with synthetic project data.
7. Add full product phases only after MVP acceptance.
