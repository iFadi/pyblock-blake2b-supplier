# Screenshot Capture Checklist

The optional Configure screenshot must be captured from a real StartOS device
after installation. It must be sanitized and reviewed before committing.

---

## Candidate screenshot

### Configuration form

**When:** Service stopped; Configure action open.

**Navigate to:** Services → PyBLOCK BLAKE2b Supplier → Actions → Configure

**Capture:** The full Configure form with all fields visible.

**Redact before committing (mandatory):**
- **Payout address** — replace with a clearly fake placeholder such as
  `bc1q_REDACTED` or blur the field entirely.
- **RPC Username** — blur or replace with `rpcuser_REDACTED`.
- **RPC Password** — the field is intentionally blank when the form opens;
  confirm no saved value is shown.
- **Supplier Name** — may be left visible if it contains no personal information,
  or blur if preferred.
- **RPC Host / Port** — these are auto-resolved and non-sensitive (they show an
  internal bridge address), but blur if you prefer a clean capture.

**Filename:** `docs/screenshots/configure.png`

---

## Tool notes

- Use OS-level screenshot (not browser DevTools) for the most authentic look.
- Crop to the panel; no need to show the full browser chrome.
- Preferred format: PNG at native resolution; no lossy JPEG for UI captures.
- If using an annotation tool to draw redaction boxes, use an opaque solid
  rectangle, not a blur — blurs can sometimes be reversed.
- Accept only this single genuine Configure screenshot. Do not add generated,
  mockup, About, health, or suppliers-page images.

---

## Adding screenshots to the README

Only after the genuine sanitized Configure file exists and has been reviewed,
add it to `README.md` with this relative path:

```markdown
![Configure form](docs/screenshots/configure.png)
```

Do not add image references to the README until the files are actually present
in the repository.
