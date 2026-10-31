# Конектор – водоизточниците

> Част от `_shared/connector.md` – чете се след него, само от скиловете, които изброява. Копие – каноничният
> източник е `plugins/fire-service/shared/`.

За `vodoiztochnitsi`.

| Вместо | Инструмент | Бележки |
|---|---|---|
| `voda.py masto` / `sluzhba` / `statistika` | `voda` с `action` и `name` (и `obshtina`) | отговорът е като на скрипта с `--json`; за място на хидрант се дават само точните (`tochni_koordinati: true`) |
| `voda.py excel` (списък в Excel) | `voda` с `action: "excel"` (по желание `name`, `obshtina`, `sluzhba`, `vid`, `samo_tochni`) | n8n прави `.xlsx` и връща само `link` (24 часа) и броевете – дай линка; не събирай редовете с други извиквания |
| `voda.py blizo` | `voda` с `action: "blizo"` и `lat`, `lon` (или `masto`) | `broi` до 25; разстоянието е по права линия |
| `voda.py dobavi` / `potvardi` / `promeni` / `premahni` | `voda_save` с `action` и същите полета (`promeni` – `id` и `set`; `premahni` – `id` и `prichina`) | всеки може да записва; премахва администраторът или който е въвел точката; първо с `dry_run: true`; координатите са само от потребителя; при `dobavi` винаги подавай `ulitsa` с номера и `orientir` – без тях n8n връща `MISSING`; адреса на ориентира го намираш ти (`kais` с `action: "mesto"`); извън улица (парк, местност) – в `ulitsa` мястото и `bez_nomer: true` |
