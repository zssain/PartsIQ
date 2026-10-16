"""Package marker for the PartsIQ catalogue tooling namespace.

The catalogue generator/validator/loader live in the nested ``catalog`` package
(tools/catalog/catalog/**), preserved verbatim from the legacy backend. This outer
marker makes ``tools.catalog`` importable so later prompts (F59 versioning) can add
sibling modules without a parallel implementation.
"""
