# Windows desktop beta 0.41.0

This private x64 portable build uses a small .NET Framework Windows Forms launcher, the system browser and an isolated CPython embedded runtime. A browser-only script would retain a Python prerequisite. A separate bundled browser would duplicate a large runtime for the existing interface. The embedded distribution provides an isolated import path and runs SQLite and the application without pip, Git, a repository checkout or Codex. The portable package uses lexical and exact-slot retrieval. Optional development-only scientific packages and model weights are excluded.

Extract the ZIP, open **TRACE-Mem Workspace.exe**, and keep its launcher window open. The browser opens on a dynamically allocated IPv4 loopback port. A session mutex and a profile lock protect against duplicate writers. Closing the launcher closes the host pipe and requests shutdown. The Start Menu and desktop shortcut buttons are optional. Users can navigate forms by keyboard, select offline lookup without a model, and choose model and strategy independently. New responses identify direct lookup versus generation. The prior research dashboards are collapsed by default. See the [included user guide](../desktop/START%20HERE.txt) for troubleshooting, updating, recovery and removal.

## Build and verification

Download the official python-3.14.0-embed-amd64.zip from python.org/ftp/python/3.14.0. Input SHA-256 is 8d4d3590c10449d78aa4375f534e6d5f3027d67fdc362dd1a882279db6f90fdf. From the Windows source checkout run:

```powershell
python -m scripts.build_workspace_desktop results/step41/python-3.14.0-embed-amd64.zip results/step41/TRACE-Mem-Workspace-0.41.0-win-x64.zip
python -m scripts.workspace_package_smoke results/step41/TRACE-Mem-Workspace-0.41.0-win-x64.zip
```

The build refuses an existing output. It compiles the launcher with Windows Framework64 csc, copies allowlisted source modules, UI assets and archived public numeric reports, and retains the official CPython license and incorporated notices. The embedded path is configured for this app. Microsoft VC runtime DLLs are excluded and must be available on the target system. The ZIP is unsigned and private. Source reuse rights and citation attribution remain maintainer decisions before publication. The compiler and ZIP timestamps can change checksums on rebuild. [CPython embedding guidance](https://docs.python.org/3.14/using/windows.html#the-embeddable-package) · [Python license](https://docs.python.org/3.14/license.html)

Measured artifact: 11,962,630 bytes. SHA-256: 93bd07846ab4ea3f6d233c532e3aed27acb0ec061981871a9edb970cbb87f538. The smoke test extracted twice into temporary directories outside Git, loaded both models, confirmed a proposed memory in Edge, reopened chat history after upgrade, checked date-specific recall and forgetting, occupied the previous port, and exercised graceful shutdown, ZIP CRC and SQLite integrity. Temporary program files could be removed after shutdown. A disposable corrupt encrypted snapshot refused startup without mutation. Starting a new profile succeeded. The native executable was separately launched on the owner's desktop and both models were discoverable. Automated tests did not create or remove shortcuts on the owner's desktop. Absent Ollama was tested by simulated connection refusal, plus actual offline lookup on the packaged backend. A clean Windows machine without developer tools has not been tested.

All 179 tests and 36 subtests passed with one prior AnyIO warning. The archive reproduction verified 27,000 history rows, 2,300 family rows, 230 summaries and 184 paired intervals.

## Privacy controls and scope

The desktop profile has one explicit full-control user ACL. Current-user Windows DPAPI protects the memory JSON payload. Valid existing plaintext memory in the beta profile is replaced atomically after validation. Chat SQLite remains plaintext in the restricted profile directory. Schema v2 transactionally excludes old turns from future model context. A direct lookup remains visible in the transcript and is excluded from subsequent generated prompts. Confirmed duration minutes is the only synthesis field: a user explicitly opts in, a fresh authorized snapshot resolves its ID, and the server accepts only a bounded numeric representation under a fixed label. Free-text saved values cannot become synthesis context through that projection. Pinning is independent of sharing. This deliberately limits the earlier experimental RAG mode for free-form generation. Historical benchmark results refer to their pinned software.

The frozen injection cases are inert fictional requested outputs. All three pinned note variants were absent from the generated requests' selected evidence and replies in both repetitions for each model. This tests a specific data boundary. It does not establish general prompt-injection resistance. Users can enter misleading instructions directly into chat, numeric facts can be false, old tabs or backups can contain forgotten content, and administrators or same-user programs can access a live profile. Recovery starts a separate profile and preserves damaged files. Backups restored by a user can predate deletion.

## Beta decision

Ready for supervised local testing on this Windows machine with reviewed, low-sensitivity inputs. General distribution still requires rights and attribution review, signed builds, clean-system testing, accessibility review, broader evidence on extraction and synthesis, and independent security review. No public release or model downloads were performed. [Matched model pilot](../research/workspace41/report.md)

For the subsequent private 0.42.0 build, profile migration, typed synthesis and optional local encoder, see the [Step 42 handoff](windows_beta_042.md).
