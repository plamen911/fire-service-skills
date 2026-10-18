# Data protection

Case files in a criminal fire investigation contain personal data: the names and statements of
owners, witnesses and investigators, addresses, and the details of a pre-trial proceeding. The key
question is how we can be sure that none of it leaks. This page answers it in three parts:

- what the system enforces in code;
- what depends on the AI provider and how it is configured;
- what remains the expert's responsibility.

## Where case data goes

```
phone photos ──► Claude chat (Anthropic) ──► .docx / .xlsx in the same chat ──► expert ──► investigator
                        │                                                                (Viber / e-mail)
                        └─► n8n (per-person key) ──► Google Drive / Firebase
                             reads: staff list, incidents, approved templates
                             writes: templates – only after an anonymisation check, admin only
```

- **The case material never reaches the public repository, n8n, Google Drive or Firebase.** It is
  read and processed inside the expert's own Claude conversation.
- The only path from a case into shared storage is saving an approved report as a template. That
  path is limited to the administrator and, since v2.22.0, guarded in code (see below).

## Enforced in code

| Protection | How |
|---|---|
| No personal data in the public repository | `tools/check_public.py` runs in CI on every push. It blocks the commit on ЕГН, phone numbers, e-mails, car plates, IBANs, street addresses, case and document numbers, Google Drive ids, keys and tokens. It also checks every person's name against the real staff list. |
| Templates are checked before they are shared | Since v2.22.0, `obraztsi.py zapis` refuses to save a template that still contains an ЕГН, a phone number, a car plate, an exact address, an e-mail or a person's name (`PERSONAL_DATA`, covered by tests). All templates saved before this check were anonymised in October 2026: names replaced by roles, addresses reduced to the settlement, plates, cadastral and case numbers removed. They were then re-checked by the script and by an independent AI audit. |
| Templates can only be written by the administrator | n8n checks the key's role; everyone else can only read anonymised templates. |
| Per-person API keys | Every colleague has their own key. n8n stores only a hash of it, and the key is shown once when issued. One key can be revoked without affecting anyone else (`admin.py key revoke`). |
| Keys never appear in output | The scripts report only whether a key exists and where it came from, never the key itself. |
| Minimum personal data in the documents | The independent review (`pregled.py`) blocks ЕГН and phone numbers in a report. People are named with first name and surname only, never three names. |
| No guessing beyond the materials | The review and the evaluation suite reject facts that are not in the case materials (see the [case study](case-study-eptz.md)). |

## Depends on the AI provider (Anthropic) and its settings

The photos are processed by Claude, so they are stored by Anthropic for as long as its terms allow.
That depends on the plan and on one setting:

- **Free, Pro and Max (consumer terms).** Whether chats may be used to train models is the user's
  choice, made with the "Help improve Claude" setting.
  - Setting off: the 30-day retention period applies.
  - Setting on: retention is extended to five years.
  - A deleted chat is removed from the history immediately and from Anthropic's back-end storage
    within 30 days.
- **Team, Enterprise, API, Claude for Government (commercial terms).** The consumer training
  choice does not apply; these plans are not used to train models.

**Required configuration for case work:**

1. Turn **off** "Help improve Claude" (Settings → Privacy) on every account used for case work.
2. **Delete the chat** once the report has been delivered.
3. For institutional use, prefer a **Team or Enterprise** plan under the commercial terms.

Sources: [Anthropic – Updates to consumer terms](https://www.anthropic.com/news/updates-to-our-consumer-terms) ·
[How long do you store my data?](https://privacy.claude.com/en/articles/10023548-how-long-do-you-store-my-data)

## The expert's responsibility

- **Delivery.** The finished report leaves the system with the expert, by Viber or e-mail, the
  same way it left before. Use the channel the investigating authority accepts.
- **The phone.** Photos of the case file stay in the phone's gallery until deleted.
- **Permission.** Processing material from a pre-trial proceeding in an external cloud service must
  be permitted by the rules of the employer and the investigating authority (the secrecy of
  pre-trial proceedings, GDPR). This tool makes the processing safe; it does not grant the
  permission. Confirm it before using the tool on real cases.
