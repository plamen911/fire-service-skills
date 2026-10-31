# Конектор – графиците за дежурства

> Част от `_shared/connector.md` – чете се след него, само от скиловете, които изброява. Копие – каноничният
> източник е `plugins/fire-service/shared/`.

За `grafik-dezhurstva`.

| Вместо | Инструмент | Бележки |
|---|---|---|
| поименното разписание за сверка на график | `staff` с `zveno` и `csv: true` → запиши `header` и `rows` във файл → `grafik.py --roster ФАЙЛ …` | трябва само за **запис** на график; въпросите за дежурства работят и без него |
| `grafik.py na-data`, `sluzhitel`, `praznichni`, `pri-proizshestvie` | `duty` с `grafik` и `mesec` → файл на месеца → `grafik.py --store ПАПКА …` (за `pri-proizshestvie`: записът от `incidents` с `fields` `id, dat, unit, forces, orderlyturn, closed, dat_o2, num_event, address, location, object, casulaty` → файл → `--zapis`; свали `oc` и графика на службата за месеца на произшествието, а за час преди 08:00 на 1-ви – и предния месец) | записваш върнатото като `ПАПКА/<grafik>/<ГГГГ-ММ>.json` (`{"grafik", "mesec", "sluzhiteli"}`); без аргументи `duty` дава списъка на месеците. „Аз“ е `ime` от `whoami` – подай го като име, не `--az` |
| `grafik.py import` (запис на график) | `duty` (запомни `md5`; при `NOT_FOUND` – `new`) → `grafik.py --store ПАПКА --roster ФАЙЛ import …` → `duty_save` с текста на файла, `sha256` от скрипта и `if_md5` | всеки може да запише график; текстът се подава без промяна. `CONFLICT` = друг е записал месеца междувременно и нищо не е записано: `duty` отново, `import` върху новия месец, запис с новия `md5` |
| `plan_grafik.py mesec` / `godina` (план-графикът на занятията на ОЦ) | `regs_list` с `name: "Plan-Grafik"` → `regs_read` → запиши текста във файл → `plan_grafik.py … --file ФАЙЛ` | |
