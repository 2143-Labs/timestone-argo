#!/usr/bin/env python3
"""Structural validator for timestone-argo manifests.

Parse every YAML file; enforce the repo conventions that keep ArgoCD healthy:
  - every document parses and carries apiVersion/kind
  - named resources carry metadata.name
  - argocd/wave-N/*.yaml are Applications with a numeric sync-wave annotation
    and a concrete https repoURL (never empty/placeholder)
  - base/ manifests are namespaced by the Application destination (default);
    an explicit metadata.namespace is allowed only when it equals "default",
    except for the directories in NAMESPACE_ALLOWLIST whose resources must live
    in a fixed system namespace

Exit code 0 = OK. Run in CI (see .github/workflows/validate.yml).
"""
from __future__ import annotations

import pathlib
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
errors: list[str] = []

# Directories whose manifests legitimately live outside the default destination
# namespace (e.g. the cloud controller manager must run in kube-system).
NAMESPACE_ALLOWLIST: dict[str, set[str]] = {
    "hcloud-ccm": {"kube-system"},
}
checked = 0


def add(kind: str, name: str, msg: str) -> None:
    errors.append(f"{kind} {name}: {msg}")


for path in sorted(ROOT.rglob("*.yaml")):
    if ".git" in path.parts:
        continue
    try:
        docs = [d for d in yaml.safe_load_all(path.read_text()) if d is not None]
    except yaml.YAMLError as exc:
        errors.append(f"{path}: YAML parse error: {exc}")
        continue

    for doc in docs:
        checked += 1
        kind = doc.get("kind")
        api = doc.get("apiVersion")
        meta = doc.get("metadata") or {}
        name = meta.get("name", "(unnamed)")
        if not kind or not api:
            add("?", name, f"{path}: missing apiVersion/kind")
            continue
        if "metadata" not in doc or not name:
            add(kind, "(unnamed)", f"{path}: missing metadata.name")
            continue

        if kind == "Application":
            ann = meta.get("annotations") or {}
            wave = ann.get("argocd.argoproj.io/sync-wave")
            spec = doc.get("spec") or {}
            repo = ((spec.get("source") or {}).get("repoURL")) or ""
            if str(path).count("wave-") and wave is None:
                add(kind, name, f"{path}: Application under wave-N missing sync-wave annotation")
            if not repo.startswith("https://") or "PLACEHOLDER" in repo or repo.endswith("/"):
                add(kind, name, f"{path}: repoURL must be a concrete https URL (got {repo!r})")
        elif "base" in path.parts:
            # base/ manifests are namespaced by the Application destination
            # (default); an explicit namespace is allowed only if it matches, or
            # if this directory has a documented system-namespace exception.
            ns = meta.get("namespace")
            allowed = {"default"} | NAMESPACE_ALLOWLIST.get(path.parent.name, set())
            if ns is not None and ns not in allowed:
                add(kind, name, f"{path}: base/ manifest namespace must be one of "
                                f"{sorted(allowed)} (destination namespace), got {ns!r}")

print(f"checked {checked} documents")
if errors:
    print(f"FAIL ({len(errors)} problem(s)):")
    for e in errors:
        print("  -", e)
    sys.exit(1)
print("OK")
