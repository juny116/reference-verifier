# Project history

This project continues Junyeob Kim's [infolumi-reference-search](https://github.com/juny116/infolumi-reference-search), retaining its Git history through `e1c7af5` and its legacy source files. The new product name is Reference Verifier. The original application focused on PubMed reference lookup; the new package introduces multiple metadata sources, explicit source disagreements, optional constrained AI extraction, and user-selected correction exports.

The original README and dependency list are preserved as `legacy-readme.md` and `legacy-requirements.txt`. New development uses `reference_verifier/` and `tests_v2/`; old modules and tests are historical and may require different dependencies. No new license is asserted by this refactor.

## Visual workspace update

The latest revision redesigns the existing review flow into a light three-pane interface: status navigation, a searchable reference list, and a focused comparison panel. It keeps the verification engine and explicit-selection export behavior from the preceding migration. The new repository name and visual identity do not reset the project’s earlier development history.
