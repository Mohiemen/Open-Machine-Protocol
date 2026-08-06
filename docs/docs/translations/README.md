# Translations

Documentation in the languages of manufacturing is a first-class deliverable
(vision principle 7), because a quickstart an engineer can read converts
directly into deployments and contributors.

## Priority

1. **getting-started** first (quickstart, first real machine, FAQ)
2. **guides** second (retrofit installation and the factory-deployment runbook
   page are the highest-leverage items)
3. **reference** last

Bangla (bn) leads, because the project's first target users are on factory
floors in Bangladesh. Vietnamese (vi), Hindi (hi), Turkish (tr), and Bahasa
Indonesia (id) are equally welcome - as is any language a factory floor speaks.

## Layout

```
translations/
├── bn/            # Bangla - directory mirrors docs/ structure
├── vi/            # Vietnamese
└── ...
```

Each language directory mirrors the English `docs/` tree, translating file by
file. Untranslated files are simply absent - no placeholder files.

## Status

| Language | getting-started | guides | reference |
|---|---|---|---|
| bn | [quickstart](bn/getting-started/quickstart.md) done; first-real-machine and FAQ **help wanted** | - | - |

## Contributing a Translation

- Translate meaning, not words - keep identifiers, commands, and field names
  in English (they are code), translate the prose around them.
- Unpolished translations are welcome; a rough Bangla quickstart today beats a
  perfect one next year. Native-speaker review happens in PR like any other
  review.
- Open an issue claiming a file before starting, so effort isn't duplicated.
