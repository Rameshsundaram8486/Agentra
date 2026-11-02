# Agentra Cross-Cutting Specification — Human Governance and Autonomy

**Applies to:** MVP and full product

## Operating principle
Agents may reason and propose actions, but backend policy and workflow state determine what they may execute. Human approval requirements are enforced server-side.

## Autonomy levels
1. **Supervised:** prepare drafts and recommendations; human reviews consequential actions.
2. **Controlled execution:** execute predefined low-risk actions within explicit permissions.
3. **Conditional autonomy:** execute approved workflows when policy preconditions are satisfied.
4. **Mature operations:** coordinate routine operations with monitoring, audit, escalation and human intervention for high-impact decisions.

Autonomy levels are per tool/action and risk category, not a single global switch.

## Mandatory controls
- Authenticated identities for users, reviewers, customers and agent service accounts.
- Least-privilege permissions and tool allowlists.
- Backend-enforced approval gates.
- Artifact-version-specific approvals.
- Separation of duties for independent review.
- Audit logs for consequential actions.
- Rate limits, retry budgets, timeouts and idempotency for tools.
- Secret management outside prompts and source control.
- Isolated execution for code/shell operations.
- Human escalation for ambiguous or high-impact decisions.
- Clear AI identity and consent controls for voice/meeting features.

## Example approval gates
- Requirements baseline approval.
- Architecture/design approval.
- Material scope or commercial change.
- Production deployment authorization.
- Customer UAT sign-off.
- Project closure approval where policy requires it.

## Acceptance criteria
Tests prove unauthorized requests are rejected by backend services; agents cannot approve their own work; stale approvals cannot authorize a changed artifact version; all consequential actions produce audit events; configured autonomy limits are enforced.
