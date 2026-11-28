# Developing TRACE-Mem

Use CPython 3.14 in a separate virtual environment. The offline console and numeric reproduction require only the standard library. For the full tests, use the [reference environment and commands](docs/technical_release.md), the [training dependencies](requirements-training.txt), and [semantic dependencies](requirements-semantic.txt). Browser regressions additionally need Playwright and Edge. Cached checkpoints and local Ollama are needed for live model checks.

Run `python -m pytest -q` from the source root. On a system with a restricted temporary directory, pass a new disposable directory such as `--basetemp=results/test-scratch`. Pytest owns the selected directory. Run `python -m scripts.verify_manuscript` after changing a numerical summary. Check staged changes with `python scripts/check_staged.py`.

Use fictional profiles for bug reports. Include the revision, platform, command, expected behavior and observed behavior. Keep personal profiles, model weights, benchmark texts and oracle labels outside Git. Preserve frozen protocols, hashes, controller weights, negative outcomes and original results. Use new versioned artifacts for changed experiments.

For a pull request, describe the change, the tests run, any failures, and whether a scientific or privacy boundary changed. Disclose AI assistance and identify the human review performed. Maintainers must resolve reuse rights before accepting contributions that require new license grants.
