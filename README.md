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

## Uso backend da terminale

Per lavorare solo su acquisizione, registrazione ed export senza GUI:

```bash
python main.py record --mode simulated --duration 5 --test-type "CMJ" --first-name Mirko --last-name Calcaterra
```

Per ispezionare l'ultimo test esportato:

```bash
python main.py inspect
```

Per analizzare l'ultimo test esportato:

```bash
python main.py analyze
```

Per analizzare un file specifico e salvare il riepilogo finale in un path custom:

```bash
python main.py analyze output/tests/20260411_124908_Calcaterra_Mirko_cmj_signals.csv --export-summary output/tests/cmj_summary.csv
```

Per forzare il tipo di test se i metadata sono assenti o non affidabili:

```bash
python main.py analyze output/tests/test_signals.csv --test-type CMJ
```

Output:

- progress realtime in terminale con `P1_total_FZ`, `P2_total_FZ`, `FZ_total`
- `*_signals.csv`
- `*_metadata.csv`
- `*.xlsx`
- ispezione rapida di colonne, durata e metadati
- report numerico finale con bodyweight stimato, eventi, picchi, jump height e asimmetria

Questo e il flusso consigliato su macOS mentre costruiamo il backend.

In modalita simulata il profilo del segnale cambia in base a `--test-type`:

- `Squat Jump` o `SJ`
- `Countermovement Jump` o `CMJ`
- `Drop Jump` o `DJ`
- qualsiasi altro valore usa un profilo generico

## Pipeline analyze

`analyze` lavora in questo ordine:

- validazione file e colonne richieste
- stima sample rate e qualita temporale
- stima quiet standing iniziale e bodyweight in Volt
- costruzione forze nette per lato e totale
- rilevazione eventi principali
- calcolo metriche finali
- export automatico di `*_summary.csv`

Note:

- in questa fase i dati restano in Volt
- `jump_height_m` viene stimata da `flight_time_s`
- `SJ` e `CMJ` hanno rilevazione eventi piu curata
- `DJ` e supportato in modo pragmatico con metriche/eventi base

## Nota macOS

Su macOS la modalita `NI Hardware` non e supportata da `nidaqmx`. Il Mac va quindi usato per:

- sviluppo software
- test UI
- simulazione segnali

Per la lettura reale della NI USB-6211 serve un PC Windows con NI-DAQmx installato.

## Output export

Ogni prova salva:

- `*_signals.csv`
- `*_metadata.csv`
- `*.xlsx` con fogli `metadata` e `signals`

I file vengono salvati in `output/tests/`.
