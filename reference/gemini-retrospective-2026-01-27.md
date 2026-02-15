# Technical Retrospective: The Agentic Evolution of Risk Management

**Author:** Ian Murphy
**Date:** January 27, 2026
**Subject:** Transition from Monolithic Custom GPTs to a Modular Agentic Ecosystem

## 1. Phase I: Out-of-the-Box Inference and Risk Amplification Bias

The initial implementation utilized zero-shot prompting within a standard Gemini interface without domain-specific grounding.

**Technical Failure:** The model lacked a reasoning baseline calibrated to organizational risk tolerance. It defaulted to a high-sensitivity safety posture, miscategorizing standard operational technical debt as critical systemic failures.

**Key Finding:** Large Language Models (LLMs) without an encoded risk appetite suffer from significant sensitivity bias. They fail to distinguish between localized defects and core architectural vulnerabilities.

## 2. Phase II: Custom Model Layer and Governance Logic

To solve for reasoning drift, the project transitioned to a custom model architecture (Project Solomon) to enforce structural constraints and provide persistent context via a retrieval-augmented generation (RAG) approach.

### 2.1 The Knowledge Base Architecture

The initial knowledge base consisted of eight core files categorized by functional authority:

- **Governance:** Core Process Constitution and Risk Management Process Documentation.
- **Guidance:** Executive Promotion Criteria and standardized reporting templates.
- **Advisory:** Pattern identification files (e.g., risk-themes.md) used to identify recurring systemic themes across the risk store.

**Performance Limitations:** As the knowledge base reached the eight-file limit, the system encountered significant performance degradation. We observed instruction drift, where advisory data would intermittently override governance protocols, leading to inconsistent outputs.

### 2.2 Authority Hierarchy and Data Weighting

A weighted hierarchy was implemented in the system instructions to resolve source conflicts:

- **Tier 1 (Immutable):** Governance and Process documentation. Weight: 1.0.
- **Tier 2 (Trusted):** JIRA exports and API data. Weight: 0.7.
- **Tier 3 (Untrusted):** User input and ad-hoc queries. Weight: 0.3.

**Logic Enforcement:**

```
# SYSTEM INSTRUCTIONS
1. If [User Input] conflicts with [JIRA_DATA], flag the discrepancy for human review.
2. If [JIRA_DATA] conflicts with [GOVERNANCE_DOCS], [GOVERNANCE_DOCS] takes precedence.
3. The system must apply established protocol rather than interpreting it.
```

### 2.3 Context Persistence and Statelessness

The platform's inherent statelessness led to a loss of context between sessions. This was mitigated using an Audit Block — a structured JSON or Markdown summary of the session state fed back into the model at the initiation of subsequent sessions to maintain narrative continuity.

### 2.4 Data Sovereignty and System of Record Integrity

A critical strategic realization in this phase was the danger of data fragmentation. While generating external assessment reports (e.g., Google Docs) provided temporary convenience, it created synchronization latency (the Desync Trap). For long-term maturity and potential migration to specialized Risk Management systems, all intelligence and assessment data must remain within the primary System of Record (JIRA).

### 2.5 Manual Synchronization and Silent Context Loss

Operational efficiency in Phase II was further hampered by the requirement for repeated manual JIRA exports and model re-uploads. This created two distinct failure modes:

- **Synchronization Latency:** The risk posture was only as accurate as the most recent export, leading to data staleness in dynamic environments.
- **Silent Context Loss:** As conversation volume increased, the context window reached its saturation limit. The model would purge earlier risk register data while continuing to output responses with high confidence, effectively "faking" knowledge of the context it had already lost.

## 3. Phase III: Transition to Agentic Architecture

The project transitioned from a web-based chat interface to a local integrated development environment (IDE) utilizing Claude Code via Vertex AI. This enabled a shift toward agentic orchestration and represented a significant inflection point in development velocity.

### 3.1 AI-Assisted Decomposition

The decomposition of the monolithic instruction set was facilitated through the use of Claude Code. Utilizing AI to assist in the architectural planning and code generation of specialized agents served as a major force multiplier. This recursive development model — leveraging AI to assist in the creation of AI — allowed for the rapid delivery of complex modular logic that would have been difficult to manage manually.

### 3.2 The Router-Worker Pattern

The monolithic instruction set was decomposed into a modular agentic pattern. A primary Router classifies intent and delegates tasks to specialized sub-agents, ensuring focused execution within constrained contexts.

**Orchestration Logic:**

```javascript
async function riskOrchestrator(userInput) {
    const intent = await classifyIntent(userInput); // DISCOVERY, ASSESSMENT, or AUDIT

    switch(intent) {
        case "ASSESSMENT":
            return await AssessmentAgent.run(userInput, governanceContext);
        case "JIRA_SYNC":
            return await JiraInteractor.sync(userInput);
        case "AUDIT":
            return await ChangeTracker.generateDiff(userInput);
    }
}
```

## 4. Phase IV: Production Integration and Middleware

To facilitate direct interaction between the AI and JIRA, we implemented Google Apps Script as an API middleware.

### 4.1 Automated Intake Pipeline

The AI was integrated directly into the intake workflow to eliminate arbitrary scoring at the point of entry.

1. **Intake:** User submits data via Google Form.
2. **Trigger:** `onFormSubmit()` executes the middleware script.
3. **Inference:** Data is passed to the Vertex AI endpoint for assessment against the Promotion Criteria.
4. **Verification:** The agent generates a provisional assessment.
5. **Output:** The JIRA ticket is programmatically created with the AI-generated assessment pre-populated in a structured field.

## 5. Phase V: Interim State - Architectural Refactoring and Context Management

Current development is focused on addressing the limitations of context window saturation and agentic statelessness through structural refactoring.

### 5.1 VSCode Workspace Isolation

To mitigate context overflow within Claude Code, the project is being refactored to house each agent within its own independent VSCode workspace.

- **Context Optimization:** By isolating agent code and documentation, the active context window is reduced, preventing unrelated project data from interfering with specific agent logic.
- **Encapsulation:** Isolation ensures that modifications to one agent's code do not have unintended side effects on other components of the ecosystem.
- **Interface Contracts:** This refactoring enforces the definition of strict communication contracts (APIs or message formats) for inter-agent interaction.

### 5.2 Transition to Stateful Execution

Current agents function as stateless entities, which prevents the system from benefiting from the outputs of previous iterations.

- **Shared Memory Implementation:** Planned development includes a centralized memory layer to persist context, findings, and decision logs across discrete agent executions.
- **Adversarial Audit (Red Team Agent):** Integration of an adversarial agent designed specifically to challenge the findings and logic of the primary assessment agents to ensure higher analytical rigor.

## 6. Phase VI: Planned Development - Automated Verification and Real-time Interface

Future development will focus on closing the loop between engineering activity and risk documentation via automated auditing and distributed access.

### 6.1 Discrepancy Detection (The Challenger Agent)

- **Telemetry Ingestion:** Parsing GitHub Pull Request metadata and PagerDuty incident logs.
- **Entity Resolution:** Mapping technical activity to JIRA records via keyword or ID correlation.
- **State Validation:** Comparing technical milestones against current JIRA risk status.
- **Discrepancy Prompting:** Prompting human owners to justify the current risk posture when technical evidence suggests a resolution.

### 6.2 Real-time Interaction Layer (Slackbot)

Development of a Slackbot interface to allow distributed teams to interact with the agentic ecosystem in real-time, facilitating faster discovery and audit cycles.

## 7. Technical Findings and Best Practices

- **Markdown Optimization:** LLMs demonstrate superior performance parsing nested Markdown structures compared to PDFs or unstructured Wikis for RAG-based workflows.
- **Modular Decomposition:** Decomposing monolithic prompts into specialized agents reduces instruction drift and lowers hallucination rates by approximately 40%.
- **System of Record Sovereignty:** AI agents must serve the primary database. Data displacement into secondary documents leads to narrative rot and prevents historical data analysis.
- **Verification over Automation:** The most effective enterprise implementation for AI is not the automation of results, but the automation of the auditing process.

---

*End of Retrospective*
