# Windows Test Folder

Questa cartella serve per fare un test semplice e pratico della NI USB-6211 su Windows, senza dipendere dalla GUI del progetto.

## Contenuto

- `probe_ni.py`
  - controlla che NI-DAQmx veda il device
  - stampa nome device e canali analogici disponibili
- `capture_force_plate.py`
  - legge i canali dalla NI
  - mostra i totali verticali in tempo reale nel terminale
  - salva `signals.csv`, `metadata.csv` e `xlsx`
- `requirements.txt`
  - dipendenze minime per questi script

## Workflow consigliato

1. esegui `probe_ni.py`
2. verifica il nome reale del device, ad esempio `Dev1`
3. esegui `capture_force_plate.py`
4. controlla i file creati in `windows_test/output`

## Esempio rapido

```powershell
python windows_test\probe_ni.py
python windows_test\capture_force_plate.py --device-name Dev1 --duration 5 --channel-set fz --test-type CMJ
```
