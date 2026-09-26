# DuoLingual Player

DuoLingual Player je desktopový přehrávač pro Windows určený k současnému poslechu dvou jazykových stop z jednoho MKV. Video běží v jediném okně, zatímco stopa A a stopa B mají vlastní dekódování, převzorkování, buffer, hlasitost, synchronizační posun a fyzický či virtuální zvukový výstup.

Backend nepoužívá VLC. Kontejner a kodeky zpracovává PyAV/FFmpeg, obraz vykreslují základní moduly PySide6 a zvuk jde přes PortAudio (`sounddevice`) do zařízení dostupných ve Windows včetně WASAPI a virtuálních vstupů VoiceMeeter.

## Požadavky

- Windows 10 nebo 11;
- Python 3.10–3.13 (doporučeno 3.12, 64bit);
- dvě zvuková výstupní zařízení;
- MKV se dvěma zvukovými stopami pro plný dvoujazyčný režim.

PyAV z PyPI obvykle obsahuje potřebné knihovny FFmpeg. Samostatná instalace VLC není potřeba.

## Instalace a spuštění

V PowerShellu v adresáři projektu použijte pro virtuální prostředí krátkou cestu mimo Google Drive. PySide6 obsahuje hlubokou adresářovou strukturu a při `.venv` uvnitř tohoto projektu by instalace mohla překročit limit délky cest ve Windows.

```powershell
$venv = "$env:LOCALAPPDATA\DuoLingualPlayer\venv"
py -3.12 -m venv $venv
& "$venv\Scripts\python.exe" -m pip install --upgrade pip
& "$venv\Scripts\python.exe" -m pip install -r requirements.txt
& "$venv\Scripts\python.exe" -m duolingual_player
```

Aktivace prostředí není nutná. Při dalších spuštěních stačí v adresáři projektu poslední příkaz. Alternativně lze použít:

```powershell
& "$env:LOCALAPPDATA\DuoLingualPlayer\venv\Scripts\python.exe" run_player.py
```

Pokud už vznikla neúplná `.venv` uvnitř projektu, není používána a po zavření terminálů ji lze smazat. Druhou možností je systémově zapnout podporu dlouhých cest ve Windows, ale pro tento projekt to není potřeba.

## Použití

1. Klikněte na **Otevřít MKV** a vyberte video.
2. Vpravo nastavte odlišnou **Zvukovou stopu** pro výstup A a B.
3. Pro A a B nastavte dvě různá zařízení. Výstupy WASAPI jsou ve výběru řazeny jako první.
4. Spusťte přehrávání mezerníkem nebo tlačítkem přehrát.
5. Případný rozdíl latence Bluetooth dorovnejte zvlášť pro A a B. Kladná hodnota zvuk zpozdí, záporná jej předsune.

Při odpojení Bluetooth zařízení přehrávač zobrazí chybu. Připojte zařízení, stiskněte **Obnovit zvuková zařízení**, znovu je vyberte a pokračujte. Změna stopy či zařízení během přehrávání znovu sestaví obě audio větve od aktuální pozice.

### Klávesové zkratky

| Klávesa | Akce |
|---|---|
| Mezerník | Přehrát / pauza |
| Šipka vlevo/vpravo | Skok o 5 sekund |
| Shift + šipka | Skok o 30 sekund |
| F | Celá obrazovka |
| Dvojklik na video | Celá obrazovka / návrat do okna |
| Esc | Opuštění celé obrazovky |
| M | Ztlumit / obnovit oba výstupy |
| Ctrl+O | Otevřít soubor |

V menu **Zobrazení → Vyhlazení obrazu** lze zapnout nebo vypnout jemnější interpolaci při zvětšování videa. Ve výchozím stavu je zapnutá. Pomáhá proti viditelným hranám pixelů vzniklým škálováním, nedokáže však odstranit bloky, které už jsou součástí silně komprimovaného zdrojového videa.

## Titulky

V panelu **Titulky** lze vybrat podporovanou vestavěnou textovou stopu MKV nebo načíst externí soubor SRT. Bitmapové titulky (například PGS) se momentálně nevykreslují. U rozsáhlé vestavěné titulkové stopy může první načtení chvíli trvat.

## VoiceMeeter Banana

1. Nainstalujte VoiceMeeter Banana a po instalaci restartujte Windows.
2. Ve VoiceMeeter nastavte vpravo nahoře **A1** a **A2** na dvě fyzická sluchátka. Pro Bluetooth bývá stabilní ovladač `WDM`, případně `MME`, pokud WDM zlobí.
3. V přehrávači vyberte například:
   - výstup A: **Voicemeeter Input (VB-Audio Voicemeeter VAIO)**;
   - výstup B: **Voicemeeter AUX Input (VB-Audio Voicemeeter AUX VAIO)**.
4. Na proužku VAIO ve VoiceMeeter zapněte pouze sběrnici A1 a na proužku AUX pouze A2. Tím se jazyky fyzicky oddělí.
5. Pokud se zařízení nezobrazí, ověřte v nastavení zvuku Windows, že není zakázané, a v aplikaci obnovte seznam zařízení.

VoiceMeeter může přidat jinou latenci než přímý Bluetooth výstup. Použijte posun A/B v milisekundách; obvyklé ladění je po 10–20 ms.

## Diagnostika

Panel zobrazuje hlavní čas, poslední vykreslené PTS videa, PTS obou zvukových výstupů, velikost front a případnou chybu zařízení. Při řešení problémů sledujte zejména, zda audio buffer neklesá trvale k nule a zda vybrané zařízení po odpojení nezmizelo.

## Testy

```powershell
& "$env:LOCALAPPDATA\DuoLingualPlayer\venv\Scripts\python.exe" -m pytest -q
```

Testy pokrývají výchozí výběr rozdílných stop a zařízení, validaci tras a převod synchronizačního posunu z milisekund.

## Architektura

- `core/clock.py` – společný monotónní čas přehrávání;
- `core/media.py` – PyAV probe, demux a dekódovací vlákno;
- `core/audio.py` – dvě instance nezávislé audio pipeline a callback výstupu;
- `core/devices.py` – výčet výstupních zařízení a host API;
- `core/controller.py` – životní cyklus, seek, synchronizace a diagnostika;
- `core/subtitles.py` – SRT a vestavěné textové titulky;
- `ui/` – hlavní okno a vykreslení obrazu/titulků.

## Známá omezení

- Přesná koncová latence závisí na Bluetooth kodeku, ovladači a velikosti hardwarového bufferu. Posun A/B je určen k jejímu ručnímu dorovnání.
- Windows může stejné fyzické zařízení zveřejnit přes více host API. Pro nízkou a předvídatelnou latenci preferujte položku označenou `Windows WASAPI`.
- Některá Bluetooth sluchátka přepnou do úzkopásmového hands-free profilu, pokud je současně používá mikrofon. Pro kvalitní stereo mikrofon sluchátek zakažte nebo nepoužívejte.
- Podporované jsou textové titulky, ne PGS/VobSub bitmapové stopy.
- DRM média a poškozené kontejnery nejsou podporované.
- Aplikace volí první video stopu. Přepínání mezi více video stopami není v této verzi v rozhraní.

## Bezpečné ukončení

Při zavření okna se nejprve zastaví časovač, dekódovací vlákno a oba zvukové streamy. Audio callbacky používají zamčené fronty a neprovádějí žádné operace v GUI vlákně.
