# AppPedanaVolley

MVP desktop in Python per acquisizione segnali da pedana BTS tramite National Instruments USB-6211.

## Obiettivi MVP

- acquisizione segnali analogici dalla NI USB-6211
- visualizzazione realtime dei canali verticali `FZ`
- aggregazioni `P1_total_FZ`, `P2_total_FZ`, `FZ_total`
- registrazione di un test breve
- export dati grezzi e metadati in CSV e Excel
- base pulita per metriche successive

## Stack scelto

- `PySide6` per GUI desktop cross-platform
- `pyqtgraph` per grafici realtime leggeri
- `pandas` + `openpyxl` per export
- `nidaqmx` per integrazione NI-DAQmx

## Avvio rapido

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Su Windows:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

## Modalita disponibili

- `NI Hardware`: usa `nidaqmx` e richiede NI-DAQmx installato
- `Simulata`: genera segnali coerenti per test software

## Output export

Ogni prova salva:

- `*_signals.csv`
- `*_metadata.csv`
- `*.xlsx` con fogli `metadata` e `signals`

I file vengono salvati in `output/tests/`.
