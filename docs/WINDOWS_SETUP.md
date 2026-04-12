# Guida Windows passo passo

Questa guida serve per testare la ricezione dati della pedana BTS tramite NI USB-6211 su un PC Windows, con un codice semplice e separato dalla GUI.

## Obiettivo

Verificare in modo affidabile che:

- il driver NI-DAQmx sia installato correttamente
- la NI USB-6211 sia visibile
- i canali analogici vengano letti correttamente
- i totali verticali `P1_total_FZ`, `P2_total_FZ`, `FZ_total` vengano calcolati e salvati

## 1. Installa Python

Installa Python 3.12 per Windows.

Durante l'installazione:

- abilita `Add Python to PATH`

Poi apri PowerShell e verifica:

```powershell
py -3.12 --version
```

## 2. Installa NI-DAQmx

Installa NI-DAQmx sul PC Windows.

Dopo l'installazione:

- collega la NI USB-6211
- apri NI MAX
- verifica che il device compaia
- annota il nome del device, ad esempio `Dev1`

Se il nome e diverso, lo userai nello script con `--device-name`.

## 3. Apri il progetto

Porta il repository su Windows e aprilo in una cartella locale.

Esempio:

```powershell
cd C:\Users\tuo_nome\Documents\AppPedanaVolley
```

## 4. Crea il virtual environment

```powershell
py -3.12 -m venv .venv
```

Se PowerShell blocca gli script:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Attiva il venv:

```powershell
.venv\Scripts\Activate.ps1
```

Aggiorna pip:

```powershell
python -m pip install --upgrade pip
```

## 5. Installa le dipendenze minime

Per il test Windows semplice usa:

```powershell
python -m pip install -r windows_test\requirements.txt
```

## 6. Verifica che Windows veda la NI

Lancia:

```powershell
python windows_test\probe_ni.py
```

Risultato atteso:

- stampa della versione driver
- elenco device trovati
- nome device, ad esempio `Dev1`
- canali `ai0 ... ai15`

Se non vedi nessun device:

- controlla cavo USB
- controlla alimentazione
- verifica NI MAX
- verifica che NI-DAQmx sia installato

## 7. Fai la prima acquisizione di test

Prova semplice sui canali verticali:

```powershell
python windows_test\capture_force_plate.py --device-name Dev1 --duration 5 --channel-set fz --test-type CMJ --first-name Test --last-name Windows
```

Se vuoi leggere tutti i 16 canali:

```powershell
python windows_test\capture_force_plate.py --device-name Dev1 --duration 5 --channel-set all --test-type CMJ
```

## 8. Cosa deve succedere se funziona

Durante la prova vedrai nel terminale qualcosa del tipo:

```text
[  1024/ 39062] P1=+0.842 V  P2=+0.791 V  TOTAL=+1.633 V
```

Alla fine devono comparire tre file in:

```text
windows_test\output\
```

File attesi:

- `*_signals.csv`
- `*_metadata.csv`
- `*.xlsx`

## 9. Come capire se la ricezione dati e giusta

Controlli minimi:

- il file `signals.csv` ha `timestamp_s`
- ci sono i canali `P1_FZ1...P2_FZ4`
- ci sono `P1_total_FZ`, `P2_total_FZ`, `FZ_total`
- i valori non sono tutti piatti a zero
- premendo o caricando la pedana i valori cambiano
- se carichi piu un lato dell'altro, `P1_total_FZ` e `P2_total_FZ` si differenziano

## 10. Errori tipici

### Device non trovato

Messaggio tipico:

- device NI non trovato

Cosa fare:

- controlla NI MAX
- usa il nome giusto in `--device-name`

### Resource reserved

Messaggio tipico:

- canale o device occupato

Cosa fare:

- chiudi NI MAX
- chiudi DAQExpress
- chiudi eventuali altri software NI

### nidaqmx non trovato

Messaggio tipico:

- package Python `nidaqmx` non trovato

Cosa fare:

```powershell
python -m pip install -r windows_test\requirements.txt
```

### Driver NI-DAQmx non disponibile

Messaggio tipico:

- errore nel caricamento NI-DAQmx

Cosa fare:

- reinstalla NI-DAQmx
- riavvia il PC

## 11. Passo successivo dopo il primo test riuscito

Quando questo script funziona, fai così:

1. salva uno o due file reali
2. portali nel flusso principale del progetto
3. usa:

```powershell
python main.py inspect path\to\your_signals.csv
python main.py analyze path\to\your_signals.csv
```

Così verifichi sia la ricezione dati sia la pipeline analitica.
