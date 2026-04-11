# AppPedanaVolley - Next Steps

Questo documento raccoglie il piano operativo per riprendere il progetto dal punto attuale.

## Stato attuale

- backend Python modulare avviato
- comandi CLI disponibili:
  - `record`
  - `inspect`
  - `analyze`
- simulazione distinta per `SJ`, `CMJ`, `DJ`
- export:
  - `*_signals.csv`
  - `*_metadata.csv`
  - `*.xlsx`
  - `*_summary.csv`
- pipeline analitica v1 già presente:
  - quiet standing iniziale
  - bodyweight stimato in Volt
  - takeoff / landing
  - jump height da flight time
  - picchi e asimmetria
  - impulse asymmetry

## Priorità operative

### 1. Validazione hardware reale su Windows

Obiettivo:

- verificare che la NI USB-6211 venga letta davvero
- confermare che il mapping dei canali BTS sia corretto
- produrre un primo file reale con la stessa pipeline di export già usata dal simulato

Checklist:

- installare Python 3.12 su Windows
- creare il venv
- installare le dipendenze Python
- installare NI-DAQmx sul PC Windows
- collegare la NI USB-6211
- verificare che il device sia visibile come `Dev1` oppure aggiornare il nome in configurazione
- eseguire una prova breve in `--mode ni`
- verificare che l'export contenga:
  - `timestamp_s`
  - canali FZ
  - `P1_total_FZ`
  - `P2_total_FZ`
  - `FZ_total`

Comandi attesi su Windows:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main.py record --mode ni --duration 5 --test-type CMJ --first-name Test --last-name Hardware
```

Acceptance:

- il comando termina senza errori
- i file vengono creati in `output/tests/`
- i segnali non sono piatti e mostrano differenze coerenti tra lato sinistro e destro

### 2. Hardening del path NI

Obiettivo:

- rendere il percorso Windows robusto prima di lavorare sulla GUI finale

Da implementare:

- comando CLI tipo `devices` o `probe-ni`
- messaggio chiaro se `Dev1` non esiste
- elenco canali configurati e canali attivi
- errore esplicito se NI-DAQmx non è installato
- override del device name da CLI o config

Acceptance:

- da terminale si capisce subito se il problema è:
  - Python
  - NI-DAQmx
  - device name
  - canale occupato
  - task non inizializzato

### 3. Taratura analitica su dati reali

Obiettivo:

- passare da una pipeline v1 simulata a una pipeline credibile su segnali veri BTS/NI

Da fare:

- acquisire almeno 3 file reali per ciascun test disponibile
  - `SJ`
  - `CMJ`
  - `DJ`
- confrontare i risultati di `analyze`
- regolare:
  - quiet standing window
  - soglie di onset
  - soglie di takeoff
  - soglie di landing
- verificare se i Volt hanno offset importanti lato sinistro/destra

Acceptance:

- `analyze` non produce eventi implausibili sulla maggior parte dei file reali
- takeoff e landing risultano temporalmente coerenti
- `DJ` produce almeno impact peak, rebound peak e landing peak in modo stabile

### 4. Miglioramento export analitico

Obiettivo:

- rendere l'output utile per confronti successivi e revisioni offline

Da fare:

- aggiungere `*_events.csv`
- separare in modo più chiaro:
  - metadata input
  - summary metrics
  - detected events
- aggiungere un identificativo test stabile

Acceptance:

- da una cartella export si può ricostruire facilmente:
  - chi ha fatto il test
  - quale test era
  - quali metriche sono state calcolate
  - quali eventi sono stati rilevati

### 5. GUI finale solo dopo backend stabile

Obiettivo:

- avere una UI minima ma davvero usabile, senza introdurre latenza o complessità inutile

Da fare dopo il backend:

- GUI come launcher di `record`
- indicatore di segnale semplice e leggero
- un solo grafico live essenziale
- report finale letto dai file generati
- niente logica analitica dentro la UI

Acceptance:

- la UI non diventa il posto in cui fare processing complesso
- tutta la logica critica resta riutilizzabile da CLI

## GitHub Action Plan

Questa sezione può essere trasformata direttamente in issue/milestone.

### Milestone 1 - Windows Hardware Bring-up

- [ ] documentare setup Windows
- [ ] verificare installazione Python 3.12
- [ ] verificare installazione NI-DAQmx
- [ ] testare `record --mode ni`
- [ ] salvare un primo file reale di riferimento

### Milestone 2 - NI Robustness

- [ ] aggiungere comando `probe-ni` o equivalente
- [ ] supportare override del device name
- [ ] migliorare messaggi di errore NI
- [ ] validare il mapping canali su hardware reale

### Milestone 3 - Real Data Analytics

- [ ] raccogliere dataset reale iniziale
- [ ] verificare `SJ`
- [ ] verificare `CMJ`
- [ ] verificare `DJ`
- [ ] tarare quiet standing ed event detection

### Milestone 4 - Report Outputs

- [ ] aggiungere `events.csv`
- [ ] migliorare `summary.csv`
- [ ] definire naming stabile dei test
- [ ] preparare export per confronti storici

### Milestone 5 - Operator UI

- [ ] ridurre la UI a launcher/monitor
- [ ] collegare UI al backend stabile
- [ ] mostrare solo segnale essenziale
- [ ] mostrare report finale già calcolato

## Note pratiche Windows

Per testare su Windows non basta solo Python.

Servono:

1. Python 3.12
2. virtual environment
3. dipendenze Python del progetto
4. NI-DAQmx installato sul sistema
5. NI USB-6211 collegata e riconosciuta

Se manca NI-DAQmx, `nidaqmx` da solo non basta.

## Punto di ripartenza consigliato

Ordine consigliato:

1. portare il repo su un PC Windows
2. creare venv e installare dipendenze
3. installare NI-DAQmx
4. lanciare `record --mode ni`
5. generare un primo file reale
6. usare `inspect` e `analyze` su quel file
7. tarare l'analisi sui dati veri
