# Case study: AI-drafted forensic fire reports, from 5–6 hours to 10–15 minutes

**Project:** `eptz` skill in the [fire-service](../README.md) Claude plugin
**Author:** Plamen Markov – design, implementation, evaluation
**Users:** forensic fire experts at the Regional Fire Safety and Civil Protection Directorate, Pleven (Bulgaria)

## The problem

When a fire becomes a criminal case, the investigator appoints a fire expert. The expert must answer
the investigator's questions in a formal expert report (ЕПТЗ), which is then used in court. Each one
means:

- reading 15–20 pages of case material: the appointment order, the fire brigade's call log, the
  scene inspection report, witness statements and photos;
- working through every standard cause in turn – arson, short circuit, natural causes,
  spontaneous combustion, negligence – and accepting or rejecting each with facts from the case;
- citing every reference value (ignition temperatures, flash points) to an authoritative source;
- producing the report on the official letterhead in a strict format, plus the fee invoice.

By hand this took **5–6 hours per case**. The work is precise rather than creative, and a single
invented detail or overstated conclusion weakens the report in court.

## The solution

A Claude plugin skill that turns phone photos of the case file into a finished report:

1. The expert photographs the 15–20 pages and uploads them in the Claude mobile app.
2. The skill reads the pages and asks only for what is missing. It then analyses the causes using
   approved past reports and a catalogue of sourced reference values (ILO/WHO ICSC cards, CHRIS,
   GESTIS-STAUB-EX, Babrauskas, METAR weather archives).
3. Python scripts build the official `.docx` and the `.xlsx` fee invoice. A mechanical check and a
   separate AI reviewer then examine the report. The reviewer did not write the text, so it does
   not grade its own work.
4. The expert reviews and signs the report, then sends it to the investigator by Viber or email.

**Stack:** Claude (skills, subagents), Python (python-docx, openpyxl), n8n as the API layer,
Google Drive (templates, approved reports, normative base), Firebase (incident database), MCP
connector for colleagues on the free Claude plan.

## Results

| | Before | After |
|---|---|---|
| Time per report (report + invoice) | 5–6 hours | **10–15 minutes** |
| Input | typing from paper files | 15–20 phone photos |
| Hardware needed | desktop with Word/Excel | phone |

That is roughly **25× faster**, or about 5 hours saved per case.

**Quality is measured, not assumed.** The skill has an automated evaluation suite. Eight synthetic
cases run against the real model with graders, including an LLM judge:

- **18/18** runs pass on routing and behaviour: the skill triggers only for an appointed
  expertise, asks before generating, and keeps first replies short.
- **6/6** planted fabricated facts are caught by the LLM judge, and correct reports pass.
- In the latest run, **8/8** judge checks passed on full reports: no invented facts, and every
  rejected cause backed by a concrete fact from the case.
- The suite found real defects that unit tests had missed and that have since been fixed:
  - a crash that blocked colleagues without a personal API key;
  - conclusions stated as facts;
  - a review step the model skipped in 3 of 4 runs.

## Data protection

A case file holds names, statements and addresses from a pre-trial proceeding. The design keeps that
data in one place, the expert's own Claude conversation, and enforces the rest in code:

- **Case material never reaches shared storage.** It does not go to the public repository, n8n,
  Google Drive or Firebase.
- **Every push is scanned.** A check in CI blocks ЕГН, phones, plates, addresses, case numbers,
  keys and the name of any real staff member.
- **Templates are anonymised before sharing, enforced in code.** A past report becomes a shared
  template only if a personal-data check passes, and only the administrator can save one.
- **Each colleague has their own key.** n8n stores only a hash of it, and one key can be revoked
  without affecting anyone else.
- **The AI provider is configured for case work.** Model training is turned off and chats are
  deleted after delivery, which keeps Anthropic's retention at 30 days. For institutional use, a
  Team or Enterprise plan falls under the commercial terms, where data is not used for training.

Details, including what remains the expert's responsibility: [data-protection.md](data-protection.md).

## What made it work

- **Evaluation first.** Every rule in the skill traces back to a failure an eval caught, for
  example "a rejected cause must cite a concrete fact, not just 'no data in the materials'".
- **The judge sees the full materials.** A summarised fact list made the judge flag true facts as
  invented; giving it the source text verbatim fixed that.
- **Script output beats instructions.** The model skipped a mandatory review step when only the
  prompt asked for it. Once the review script itself announced the next step, the review ran far
  more reliably.
- **Privacy by design.** The repository is public; case data, staff lists and approved reports sit
  behind n8n with per-person API keys, so each colleague can be revoked individually.

All examples in this repository are fictional; no real case material is published.
