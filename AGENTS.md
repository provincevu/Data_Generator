# Project instructions

### **Persistent decision records**

Record important project decisions so that their reasoning and context remain available independently of chat history.

- Record decisions when they are made, especially decisions where the user has been deeply involved or has provided substantial direction. Such decisions should be explicitly marked as **important**.
- Each decision record should include:
  - **Decision:** a brief description of what was decided.
  - **Date:** when the decision was made.
  - **Problem addressed:** the problem or question that led to the decision.
  - **Current system state:** the relevant state of the system at the time of the decision.
  - **Business requirements:** the underlying business or project requirements motivating the decision.
  - **Alternatives considered:** the meaningful alternatives that were evaluated.
  - **Rationale:** why this option was selected, including:
    - the criteria used to evaluate the alternatives;
    - the reasoning and arguments supporting the decision;
    - the assumptions underlying the decision;
    - the evidence supporting those arguments and assumptions.
  - **Consequences:** the expected positive and negative consequences of the decision.
  - **Reconsideration conditions:** the conditions or circumstances under which the decision may no longer be appropriate and should be reviewed.
- Do not record decisions merely as conclusions. Preserve enough context to understand **why** the decision was made and **when it should be reconsidered**.
- When a decision changes, update its record rather than silently superseding it elsewhere in code, experiments, or documentation.
- If a decision appears unreasonable, outdated, or inconsistent with the project's current needs, discuss and review it before changing the durable decision record.
- Record project decisions in `docs/decisions.md`.
- Before taking an action that may be affected by a previous decision, review the relevant entries in `docs/decisions.md` first. Ensure that the planned action does not unintentionally conflict with decisions made previously.
- If the planned action appears to conflict with an existing decision, do not silently override the previous decision. Review the conflict, discuss whether the decision should be changed, and update `docs/decisions.md` when the decision is formally revised.