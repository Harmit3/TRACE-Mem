"""Canonical mechanism graph and normalized-text checks for independent fixture review."""

import re
import unicodedata

from trace_mem.validation_v2 import signature


def normalized_text(text, bindings):
    value = unicodedata.normalize("NFKC", text).casefold()
    for label, token in sorted(bindings.items(), key=lambda pair: -len(pair[0])):
        label = unicodedata.normalize("NFKC", label).casefold()
        value = re.sub(r"(?<!\w)" + re.escape(label) + r"(?!\w)", f" {token.casefold()} ", value)
    value = re.sub(r"\b\d+(?:[./-]\d+)*\b", " number ", value)
    return " ".join(re.findall(r"\w+", value))


def mechanism_hash(nodes):
    """Hash ordered controlled-vocabulary transitions after renaming entity/slot/value IDs."""
    aliases = [{}, {}, {}]
    canon = []
    for i, node in enumerate(nodes):
        entity, slot, value, action, temporal, authority, parents = node
        if (not isinstance(parents, (tuple, list)) or len(set(parents)) != len(parents)
                or any(type(j) is not int or not 0 <= j < i for j in parents)):
            raise ValueError("Mechanism edges must refer to prior unique nodes")
        terms = [table.setdefault(x, len(table)) for table, x in zip(
            aliases, (entity, slot, value), strict=True)]
        canon.append((*terms, action, temporal, authority, sorted(parents)))
    if not canon:
        raise ValueError("Mechanism graph is empty")
    return signature(canon)


def shingles(text):
    terms = text.split()
    if len(terms) < 5:
        return {tuple(terms)} if terms else set()
    return {tuple(terms[i:i + 5]) for i in range(len(terms) - 4)}


def overlap(candidate_text, candidate_graph, archive):
    matches = []
    x = shingles(candidate_text)
    for name, text, graph in archive:
        y = shingles(text)
        ratio = len(x & y) / len(x | y) if x or y else 0
        if candidate_graph == graph or candidate_text == text or ratio >= .8:
            matches.append((name, ratio, candidate_graph == graph))
    return matches
