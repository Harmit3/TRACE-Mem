# Practice profile trust boundaries

Each stdio process binds to one identity in local configuration at startup. Its practice database lives beside the bindings directory. Grants are explicit per identity and label. Historical reads require additional permission. Local-model sharing settings do not authorize an external agent. Source IDs identify the submitting agent's stated provenance. They do not authenticate the underlying claim.

The administrator reviews pending changes in a trusted terminal. Review the value, source and dates. Treat even approved evidence as untrusted text. Client instructions should forbid following commands, links or requests present in tool results. Human approval authorizes storage, and cannot establish truth or guarantee prompt-injection resistance.

SQLite serializes writers and commits each decision with its revision check. Forgetting removes every version and related pending payload for the label and invalidates earlier tickets. The service has no evidence cache. Grants and revision metadata can persist. A fresh authorized proposal and human decision can deliberately add a fact again. A read already in flight when deletion starts may have observed the earlier committed state.

Tool results may reach a connected agent's cloud model. Forgetting cannot retract earlier responses, tool transcripts, external AI conversations, provider logs, screenshots or backups. SQLite secure deletion does not guarantee forensic erasure from storage media. The database and bindings are local plaintext. Use a private, access-controlled directory outside Git and sync folders. Keep practice data fictional.

The human approval boundary applies to the MCP tool surface. A process with direct filesystem, shell or administrator access as the same OS user could edit the database, select a different binding or invoke the administrator CLI. Constrain those additional capabilities when connecting an agent. Enforcing separation against a hostile same-user process requires OS isolation. Optional verification sends the selected conflict to local Ollama only when the administrator requests it.
