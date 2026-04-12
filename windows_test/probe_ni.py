from __future__ import annotations

import sys


def main() -> int:
    try:
        import nidaqmx
        from nidaqmx.system import System
    except ImportError:
        print("Errore: package Python 'nidaqmx' non trovato.")
        print("Installa le dipendenze con:")
        print(r"  python -m pip install -r windows_test\requirements.txt")
        return 1

    if not sys.platform.startswith("win"):
        print("Questo script e pensato per Windows.")
        return 1

    try:
        system = System.local()
        devices = list(system.devices)
    except Exception as exc:
        print(f"Errore nel caricamento NI-DAQmx: {exc}")
        print("Verifica che NI-DAQmx sia installato correttamente sul PC Windows.")
        return 1

    print("NI device probe")
    print(f"Driver version: {system.driver_version}")
    print(f"Devices trovati: {len(devices)}")

    if not devices:
        print("Nessun device NI trovato.")
        print("Controlla USB, alimentazione, driver e NI MAX.")
        return 1

    for device in devices:
        print("-" * 60)
        print(f"Name: {device.name}")
        print(f"Product: {device.product_type}")
        print(f"Serial: {getattr(device, 'serial_num', 'n/a')}")
        try:
            ai_channels = [channel.name for channel in device.ai_physical_chans]
            print(f"AI channels: {', '.join(ai_channels)}")
        except Exception:
            print("AI channels: n/a")

    print("-" * 60)
    print("Se il device non si chiama Dev1, usa --device-name nel comando di acquisizione.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
