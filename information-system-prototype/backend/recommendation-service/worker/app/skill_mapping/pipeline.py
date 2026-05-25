"""
Map extracted resume skills to ESCO skills using an ADAPTIVE HYBRID
cosine pipeline.

For every resume skill the score against each ESCO concept is

    hybrid(uri) = w_label * max_label_cos(uri) + w_concat * concat_cos(uri)

where (w_label, w_concat) is chosen per input skill by `get_hybrid_weight`:

  - Concrete tools / products / programming languages
        (e.g. "python", "excel", "docker") -> (1.0, 0.0)
        Bare label match is enough; description signal is noise.
  - Generic single-word competencies that ESCO splits across many
    domain-specialized labels (e.g. "leadership", "management",
    "nursing", "office") -> (0.7, 0.3)
        Description carries most of the disambiguating signal.
  - Everything else -> (0.85, 0.15)
        Mostly label-driven, light description tie-break.

  - max_label_cos(uri): the multi-vector retrieval used by the cosine-only
    variant — every preferredLabel and altLabel is a separate retrievable
    string and we take the max cosine across all entries belonging to the
    URI.
  - concat_cos(uri): cosine against ONE per-URI document built by
    concatenating preferredLabel + altLabels + description. Captures
    semantic signal the bare labels miss (definition, examples, scope).

Stage 1 — retrieval: encode the label corpus (multi-vector) and the
         concat corpus (one row per URI) once with
         google/embeddinggemma-300m. EmbeddingGemma uses task-specific
         prompt prefixes — applied automatically for queries and docs.
Stage 2 — filter: drop adjective-only fragments and ESCO candidates
         whose label commits to a domain (e.g. "leadership in nursing")
         that the resume context doesn't justify.
Stage 3 — select: take the top-1 surviving candidate; keep it if its
         hybrid score >= COSINE_THRESHOLD, otherwise drop the skill.

This module is the reusable v3 pipeline (originally a batch CSV enrichment
script). The CSV/CLI batch driver has been dropped — the worker drives it
online via `app.skill_mapping.mapper.EscoSkillMapper`, which builds the index
once on startup and maps one user profile at a time. The retrieval / hybrid /
domain-filter / short-circuit logic below is unchanged.

EmbeddingGemma is a gated model — accept its license at
https://huggingface.co/google/embeddinggemma-300m and authenticate
(set HF_TOKEN env var).
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer

EMBED_MODEL = "google/embeddinggemma-300m"
DEFAULT_TOP_K = 1
COSINE_THRESHOLD = 0.6

# Adaptive hybrid weights — picked per input skill by `get_hybrid_weight`.
# These constants only define the three branches it returns.
HYBRID_WEIGHTS_CONCRETE: tuple[float, float] = (1.0, 0.0)
HYBRID_WEIGHTS_GENERIC: tuple[float, float] = (0.7, 0.3)
HYBRID_WEIGHTS_DEFAULT: tuple[float, float] = (0.85, 0.15)

# Concrete tools / products / programming languages: their preferredLabel
# (or an altLabel) IS the canonical name, so cosine against the label
# alone identifies the concept. Pulling in description here mostly hurts
# (definitions tend to talk about adjacent concepts).
#
# Curated seed list — extend as new tool names surface. Lower-case only;
# matched as exact strings against `input_skill.lower()`.
CONCRETE_TOOLS_SET: frozenset[str] = frozenset({
    # Programming languages
    "python", "java", "javascript", "js", "typescript", "ts",
    "c", "c++", "c#", "go", "golang", "rust", "ruby", "php",
    "swift", "kotlin", "scala", "perl", "r", "matlab", "sql",
    "html", "html5", "css", "css3", "sass", "scss", "less",
    "bash", "shell", "powershell", "objective-c", "f#", "vba",
    "dart", "lua", "julia", "groovy", "haskell", "clojure", "elixir",
    # Frameworks / libraries
    "react", "react.js", "reactjs", "angular", "angular.js", "angularjs",
    "vue", "vue.js", "vuejs", "svelte", "ember", "jquery",
    "django", "flask", "fastapi", "spring", "spring boot",
    "rails", "ruby on rails", "laravel", "symfony", "express",
    "express.js", "node", "node.js", "nodejs", "next.js", "nextjs",
    "nuxt", "gatsby", "redux", "bootstrap", "tailwind", "tailwindcss",
    # ML / data
    "tensorflow", "pytorch", "keras", "scikit-learn", "sklearn",
    "pandas", "numpy", "scipy", "matplotlib", "seaborn", "jupyter",
    "huggingface", "hugging face", "opencv", "nltk", "spacy",
    "transformers", "langchain", "xgboost", "lightgbm",
    # DevOps / infra
    "docker", "kubernetes", "k8s", "jenkins", "gitlab", "github",
    "bitbucket", "circleci", "travis ci", "terraform", "ansible",
    "puppet", "chef", "vagrant", "helm", "prometheus", "grafana",
    "splunk", "datadog", "sentry", "nginx", "apache",
    # Cloud
    "aws", "azure", "gcp", "google cloud", "heroku", "vercel",
    "netlify", "digitalocean", "ec2", "s3", "lambda", "cloudfront",
    # Databases
    "mysql", "postgresql", "postgres", "mongodb", "redis",
    "elasticsearch", "sqlite", "mariadb", "cassandra", "neo4j",
    "firebase", "firestore", "dynamodb", "sql server", "mssql",
    # Office / productivity
    "excel", "ms excel", "microsoft excel", "word", "ms word",
    "microsoft word", "powerpoint", "ms powerpoint",
    "microsoft powerpoint", "outlook", "onenote", "sharepoint",
    "ms teams", "microsoft teams", "google docs", "google sheets",
    "google slides", "notion", "confluence", "jira", "asana",
    "trello", "slack", "zoom",
    # Design / creative
    "photoshop", "adobe photoshop", "indesign", "adobe indesign",
    "premiere", "premiere pro", "after effects", "lightroom",
    "figma", "sketch", "adobe xd", "canva", "invision",
    "3ds max", "maya", "revit", "sketchup", "blender", "cinema 4d",
    # Business / analytics
    "salesforce", "sap", "sap hana", "workday", "hubspot",
    "dynamics 365", "ms dynamics", "microsoft dynamics",
    "quickbooks", "xero", "sage", "tableau", "power bi", "powerbi",
    "looker", "qlik", "qlikview",
    # OS
    "linux", "ubuntu", "centos", "debian", "fedora", "red hat",
    "rhel", "windows", "windows server", "macos", "mac os",
    "unix", "ios", "android",
    # Versioning / file formats / misc concrete
    "git", "svn", "mercurial", "json", "xml", "yaml", "csv",
    "rest", "graphql", "grpc", "soap", "websocket",
})

# Generic single-word competencies whose ESCO label retrieval pulls in
# many domain-specialized variants ("X in nursing", "Y of warehouse").
# Description signal helps disambiguate — populated at runtime from the
# generic-topic-noun JSON cache built by `map_esco_gemma.py`. Falls back
# to an empty set if the cache file is missing.
GENERIC_TOPIC_NOUNS: frozenset[str] = frozenset()

# Short-circuit overrides: inputs whose ESCO mapping is so well-known
# (or so easy for cosine retrieval to misroute) that we hard-code the
# answer instead of running the embedding/threshold/domain-filter
# pipeline. Covers spoken languages, programming languages with
# dedicated ESCO concepts, and a handful of umbrella concepts that
# sensibly absorb HTML/XML/regex/shell/Linux/MS Word style inputs.
#
# Lower-case keys only; matched as exact strings against
# `input_skill.lower().strip()`. URIs were verified against the local
# skills_en.csv. Inputs without a meaningful ESCO concept (Kotlin, Go,
# Rust, Dart, Node.js, React, Vue, Django, Flask, Laravel, Spring,
# Rails, .NET, Lua, Fortran, Ada, ...) are deliberately absent — they
# fall through to the standard cosine pipeline.
SHORT_CIRCUIT_OVERRIDES: dict[str, str] = {
    # ---- Spoken / written languages (ESCO skillType=language) ----
    "arabic":      "http://data.europa.eu/esco/skill/33859d93-987c-4caa-a0a9-6159ea7bbc2a",
    "bulgarian":   "http://data.europa.eu/esco/skill/d5fd4958-4ca6-4d06-845f-713e2c459612",
    "chinese":     "http://data.europa.eu/esco/skill/1fe42b38-cd42-4fc7-ae77-14e4c9e96295",
    "croatian":    "http://data.europa.eu/esco/skill/6bc58e91-1827-4dc7-a9cf-2311edcba0ec",
    "czech":       "http://data.europa.eu/esco/skill/da0795a7-6866-4afc-81ed-5e3aa398f058",
    "danish":      "http://data.europa.eu/esco/skill/273a28d6-1bd3-4d13-a906-3d75c1cfdfc1",
    "dutch":       "http://data.europa.eu/esco/skill/cad4f44b-28a8-4448-86e5-7389e5ebf3eb",
    "english":     "http://data.europa.eu/esco/skill/6d3edede-8951-4621-a835-e04323300fa0",
    "finnish":     "http://data.europa.eu/esco/skill/0e3493f4-0cad-4fbc-8e02-025f169b8114",
    "french":      "http://data.europa.eu/esco/skill/e747e77e-0ea1-4001-8b07-1d11946b5f1b",
    "german":      "http://data.europa.eu/esco/skill/4812a4ea-dc55-4dc6-b9b0-4a59bba2c647",
    "greek":       "http://data.europa.eu/esco/skill/ea4ebfa1-e17a-4416-ac54-955f33e6ade7",
    "hebrew":      "http://data.europa.eu/esco/skill/8a45f04a-cd28-4ac1-8e8b-ecfd21be0b18",
    "hindi":       "http://data.europa.eu/esco/skill/d93a7370-bf56-43f5-be54-e108f8ec3107",
    "hungarian":   "http://data.europa.eu/esco/skill/ddd3596a-43f3-402e-960a-5f79362a8609",
    "italian":     "http://data.europa.eu/esco/skill/87219dfe-a21c-4160-8cc8-1eabf9b16b44",
    "japanese":    "http://data.europa.eu/esco/skill/39c675c4-af13-49db-bbed-cf762102f85e",
    "korean":      "http://data.europa.eu/esco/skill/f9bc2890-d1f2-4a83-bd7b-b150a7679c79",
    "malay":       "http://data.europa.eu/esco/skill/1f90c205-f869-4dcf-a374-c4fdeded9cbc",
    "norwegian":   "http://data.europa.eu/esco/skill/829f6eb5-0b26-4152-8eb3-82dd32b2b6f2",
    "polish":      "http://data.europa.eu/esco/skill/f3e9b964-0c2d-46c4-a895-8b3583054d69",
    "portuguese":  "http://data.europa.eu/esco/skill/584c13e8-fd06-4ca3-a45b-cca5b2f147a7",
    "romanian":    "http://data.europa.eu/esco/skill/4b9f1ae5-0ee6-4738-8999-9b8191fba808",
    "russian":     "http://data.europa.eu/esco/skill/6891bbce-20bf-4afc-bd5e-75bdf54c0165",
    "serbian":     "http://data.europa.eu/esco/skill/c5cb0cc1-c40b-4544-a21c-8472f0b5c14a",
    "slovak":      "http://data.europa.eu/esco/skill/246980fe-6222-4852-ade8-b372f7e0fd20",
    "spanish":     "http://data.europa.eu/esco/skill/14ee9f76-3524-43d5-8a1a-5ba8283f8bd7",
    "swedish":     "http://data.europa.eu/esco/skill/7ee51257-8947-4b69-9bdf-322baf0a6398",
    "turkish":     "http://data.europa.eu/esco/skill/aa66a033-8522-40e9-a5c0-ff2593e2669c",
    "ukrainian":   "http://data.europa.eu/esco/skill/354b948c-7eef-4ebc-bfd6-f60d7d5acb62",
    "vietnamese":  "http://data.europa.eu/esco/skill/bf60009d-8afb-4306-9b0d-cfe2f66ab08f",
    # ---- Other ESCO-listed languages (preferredLabel matches) ----
    "bengali":     "http://data.europa.eu/esco/skill/ede98e07-f07d-41bc-99b0-f88bf0dad438",
    "urdu":        "http://data.europa.eu/esco/skill/bc546a09-1103-4184-b757-3508ef5f8490",
    "persian":     "http://data.europa.eu/esco/skill/58cabf75-2520-4358-a210-2cbc628f4aa2",
    "punjabi":     "http://data.europa.eu/esco/skill/e05b9e06-d298-4646-b762-acbd485a20e9",
    "tamil":       "http://data.europa.eu/esco/skill/e9e9b625-f59f-4bda-952d-1f9831e6dfda",
    "telugu":      "http://data.europa.eu/esco/skill/64fe09ac-f419-4c04-8997-d1dde2e31bfc",
    "catalan":     "http://data.europa.eu/esco/skill/8ee2b6f2-7017-4b9a-9de2-4dedf0711394",
    "basque":      "http://data.europa.eu/esco/skill/a28fa5f1-be5b-4608-8376-acea8c2f8cb1",
    "galician":    "http://data.europa.eu/esco/skill/66212ff2-34b9-4812-be58-f53a0b751863",
    "welsh":       "http://data.europa.eu/esco/skill/8dbd15c6-ecf0-468c-8ae1-f6eb360743dd",
    "irish":       "http://data.europa.eu/esco/skill/8f4c0fe6-10c7-409e-92d6-245f46728209",
    "latvian":     "http://data.europa.eu/esco/skill/5de39924-769c-4301-82a5-525358dffe50",
    "lithuanian":  "http://data.europa.eu/esco/skill/b3950b87-a980-4cd4-a795-be8a9b63661d",
    "estonian":    "http://data.europa.eu/esco/skill/1b7e6f56-bc73-4bcc-81ae-09252175d418",
    "slovenian":   "http://data.europa.eu/esco/skill/9ace3aae-aeae-4ed6-b625-26bc58345554",
    "maltese":     "http://data.europa.eu/esco/skill/cb50f9cd-3638-409b-8f93-befaf17d313e",
    "albanian":    "http://data.europa.eu/esco/skill/f1a08ec9-32d2-4e52-ba4a-66e049019be8",
    "macedonian":  "http://data.europa.eu/esco/skill/15f261e6-4379-437e-b137-b0c473ae3e74",
    "bosnian":     "http://data.europa.eu/esco/skill/a9fdd2c9-4295-4407-ba3c-1547cbce40a2",
    "belarusian":  "http://data.europa.eu/esco/skill/6f55e44d-4494-4079-9b8d-01ac6912529e",
    "georgian":    "http://data.europa.eu/esco/skill/b2c1f90a-72ce-4499-ab9a-a9a5c9355d5b",
    "armenian":    "http://data.europa.eu/esco/skill/fcbcdf4c-d079-4010-ab4b-8356fbfa5096",
    "azerbaijani": "http://data.europa.eu/esco/skill/5bfce8e7-6f22-4e67-9018-0e4161620f3a",
    "kazakh":      "http://data.europa.eu/esco/skill/f37dbb3c-dafc-4835-86d1-de9615626f9b",
    # ---- Spoken-language aliases / spelling variants ----
    "mandarin":    "http://data.europa.eu/esco/skill/1fe42b38-cd42-4fc7-ae77-14e4c9e96295",  # -> Chinese
    "cantonese":   "http://data.europa.eu/esco/skill/1fe42b38-cd42-4fc7-ae77-14e4c9e96295",  # -> Chinese
    "farsi":       "http://data.europa.eu/esco/skill/58cabf75-2520-4358-a210-2cbc628f4aa2",  # -> Persian
    "castilian":   "http://data.europa.eu/esco/skill/14ee9f76-3524-43d5-8a1a-5ba8283f8bd7",  # -> Spanish
    "flemish":     "http://data.europa.eu/esco/skill/cad4f44b-28a8-4448-86e5-7389e5ebf3eb",  # -> Dutch

    # ---- Programming languages with dedicated ESCO concepts ----
    "python":         "http://data.europa.eu/esco/skill/ccd0a1d9-afda-43d9-b901-96344886e14d",
    "java":           "http://data.europa.eu/esco/skill/19a8293b-8e95-4de3-983f-77484079c389",
    "javascript":     "http://data.europa.eu/esco/skill/3cd569a2-4f88-4c1e-9995-8dce8c5e51a7",
    "typescript":     "http://data.europa.eu/esco/skill/867137fb-ff1b-4ca3-99f3-cb6969aa2c68",
    "c++":            "http://data.europa.eu/esco/skill/b633eb55-8f1f-4ae6-ab4c-2022ffe2cb7f",
    "c#":             "http://data.europa.eu/esco/skill/4c016b68-4116-468c-9dc6-42710c239e4a",
    "php":            "http://data.europa.eu/esco/skill/4350c38d-0fe9-4ca7-bab9-40ed7f72b04f",
    "scala":          "http://data.europa.eu/esco/skill/ffddfc7c-a9dd-449f-9e96-882dc447c8b6",
    "perl":           "http://data.europa.eu/esco/skill/401eb8d8-6daa-4f8b-90ad-60afc71eb4f8",
    "r":              "http://data.europa.eu/esco/skill/51586df8-1c46-4b47-8583-773cb63bf00b",
    "matlab":         "http://data.europa.eu/esco/skill/c3a03c5a-c260-4c26-9b9a-873abb396f4d",
    "sql":            "http://data.europa.eu/esco/skill/598de5b0-5b58-4ea7-8058-a4bc4d18c742",
    "css":            "http://data.europa.eu/esco/skill/e5d1f825-60ed-4bdd-872a-e748c387f777",
    "objective-c":    "http://data.europa.eu/esco/skill/9973a5a2-7822-4161-99e9-95c781eb63f8",
    "visual basic":   "http://data.europa.eu/esco/skill/13bdd41a-2a18-441f-96db-41252c519413",
    "groovy":         "http://data.europa.eu/esco/skill/52cf3037-ab53-4806-85ed-7fd21ea7f6a1",
    "haskell":        "http://data.europa.eu/esco/skill/000f1d3d-220f-4789-9c0a-cc742521fb02",
    "erlang":         "http://data.europa.eu/esco/skill/034c29fa-c3ba-45ea-b8f3-bf8e3705e386",
    "lisp":           "http://data.europa.eu/esco/skill/0de61385-de6d-4146-ba32-1cc1bc102220",
    "cobol":          "http://data.europa.eu/esco/skill/def007fa-5fed-4a5f-91a2-b0d7e3db1be1",
    "abap":           "http://data.europa.eu/esco/skill/eb0e5615-1575-4a86-a1a2-7d39595033c5",
    "apl":            "http://data.europa.eu/esco/skill/58d7a289-dafd-4363-833f-d1dc4140885e",
    "ajax":           "http://data.europa.eu/esco/skill/b4dc6e4f-dc7d-445f-8ce2-d7b9d225e282",
    "asp.net":        "http://data.europa.eu/esco/skill/56a7f561-1d55-43c9-9cd7-36a0a9bc6c50",
    "coffeescript":   "http://data.europa.eu/esco/skill/993b1e23-f2de-4bd8-b33f-f86dde1c8e9d",
    "ruby":           "http://data.europa.eu/esco/skill/0ccdfe98-f845-4598-84a1-3dca66e9d9a3",
    "swift":          "http://data.europa.eu/esco/skill/be80acfc-b6f2-4411-9b8d-b19d9cd2556a",
    "pascal":         "http://data.europa.eu/esco/skill/e8b89eb6-51e8-4c3a-babb-88b2e110376b",
    "smalltalk":      "http://data.europa.eu/esco/skill/42ed3bfb-1a01-4c8b-9758-fc6438865734",
    "prolog":         "http://data.europa.eu/esco/skill/2bde42ae-e776-41c1-9ded-b07b30bfe985",
    "scratch":        "http://data.europa.eu/esco/skill/d56fc2b5-4b0a-4e7e-9bde-a33736f6ff18",
    "vbscript":       "http://data.europa.eu/esco/skill/dcdd5ddf-82a6-4ac3-8edc-d4b23cae9a88",
    "sas":            "http://data.europa.eu/esco/skill/04f1b938-d4d4-4cb1-a863-982af76b9d93",
    "sass":           "http://data.europa.eu/esco/skill/1110c92f-3059-445a-9436-0f4200d365f5",
    "xquery":         "http://data.europa.eu/esco/skill/3f4dab51-572b-4e2c-85ef-3b4c3f7094e1",
    "solidity":       "http://data.europa.eu/esco/skill/605399ce-4736-4b41-b41e-92ecf2139454",
    "openedge advanced business language":
                      "http://data.europa.eu/esco/skill/300d432b-f457-4cd3-9cb1-1858c7d14954",
    # ---- Programming-language aliases ----
    "js":              "http://data.europa.eu/esco/skill/3cd569a2-4f88-4c1e-9995-8dce8c5e51a7",  # -> JavaScript
    "ts":              "http://data.europa.eu/esco/skill/867137fb-ff1b-4ca3-99f3-cb6969aa2c68",  # -> TypeScript
    "cpp":             "http://data.europa.eu/esco/skill/b633eb55-8f1f-4ae6-ab4c-2022ffe2cb7f",  # -> C++
    "c sharp":         "http://data.europa.eu/esco/skill/4c016b68-4116-468c-9dc6-42710c239e4a",  # -> C#
    "csharp":          "http://data.europa.eu/esco/skill/4c016b68-4116-468c-9dc6-42710c239e4a",  # -> C#
    "obj-c":           "http://data.europa.eu/esco/skill/9973a5a2-7822-4161-99e9-95c781eb63f8",  # -> Objective-C
    "objc":            "http://data.europa.eu/esco/skill/9973a5a2-7822-4161-99e9-95c781eb63f8",  # -> Objective-C
    "vb":              "http://data.europa.eu/esco/skill/13bdd41a-2a18-441f-96db-41252c519413",  # -> Visual Basic
    "vb.net":          "http://data.europa.eu/esco/skill/13bdd41a-2a18-441f-96db-41252c519413",  # -> Visual Basic
    "vbnet":           "http://data.europa.eu/esco/skill/13bdd41a-2a18-441f-96db-41252c519413",  # -> Visual Basic
    "visual basic .net":
                       "http://data.europa.eu/esco/skill/13bdd41a-2a18-441f-96db-41252c519413",  # -> Visual Basic
    "asp net":         "http://data.europa.eu/esco/skill/56a7f561-1d55-43c9-9cd7-36a0a9bc6c50",  # -> ASP.NET
    "sas language":    "http://data.europa.eu/esco/skill/04f1b938-d4d4-4cb1-a863-982af76b9d93",  # -> SAS
    "common lisp":     "http://data.europa.eu/esco/skill/0de61385-de6d-4146-ba32-1cc1bc102220",  # -> Lisp

    # ---- Markup / data-format languages -> "use markup languages" ----
    # ESCO has no dedicated concepts for HTML/XML/JSON/YAML; the
    # umbrella concept's altLabels explicitly include "use html", "use
    # XHTML", and the description covers "annotations to a document,
    # specify layout and process types of documents" — exactly the
    # space JSON/YAML inhabit too.
    "html":            "http://data.europa.eu/esco/skill/0af062de-eb43-41e9-9b96-249e2cd22d26",
    "html5":           "http://data.europa.eu/esco/skill/0af062de-eb43-41e9-9b96-249e2cd22d26",
    "xhtml":           "http://data.europa.eu/esco/skill/0af062de-eb43-41e9-9b96-249e2cd22d26",
    "xml":             "http://data.europa.eu/esco/skill/0af062de-eb43-41e9-9b96-249e2cd22d26",
    "json":            "http://data.europa.eu/esco/skill/0af062de-eb43-41e9-9b96-249e2cd22d26",
    "yaml":            "http://data.europa.eu/esco/skill/0af062de-eb43-41e9-9b96-249e2cd22d26",
    "markup languages":
                       "http://data.europa.eu/esco/skill/0af062de-eb43-41e9-9b96-249e2cd22d26",

    # ---- Regular expressions -> "utilise regular expressions" ----
    "regex":               "http://data.europa.eu/esco/skill/697dcc9f-ae92-4506-b5f2-e770d7589f74",
    "regexp":              "http://data.europa.eu/esco/skill/697dcc9f-ae92-4506-b5f2-e770d7589f74",
    "regular expressions": "http://data.europa.eu/esco/skill/697dcc9f-ae92-4506-b5f2-e770d7589f74",
    "regular expression":  "http://data.europa.eu/esco/skill/697dcc9f-ae92-4506-b5f2-e770d7589f74",

    # ---- Shell / scripting -> "use scripting programming" ----
    # Bash/Shell/PowerShell/Lua/Fortran/Ada all sit as altLabels under
    # the generic "computer programming" concept in ESCO. We route the
    # shell-shaped ones to "use scripting programming" instead, which
    # is the closer-fit umbrella for command-line scripting work.
    "bash":            "http://data.europa.eu/esco/skill/5ef0c719-5bcb-49f8-b8eb-824388225333",
    "shell":           "http://data.europa.eu/esco/skill/5ef0c719-5bcb-49f8-b8eb-824388225333",
    "shell scripting": "http://data.europa.eu/esco/skill/5ef0c719-5bcb-49f8-b8eb-824388225333",
    "shell script":    "http://data.europa.eu/esco/skill/5ef0c719-5bcb-49f8-b8eb-824388225333",
    "powershell":      "http://data.europa.eu/esco/skill/5ef0c719-5bcb-49f8-b8eb-824388225333",

    # ---- Desktop operating systems -> "operating systems" ----
    # ESCO has no dedicated concept for any specific desktop OS; the
    # umbrella's description literally lists "Linux, Windows, MacOS,
    # etc." as examples.
    "linux":           "http://data.europa.eu/esco/skill/f9a6f35b-01a7-40c9-8b61-b6ee46f97272",
    "unix":            "http://data.europa.eu/esco/skill/f9a6f35b-01a7-40c9-8b61-b6ee46f97272",
    "macos":           "http://data.europa.eu/esco/skill/f9a6f35b-01a7-40c9-8b61-b6ee46f97272",
    "mac os":          "http://data.europa.eu/esco/skill/f9a6f35b-01a7-40c9-8b61-b6ee46f97272",
    "mac os x":        "http://data.europa.eu/esco/skill/f9a6f35b-01a7-40c9-8b61-b6ee46f97272",
    "operating systems":
                       "http://data.europa.eu/esco/skill/f9a6f35b-01a7-40c9-8b61-b6ee46f97272",

    # ---- Mobile operating systems (dedicated ESCO concepts) ----
    "ios":             "http://data.europa.eu/esco/skill/ce26e71f-2d47-474e-89b6-7920931ac4fc",
    "android":         "http://data.europa.eu/esco/skill/d8829a1d-dbde-435b-b921-29d6462f35c9",

    # ---- Web frameworks (only Angular has its own ESCO concept) ----
    # React, Vue, Django, Flask, Laravel, Spring, Rails, Node.js etc.
    # have no ESCO equivalent — left to fall through.
    "angular":         "http://data.europa.eu/esco/skill/1ffac4ac-fda7-407d-8ed1-ca8f4a8dc146",
    "angular.js":      "http://data.europa.eu/esco/skill/1ffac4ac-fda7-407d-8ed1-ca8f4a8dc146",
    "angularjs":       "http://data.europa.eu/esco/skill/1ffac4ac-fda7-407d-8ed1-ca8f4a8dc146",

    # ---- Microsoft Word -> "use word processing software" ----
    # The umbrella's altLabels include "Microsoft Office Word",
    # "use MS Word", "use word processor" — exactly the resume forms.
    "microsoft word":          "http://data.europa.eu/esco/skill/81633a44-f1db-4a01-a940-804c6905e330",
    "microsoft office word":   "http://data.europa.eu/esco/skill/81633a44-f1db-4a01-a940-804c6905e330",
    "ms word":                 "http://data.europa.eu/esco/skill/81633a44-f1db-4a01-a940-804c6905e330",
    "word":                    "http://data.europa.eu/esco/skill/81633a44-f1db-4a01-a940-804c6905e330",
    "ms office word":          "http://data.europa.eu/esco/skill/81633a44-f1db-4a01-a940-804c6905e330",
    "word processor":          "http://data.europa.eu/esco/skill/81633a44-f1db-4a01-a940-804c6905e330",
    "word processing":         "http://data.europa.eu/esco/skill/81633a44-f1db-4a01-a940-804c6905e330",
    "word processing software":
                               "http://data.europa.eu/esco/skill/81633a44-f1db-4a01-a940-804c6905e330",

    # ---- Microsoft Office (general) -> "use microsoft office" ----
    "microsoft office": "http://data.europa.eu/esco/skill/f683ae1d-cb7c-4aa1-b9fe-205e1bd23535",
    "ms office":        "http://data.europa.eu/esco/skill/f683ae1d-cb7c-4aa1-b9fe-205e1bd23535",
}


def short_circuit_uri(skill: str) -> Optional[str]:
    """Return a hard-mapped URI for `skill` without retrieval, or None.

    Used in BOTH the chunk-collection (to skip embedding entirely) and
    the per-skill mapping loop (to bypass map_skill)."""
    return SHORT_CIRCUIT_OVERRIDES.get(skill.lower().strip())


HARD_BLACKLIST: frozenset[str] = frozenset({
    "cf6ca1fc-f2be-4deb-bb35-1fffe4099023",  # leadership in nursing
    "6d56955d-2b6c-471f-890d-8c17ab16053b",  # communicate in an outdoor setting (drops 153)
    "96a6b597-fc62-487e-87f2-de5b67950a3a",  # calculate dividends (drops 92)
    "5d2e82cc-5943-4218-a459-a1956fad2b63",  # manage inventory of warehouse (drops 65)
    "f7e051fc-8f7b-45b3-8911-8ffb9b951f4a",  # blockchain consensus mechanisms (drops 46)
    "79c012c7-4b09-497e-8152-e73e5d1d3384",  # adapt leadership styles in healthcare
    "ec970529-8900-404f-95aa-7521551e964f",  # leadership of drilling crews
    "06ec0ecb-87fc-47a4-8348-81df2470ff3d",  # act as leader in dental teams
})


def resolve_blacklist_indices(
    unique_uris: list[str],
    blacklist: frozenset[str],
) -> np.ndarray:
    """Convert HARD_BLACKLIST UUIDs to indices into `unique_uris`.
    Warns once for any UUID that doesn't match a known concept."""
    if not blacklist:
        return np.empty(0, dtype=np.int64)
    suffix_to_idx: dict[str, int] = {}
    for i, uri in enumerate(unique_uris):
        suffix = uri.rsplit("/", 1)[-1]
        suffix_to_idx[suffix] = i
    indices: list[int] = []
    missing: list[str] = []
    for uuid in blacklist:
        idx = suffix_to_idx.get(uuid)
        if idx is None:
            missing.append(uuid)
        else:
            indices.append(idx)
    if missing:
        print(
            f"  WARNING: {len(missing)} blacklist UUID(s) not found in "
            f"catalog: {', '.join(missing)}",
            file=sys.stderr,
        )
    return np.asarray(sorted(indices), dtype=np.int64)


def get_hybrid_weight(input_skill: str) -> tuple[float, float]:
    """Returns (label_weight, concat_weight) for an input skill."""
    s = input_skill.lower().strip()
    if s in CONCRETE_TOOLS_SET:
        return HYBRID_WEIGHTS_CONCRETE
    #if s in GENERIC_TOPIC_NOUNS:
        #return HYBRID_WEIGHTS_GENERIC
    return HYBRID_WEIGHTS_DEFAULT


# Inner per-step batch size used by sentence-transformers for both the corpus
# and the per-profile query encodes — controls GPU/CPU utilization.
DEFAULT_EMBED_BATCH_SIZE = 64

CONTEXT_CHARS = 1000  # total context budget (~250 tokens)
SUMMARY_CHARS = 250
DESC_CHARS_EACH = 100
MAX_EXPERIENCES = 6
MAX_OTHER_SKILLS = 25

# Candidate-side domain filter. Drops ESCO candidates whose label commits
# to a specific industry/setting (e.g. "leadership in nursing",
# "communicate in an outdoor setting") when the resume context lacks any
# token associated with that domain.
#
# Pattern allows an optional article ("in AN outdoor setting") which the
# bare "preposition + domain" form would otherwise miss.
DOMAIN_FILTER_PATTERN = re.compile(
    r"\b(in|of|for)\s+(?:(?:a|an|the)\s+)?"
    r"(nursing|maritime|aviation|tourism|hospitality|healthcare|"
    r"social\s+(?:work|services?)|veterinary|clinical|outdoor|pilots?|"
    r"forestry|coastal|agricultural|correctional|warehouse)\b",
    re.IGNORECASE,
)

# Each domain key maps to resume-context tokens that justify keeping a
# candidate. Tokens are matched as whole words (or as substrings for
# multi-word entries like "case worker"). Extend this as new domain-
# specialized labels surface in the failure log.
DOMAIN_CONTEXT_REQUIREMENTS: dict[str, frozenset[str]] = {
    "nursing":         frozenset({"nurse", "nursing"}),
    "maritime":        frozenset({"maritime", "ship", "vessel", "naval", "sailor"}),
    "aviation":        frozenset({"aircraft", "airline", "aviation", "flight", "airport"}),
    "tourism":         frozenset({"tourism", "tourist", "travel agency", "tour operator", "sightseeing"}),
    "hospitality":     frozenset({
        "hospitality", "hotel", "restaurant", "guest", "concierge", "lodging",
        "kitchen", "culinary", "chef", "cook", "catering", "dining", "cuisine", "menu",
    }),
    "healthcare":      frozenset({"healthcare", "physician", "doctor", "nurse", "nursing", "hospital"}),
    "social work":     frozenset({"social work", "social worker", "case worker", "caseworker", "welfare", "counseling", "counsellor"}),
    "social service":  frozenset({"social services", "social service", "case worker", "caseworker", "welfare"}),
    "social services": frozenset({"social services", "case worker", "caseworker", "welfare"}),
    "veterinary":      frozenset({"veterinary", "veterinarian", "animal", "pet"}),
    "clinical":        frozenset({"clinical trial", "clinical research", "clinical study", "clinical care", "clinical setting", "clinical experience", "clinical practice"}),
    "outdoor":         frozenset({"outdoor", "wilderness", "hiking", "camp", "camping", "expedition", "ranger"}),
    "pilot":           frozenset({"aircraft", "flight", "aviation"}),
    "pilots":          frozenset({"aircraft", "flight", "aviation"}),
    "forestry":        frozenset({"forestry", "forest", "timber", "woodland"}),
    "coastal":         frozenset({"coast", "coastal", "shoreline", "seaside"}),
    "agricultural":    frozenset({"agriculture", "agricultural", "farm", "farming", "crops", "livestock"}),
    "correctional":    frozenset({"correctional", "corrections", "prison", "jail", "inmate", "warden"}),
    "warehouse":       frozenset({"warehouse", "stockroom", "fulfillment center", "distribution center"}),
}

# Domain filter over-fetches before truncating so we still have top_k
# candidates after dropping mismatches. Headroom of ~12 candidates is
# enough in practice — typical drop count per skill is 0–3.
DOMAIN_FILTER_OVERFETCH = 20

# Inputs that are pure adjectives / modifiers without a noun-anchored
# competency. Skipped before retrieval.
ADJECTIVE_FRAGMENTS: frozenset[str] = frozenset({
    "advanced", "basic", "general", "professional", "experienced",
    "skilled", "various", "multiple", "diverse", "extensive", "strong",
    "excellent", "good", "great", "intermediate", "fluent", "proficient",
    "beginner", "expert", "entry-level", "senior-level", "expert-level",
    "computer-literate", "tech-savvy", "self-motivated", "self-starter",
    "team-player", "highly-motivated", "motivated", "detail-oriented",
})
ADJECTIVE_SUFFIXES: tuple[str, ...] = (
    "-based", "-related", "-friendly", "-oriented", "-driven",
    "-focused", "-savvy", "-literate", "-motivated", "-minded",
)


def is_adjective_fragment(skill: str) -> bool:
    """True for inputs like "web-based" or "advanced" — adjective without a noun."""
    s = skill.lower().strip()
    if s in ADJECTIVE_FRAGMENTS:
        return True
    return s.endswith(ADJECTIVE_SUFFIXES)

# EmbeddingGemma uses task-specific prefixes (asymmetric retrieval).
# Source: https://huggingface.co/google/embeddinggemma-300m
EMBED_QUERY_PREFIX = "task: search result | query: "
EMBED_DOC_PREFIX = "title: none | text: "


# -----------------------------------------------------------------------------
# ESCO catalog
# -----------------------------------------------------------------------------

@dataclass
class EscoCatalog:
    """Both retrieval views over the ESCO catalog.

    Multi-vector label view:
      label_texts[i] is the i-th retrievable label string (preferredLabel
      or altLabel); label_uris[i] is its concept URI; label_to_uri_idx[i]
      is the row index of that URI in the per-URI views below.

    Per-URI concat view:
      unique_uris[u] is the u-th concept URI; concat_texts[u] is the
      "preferredLabel + altLabels + description" document for it;
      uri_to_label_indices[u] enumerates all label-row indices that
      belong to it (used to resolve the best-scoring label per URI).
    """
    label_texts: list[str]
    label_uris: list[str]
    uri_to_label: dict[str, str]
    unique_uris: list[str]
    concat_texts: list[str]
    label_to_uri_idx: np.ndarray
    uri_to_label_indices: list[np.ndarray]


@dataclass
class EscoIndex:
    """Catalog + the two embedding matrices it indexes into."""
    catalog: EscoCatalog
    label_emb: np.ndarray   # (n_labels, dim) float32, normalized
    concat_emb: np.ndarray  # (n_uris,   dim) float32, normalized
    blacklist_uri_indices: np.ndarray  # int64; rows in unique_uris to suppress


def load_esco_catalog(path: Path) -> EscoCatalog:
    """
    Build both retrieval views over the ESCO catalog in one pass.

    The label corpus is multi-vector (every preferredLabel/altLabel is
    its own row) so cosine recall mirrors the cosine-only variant. The
    concat corpus has one row per concept URI, built from
    "preferredLabel. altLabels. description" — designed to bring in
    semantic signal that the bare labels alone don't carry.
    """
    df = pd.read_csv(path)

    label_texts: list[str] = []
    label_uris: list[str] = []
    uri_to_label: dict[str, str] = {}

    unique_uris: list[str] = []
    concat_texts: list[str] = []
    uri_to_uri_idx: dict[str, int] = {}

    for _, row in df.iterrows():
        uri = row.get("conceptUri")
        pref = row.get("preferredLabel")
        if not isinstance(uri, str) or not isinstance(pref, str) or not pref.strip():
            continue
        pref = pref.strip()
        if uri in uri_to_uri_idx:
            # Same URI listed twice in the CSV — keep the first.
            continue

        uri_to_label[uri] = pref
        uri_idx = len(unique_uris)
        uri_to_uri_idx[uri] = uri_idx
        unique_uris.append(uri)

        label_texts.append(pref)
        label_uris.append(uri)

        alt_list: list[str] = []
        alts = row.get("altLabels")
        if isinstance(alts, str):
            for alt in alts.split("\n"):
                alt = alt.strip()
                if alt:
                    label_texts.append(alt)
                    label_uris.append(uri)
                    alt_list.append(alt)

        # Per-URI concat doc: title + alt labels + description.
        concat_parts = [pref]
        if alt_list:
            concat_parts.append(", ".join(alt_list))
        desc = row.get("description")
        if isinstance(desc, str) and desc.strip():
            concat_parts.append(desc.strip())
        concat_texts.append(". ".join(concat_parts))

    label_to_uri_idx = np.fromiter(
        (uri_to_uri_idx[u] for u in label_uris),
        dtype=np.int64,
        count=len(label_uris),
    )

    # Reverse map: per URI, the list of label-row indices that belong to it.
    buckets: list[list[int]] = [[] for _ in range(len(unique_uris))]
    for label_idx, uri_idx in enumerate(label_to_uri_idx):
        buckets[int(uri_idx)].append(label_idx)
    uri_to_label_indices = [
        np.asarray(b, dtype=np.int64) for b in buckets
    ]

    return EscoCatalog(
        label_texts=label_texts,
        label_uris=label_uris,
        uri_to_label=uri_to_label,
        unique_uris=unique_uris,
        concat_texts=concat_texts,
        label_to_uri_idx=label_to_uri_idx,
        uri_to_label_indices=uri_to_label_indices,
    )


# -----------------------------------------------------------------------------
# Retrieval
# -----------------------------------------------------------------------------

def embed_corpus(
    texts: list[str],
    model: SentenceTransformer,
    batch_size: int = DEFAULT_EMBED_BATCH_SIZE,
) -> np.ndarray:
    prefixed = [EMBED_DOC_PREFIX + t for t in texts]
    return model.encode(
        prefixed,
        normalize_embeddings=True,
        batch_size=batch_size,
        show_progress_bar=True,
        convert_to_numpy=True,
    ).astype(np.float32)


def encode_queries(
    queries: list[str],
    model: SentenceTransformer,
    batch_size: int = DEFAULT_EMBED_BATCH_SIZE,
) -> np.ndarray:
    """Batch-encode skill queries with the EmbeddingGemma query prefix.
    Returns a normalized (N, dim) float32 array."""
    if not queries:
        return np.zeros((0, 0), dtype=np.float32)
    prefixed = [EMBED_QUERY_PREFIX + q for q in queries]
    return model.encode(
        prefixed,
        normalize_embeddings=True,
        batch_size=batch_size,
        show_progress_bar=False,
        convert_to_numpy=True,
    ).astype(np.float32)


def retrieve_top_k_hybrid(
    query_emb: np.ndarray,
    index: EscoIndex,
    k: int,
    *,
    label_weight: float,
    concat_weight: float,
) -> list[tuple[str, str, float]]:
    """Top-k unique URIs by hybrid score, returned as (uri, label, score).

    label is the highest-scoring label entry for the URI — the same string
    the cosine-only variant would have shown — so the downstream domain
    filter sees the same surface form it always has.
    """
    cat = index.catalog
    label_scores = index.label_emb @ query_emb            # (n_labels,)
    concat_scores = index.concat_emb @ query_emb          # (n_uris,)

    n_uris = len(cat.unique_uris)
    label_max = np.full(n_uris, -np.inf, dtype=np.float32)
    np.maximum.at(label_max, cat.label_to_uri_idx, label_scores)

    hybrid = label_weight * label_max + concat_weight * concat_scores

    # Hard blacklist: force these URIs out of contention before top-k.
    if index.blacklist_uri_indices.size:
        hybrid[index.blacklist_uri_indices] = -np.inf

    eff_k = min(k, n_uris)
    if eff_k <= 0:
        return []
    top_idx = np.argpartition(-hybrid, eff_k - 1)[:eff_k]
    top_idx = top_idx[np.argsort(-hybrid[top_idx])]

    out: list[tuple[str, str, float]] = []
    for u_idx in top_idx:
        uri = cat.unique_uris[int(u_idx)]
        l_indices = cat.uri_to_label_indices[int(u_idx)]
        # Every URI has at least its preferredLabel, so l_indices is non-empty.
        best_label_idx = int(l_indices[int(np.argmax(label_scores[l_indices]))])
        best_label = cat.label_texts[best_label_idx]
        out.append((uri, best_label, float(hybrid[int(u_idx)])))
    return out


# -----------------------------------------------------------------------------
# Domain filter
# -----------------------------------------------------------------------------

def _resume_word_set(resume_text: str) -> set[str]:
    return set(re.findall(r"\b[\w']+\b", resume_text.lower()))


def candidate_passes_domain_check(
    label: str,
    resume_text: str,
    resume_words: Optional[set[str]] = None,
) -> tuple[bool, Optional[str], Optional[str]]:
    """Returns (passes, domain, matched_token).

    matched_token is the resume-context token that justified keeping the
    candidate. None when label has no domain qualifier, when the domain
    isn't in our requirements table, or when the candidate is dropped.
    """
    m = DOMAIN_FILTER_PATTERN.search(label)
    if not m:
        return True, None, None

    domain = re.sub(r"\s+", " ", m.group(2).strip().lower())
    required = DOMAIN_CONTEXT_REQUIREMENTS.get(domain)
    if not required:
        return True, domain, None

    if resume_words is None:
        resume_words = _resume_word_set(resume_text)
    resume_lower = resume_text.lower()
    for token in required:
        if " " in token:
            if token in resume_lower:
                return True, domain, token
        elif token in resume_words:
            return True, domain, token
    return False, domain, None


def filter_candidates_by_domain(
    candidates: list[tuple[str, str, float]],
    resume_text: str,
    top_k: int,
) -> tuple[list[tuple[str, str, float]], list[dict], list[dict]]:
    """Returns (kept[:top_k], dropped_audit, kept_with_trigger_audit).

    kept_with_trigger_audit lists candidates that *were domain-qualified*
    and passed because a context token matched. Plain candidates without
    domain qualifiers are silent (no audit entry).
    """
    resume_words = _resume_word_set(resume_text)
    kept: list[tuple[str, str, float]] = []
    dropped_audit: list[dict] = []
    kept_audit: list[dict] = []
    for idx, cand in enumerate(candidates):
        uri, label, score = cand
        passes, domain, trigger = candidate_passes_domain_check(
            label, resume_text, resume_words,
        )
        if passes:
            kept.append(cand)
            # Only audit keeps where a domain qualifier was actually
            # evaluated (trigger is set). Skips plain non-domain labels.
            if trigger and len(kept) <= top_k:
                kept_audit.append({
                    "uri": uri,
                    "label": label,
                    "cosine": round(score, 4),
                    "domain": domain,
                    "trigger": trigger,
                })
        elif idx < top_k:
            dropped_audit.append({
                "uri": uri,
                "label": label,
                "cosine": round(score, 4),
                "domain": domain,
            })
    return kept[:top_k], dropped_audit, kept_audit


# -----------------------------------------------------------------------------
# Mapping
# -----------------------------------------------------------------------------

def _log_event(
    log_file,
    identifier: Optional[str],
    skill: str,
    context: str,
    candidates: list[tuple[str, str, float]],
    outcome: str,
    detail: Optional[dict] = None,
) -> None:
    """Append one JSONL record describing a non-trivial outcome.
    Flushed immediately so partial logs survive a Ctrl-C / crash."""
    if log_file is None:
        return
    record = {
        "identifier": identifier,
        "skill": skill,
        "outcome": outcome,
        "context": (context[:200] if context else None),
        "candidates": [
            {"uri": uri, "label": label, "cosine": round(sc, 4)}
            for uri, label, sc in candidates
        ],
    }
    if detail:
        record["detail"] = detail
    log_file.write(json.dumps(record, ensure_ascii=False) + "\n")
    log_file.flush()


def map_skill(
    skill: str,
    context: str,
    query_emb: np.ndarray,
    index: EscoIndex,
    top_k: int,
    *,
    threshold: float = COSINE_THRESHOLD,
    domain_filter_enabled: bool = True,
    identifier: Optional[str] = None,
    log_file=None,
) -> Optional[str]:
    """Caller is responsible for applying `is_adjective_fragment` upstream
    and not computing/passing a query embedding for those inputs.

    Hybrid weights are picked per skill by `get_hybrid_weight` (concrete
    tools collapse to label-only, generic competencies lean on
    description, everything else takes a light description tie-break)."""
    label_weight, concat_weight = get_hybrid_weight(skill)
    if domain_filter_enabled:
        pre_k = max(DOMAIN_FILTER_OVERFETCH, top_k * 2)
        raw_candidates = retrieve_top_k_hybrid(
            query_emb, index, pre_k,
            label_weight=label_weight, concat_weight=concat_weight,
        )
        candidates, dropped, kept_with_trigger = filter_candidates_by_domain(
            raw_candidates, context, top_k,
        )
        if dropped or kept_with_trigger:
            detail: dict = {}
            if dropped:
                detail["dropped"] = dropped
            if kept_with_trigger:
                detail["kept_with_trigger"] = kept_with_trigger
            _log_event(log_file, identifier, skill, context, candidates,
                    "domain_filtered", detail)
    else:
        candidates = retrieve_top_k_hybrid(
            query_emb, index, top_k,
            label_weight=label_weight, concat_weight=concat_weight,
        )

    if not candidates:
        return None

    top_uri, _, top_score = candidates[0]
    if top_score < threshold:
        return None
    return top_uri
