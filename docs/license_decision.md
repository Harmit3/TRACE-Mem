# Maintainer licensing decision

No root reuse license has been applied. GitHub visibility, an author credit in CFF and inclusion in a source archive do not settle ownership. Identify the holders of rights in code, documentation, illustrations and research data. Check applicable employment, coursework, contributor and third-party obligations separately. Record any confirmed grant and its scope.

| Option for eligible project-owned software | Practical implication |
| --- | --- |
| MIT | Permits broad use and redistribution, including proprietary derivatives, subject to preserving the copyright and permission notice. Short text makes notice compliance straightforward. [License](https://opensource.org/license/mit) |
| Apache-2.0 | Permissive terms include an express contributor patent grant with termination conditions, change notices and applicable NOTICE obligations. Appropriate when those obligations and patent terms are desired. [License](https://www.apache.org/licenses/LICENSE-2.0) |
| GPL-3.0 | Distribution of covered modifications or combined works can require corresponding source and compatible terms. Suitable if downstream software freedom is a priority. Evaluate dependency compatibility and the intended distribution first. [License](https://www.gnu.org/licenses/gpl-3.0.en.html) |

For a small research library prioritizing reuse, MIT is a candidate once ownership is confirmed. A permissive software license need not cover the manuscript or datasets. Keep upstream terms with the material they cover. The beta bundles the pinned CPython embedded runtime and its incorporated notices. Ollama, .NET, VC++ runtimes, MiniLM, DeBERTa, PyTorch and Qwen are external prerequisites. No model weights are licensed by this release. Source packages retain original synthetic research records and numeric summaries. External Memora and LongMemEval data, benchmark keys and private annotations stay outside. See [dataset provenance](data_audit.md), [dependency and redistribution review](step43.md), and the [CPython license](https://docs.python.org/3.14/license.html).

Before distributing the Windows executable, approve the exact license scope, upstream notices and binary distribution terms. Review signing and clean-system testing separately. The unsigned package remains private.
