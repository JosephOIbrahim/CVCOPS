# 0002. Names and the asset namespace

Status: accepted for the namespace, 9 November 2026. Joe chose `cvcops::`. The licence and public or private
are still open.

## Decision

**The first asset is `cvcops::flow::1.0`.** Joe picked the working-title namespace ("CvCops"). The names table in
`pyproject.toml` already held it, so no code changes. The Python package and the command stay `cvcops` to match.

## Why it matters

A Houdini asset is named `namespace::name::version`, and every .hip file that uses it stores that name. Renaming
the namespace later means every saved scene points at a node that no longer exists. The package name and the
command are easier to change, but they appear in receipts and in SYNAPSE's adapter.

## Options considered

| Option | Asset name | For | Against |
| --- | --- | --- | --- |
| Working title (chosen) | `cvcops::flow::1.0` | One name everywhere: package, command, environment prefix and asset | If the product is renamed, saved scenes keep `cvcops::` |
| Owner namespace (my lean) | `mythlogic::cv_flow::1.0` | Never changes, whatever the product is called or wherever it lives | Says nothing about the tool |
| Umbrella namespace | `synapse::cv_flow::1.0` | Matches the fold in decision 0001 | SYNAPSE is heading toward 2.0; a product name in saved scenes ties them to its future |

## Consequences

The namespace is now the one name that must not move once a scene uses the asset. A later product rename is
cosmetic: the asset's label, the text artists see in the Tab menu, can change freely, and the type name stays
`cvcops::flow`. The fold under SYNAPSE (decision 0001) moves the repository, not the namespace.

## Where names live

The names live in one place, the `[tool.cvcops.names]` table in `pyproject.toml`. The asset builder reads the
namespace from there, the package installer reads the package name, and a guard test checks they agree with
`src/cvcops/capabilities.json`.

## Still open

- The licence for this code, and whether the repository is public or private. Decision 0001's fold-in checklist
  needs both.
