---
title: Rationale Template
summary: Krótki, ustrukturyzowany szablon wyjaśniający decyzje implementacyjne i mapujący zmiany do acceptance criteria. Wymagany jako `rationale.md` w PR/branchie dla każdego task_id.
---

# Rationale for `{{ task_id }}`

**author:**  
**branch:**  
**commit_sha:**  
**date:**  

---

## 1) One-line summary
Krótko — czym jest zmiana i jaki problem rozwiązuje (1 zdanie).

**Example:** Implement backend endpoint `/api/watchlist/:id/anomalies` to return unresolved crypto anomalies (last 24h, severity >= 0.5).

---

## 2) Mapping to acceptance criteria  
Dla każdej pozycji z `acceptance_criteria` w task spec wpisz następujące pola. Skopiuj każdy item i wypełnij:

- **Criteria:** *(skopiuj z task spec)*  
- **Status:** `pass | fail | partial`  
- **Evidence:** (np. `pytest tests/test_anomalies_api.py::test_unresolved_returns_200 — passed`, `'diff: src/services/anomalies.py#L45-L78'`, fragment logów)  
- **Notes / justification:** (krótka nota jeśli status = partial lub fail)

Repeat for all acceptance criteria.

---

## 3) Files changed (and rationale per file)
Wypisz wszystkie zmienione pliki i krótko opisz dlaczego były konieczne. Jeśli zmieniono plik poza `files_expected`, podaj uzasadnienie i ocenę ryzyka.

- `path/to/file.py` — reason, key changes, estimated LOC delta
- `path/to/test_x.py` — reason
- ...

---

## 4) Tests run & results
Podaj dokładne polecenia, które zostały uruchomione (kopiuj CLI), oraz wyciąg z logów / podsumowanie wyników.

- **Commands run:**
  - `pytest tests/test_anomalies_api.py`
  - `python -m myproject.typecheck`
  - `npm run lint`
- **Results summary:**  
  - tests: X passed, Y failed (attach important failing traces)  
  - lint: passed/failed (attach excerpts)  
  - typecheck: passed/failed (attach excerpts)

Jeśli jakieś testy są flaky/pending, opisz dlaczego i co planujesz zrobić.

---

## 5) Data & sample evidence
Dołącz krótkie przykłady danych użytych w testach / sample time-series previewy / fixtures. Wskaż, skąd pochodzą (synthetic / fixture / live-demo) i dlaczego są reprezentatywne.

- `asset: BTC-USD, window: 2026-03-01..2026-03-02` — snapshot: {open,high,low,close,volume}
- sample anomaly record: `{ "id": "anom-123", "type":"price_spike", "severity":0.72, "timestamp": "..." }`

---

## 6) Risk assessment & mitigations
Krótka tabela ryzyk, severity i co zrobiono, by zmitygować.

- **Risk:** touching forbidden path (e.g., `secrets/`) — **Severity:** high — **Mitigation:** niezmienione, dodatkowe testy, alert w CI  
- **Risk:** coverage drop — **Severity:** medium — **Mitigation:** dodałem unit tests for X

---

## 7) Backwards compatibility / migration notes
Jeżeli zmiana wpływa na API, storage lub behavior, opisz kompatybilność i ewentualne kroki migracyjne (DB migrations, schema changes, feature flags).

- API changes: `/api/watchlist/:id/anomalies` added — backward compatible: yes/no  
- DB migrations: none / `CREATE TABLE ...` (attach SQL / migration script)

---

## 8) Performance considerations
Jeśli zmiana może wpłynąć na latencję, pamięć lub koszt (np. agregacje czasu rzeczywistego), opisz mierzalne przybliżenia i testy wydajnościowe.

- expected QPS impact: +X%  
- memory: +Y MB per request  
- perf tests: `scripts/perf/run_anomaly_query.sh` — results summary

---

## 9) Security & safety checks
Wskaż, że nie ma zmian w `forbidden_paths` i potwierdź brak użycia broker SDK / real API keys. Jeśli coś wzbudza wątpliwość, opisz.

- forbidden paths touched: `no`  
- external/broker sdk usage: `no`  
- secrets touched: `no`

---

## 10) Open questions & follow-ups
Lista rzeczy do rozstrzygnięcia przez Orchestratora / Reviewer / Human:

1. (np.) Czy threshold 0.5 jest docelowy czy powinniśmy parametryzować?  
2. Czy trzeba dodać E2E test dla frontend panelu?

---

## 11) Short changelog (commit messages / important diffs)
Wypisz najważniejsze commity i krótkie podsumowania. Każdy commit musi zawierać `task_id` w message.

- `commit_sha1` — implement anomalies API — files: ... — tests: ...
- `commit_sha2` — add tests for edge-case X

---

## 12) Final verdict (developer self-check)
Krótka deklaracja developera:

- **I confirm** that all acceptance criteria marked `pass` have test evidence attached: `yes|no`  
- **I confirm** no forbidden paths were modified: `yes|no`  
- **I request** next step: `validate|mark-ready|ask_human`

---

### Notes for coders (how to fill)
- Bądź precyzyjny — kopiuj dokładne CLI i fragmenty logów.  
- Nie pisz narracyjnie — pisz punktowo i do rzeczy.  
- Jeśli coś jest partial, opisz plan naprawczy.