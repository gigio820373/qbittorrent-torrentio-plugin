qbittorrent-torrentio-plugin
Un potente plugin di ricerca per qBittorrent che interroga Torrentio e IMDb in parallelo tramite multithreading. Zero API, ottimizzato per l'italiano.

**Versione corrente:** v3.09 — stabile, testata, senza dipendenze esterne.

## 🎬 qBittorrent Torrentio Search Plugin (Ultra ITA)

Un motore di ricerca non ufficiale e ad alte prestazioni per qBittorrent che integra l'immenso database di Torrentio direttamente nel tuo client torrent.

Questo script Python colma il divario tra l'ecosistema di Stremio e qBittorrent, permettendoti di cercare film e serie TV in modo infallibile senza dover configurare servizi esterni.

## ✨ Caratteristiche Principali

- 🚫 **Zero API Key / Zero Account**: Nessuna registrazione richiesta. Nessun limite. Nessun servizio Debrid obbligatorio. Funziona "out of the box".
- 🧠 **Motore IMDb Integrato**: Risoluzione nativa dei titoli tramite l'API di autocompletamento pubblica di IMDb. Trova sempre il film o la serie corretta, anche se digiti il titolo in italiano.
- ⚡ **Multithreading Parallelo**: Elaborazione simultanea delle richieste tramite `concurrent.futures`. Risultati caricati in frazioni di secondo.
- 🇮🇹 **Ottimizzato per l'Italia**: Filtra e privilegia automaticamente le release con audio italiano o tracce multilingua (MULTI, Dual Audio), interrogando anche tracker nostrani come Il Corsaro Nero.
- 📊 **Parsing Avanzato**: Estrazione chirurgica di dimensione file (GB/MB), seeders e risoluzione, per permettere a qBittorrent di ordinare correttamente i risultati.
- 🎞️ **Metadati Arricchiti**: Riconosce e mostra codec video (H264/H265/HEVC/AV1), codec audio (AAC/AC3/EAC3/DTS/TRUEHD/ATMOS/DD) e numero di canali (2.0, 5.1, 7.1) direttamente nel nome del risultato.
- 🏷️ **Tag Visivi Chiari**: Ogni risultato è etichettato con tag leggibili, con il codec audio **in testa** per identificare subito la qualità della traccia:
  `[DDP 5.1] [ITA] [4k] [H265] Dune (2021)`
  `[TrueHD 7.1 ATMOS] [MULTI] [4k] [AV1] Blade Runner 2049 (2017)`
- 🧹 **Deduplica Intelligente**: Oltre all'`infoHash`, normalizza il titolo includendo risoluzione, codec video, codec audio e lingua. Elimina i veri duplicati e mantiene la release con più seeders, senza scartare release legittimamente diverse (4K vs 1080p, H265 vs H264, ITA vs ENG).
- 🔍 **Filtri Query Inline**: Puoi raffinare la ricerca direttamente dalla barra di qBittorrent scrivendo `ita`, `pack`, `4k`, `1080p`, `720p` o `480p` insieme al titolo. Esempio: `Il Padrino 1080p ita`.
- 📅 **Riconoscimento Anno**: Se scrivi `Il Padrino 1972`, il plugin estrae l'anno, valida che non sia nel futuro e lo usa per prioritizzare il risultato corretto.
- 🗂️ **Ordinamento a Fasce**: I risultati sono ordinati per lingua (tutti gli ITA prima, poi SUB ITA, poi altre lingue), poi per risoluzione (4K → 2K → 1080p), poi per dimensione decrescente, infine per seeders.
- 🎚️ **Filtro Risoluzione Minima**: Per film e serie, i risultati sotto 1080p vengono scartati automaticamente. Configurabile o disattivabile.
- 🎌 **Supporto Anime (opzionale)**: Integrazione con l'API di Kitsu per la ricerca anime, attivabile con `USE_KITSU_FOR_ANIME = True`.
- ⚙️ **Configurazione automatica**: al primo avvio crea `torrentio.json` accanto al plugin. Le modifiche sopravvivono agli aggiornamenti.
- 💾 **Persistenza stato**: cache, health tracker, circuit breaker e rate limiter sopravvivono tra ricerche diverse.

## 🆕 Cronologia delle Novità

### 🆕 Novità nella v3.09

Aggiornamento di correzione (bug fix) focalizzato sull'accuratezza della lingua nei risultati. Nessuna nuova funzionalità visibile, ma un comportamento finalmente corretto.

- 🐛 **Risolto il bug dei falsi `[ITA]`**: In precedenza, i file che contenevano *solo sottotitoli italiani* (es. `Movie.2023.1080p.SUB.ITA`) venivano erroneamente taggati come `[ITA]` (suggerendo la presenza di audio italiano), quando in realtà l'audio era in inglese. Questo accadeva perché il plugin si fidava ciecamente del filtro lato server di Torrentio (`language=italian`), che a volte include release con soli sottotitoli o con audio originale e traccia ITA secondaria.
- 🛡️ **`TRUST_LANGUAGE_FILTER` ora è `False` di default**: Il plugin non presume più che un file sia in italiano solo perché arriva da Torrentio. Ora controlla il nome del file: se c'è scritto `SUB ITA` verrà mostrato `[SUB ITA]`; se c'è scritto `ITA` verrà mostrato `[ITA]`; se non c'è nessuna indicazione di lingua, il tag lingua non verrà aggiunto.
- 🎯 **Deduplica più pulita**: Ora che i falsi `[ITA]` sono stati eliminati, anche l'ordinamento a fasce (che mette gli ITA in cima) è molto più affidabile e non "sporca" la lista con file in inglese.

> **Nota per gli utenti esistenti:** Se nel tuo file `torrentio.json` avevi forzato `"TRUST_LANGUAGE_FILTER": true` (magari per cercare di risolvere i falsi ITA in passato), ti consigliamo di riportarlo a `false` per beneficiare della correzione. Se invece preferisci il vecchio comportamento (fidarsi ciecamente di Torrentio), puoi impostarlo nuovamente a `true` dal file JSON.

### 🆕 Novità nella v3.08

Aggiornamento che porta il plugin da "motore solido" a "motore solido, sicuro, configurabile e persistente". Il cuore della ricerca è lo stesso della v3.00, ma cambia molto di ciò che l'utente vede e di come il plugin si comporta tra una ricerca e l'altra.

- 🎯 **Nome del risultato e ordinamento**:
  - 🎧 **Audio in testa al nome**: il tag audio (codec + canali + Atmos) è ora il primo elemento visibile.
  - 🏷️ **Nuovo tag `[MULTI]`**: quando un release contiene audio italiano **e** un codec premium (TrueHD / DTS-HD MA / Atmos), viene taggato `[MULTI]` invece di `[ITA]`.
  - 🧹 **Nome pulito**: il nome visualizzato non include più il suffisso del release (`The.Lord.of.the.Rings.2001.2160p...`) né il nome del tracker.
  - 🗂️ **Ordinamento a fasce**: lingua (ITA → SUB ITA → altre) → risoluzione (4K → 1440p → 1080p) → dimensione decrescente → seeders.
  - 🎚️ **Filtro risoluzione minima**: per film e serie, i risultati sotto `1080p` vengono scartati.
- 🧹 **Deduplica e qualità**:
  - 🧹 **Deduplica corretta**: dedup per `infoHash` sempre, poi dedup per titolo includendo risoluzione, codec e lingua.
  - 🔁 **Retry query originale**: se i filtri inline svuotano la query, il plugin riprova con la query originale.
  - 🎬 **Ricerca serie multi-stagione**: nuova opzione `SEARCH_ALL_SEASONS`.
  - 🔇 **`ONLY_ITA_AUDIO`**: esclude i risultati con solo sottotitoli italiani.
- 🔒 **Sicurezza**:
  - 🛡️ **Validazione magnet**: accettati solo magnet con schema corretto e hash validi.
  - 💾 **Cache IMDb onesta**: gli errori di rete non vengono più cachati per un'ora.
- ⚙️ **Configurazione e persistenza**:
  - ⚙️ **`torrentio.json`**: configurazione esterna che sopravvive agli aggiornamenti.
  - 💾 **Persistenza stato**: cache e tracker salvati in `torrentio_state.json` e ricaricati tra una ricerca e l'altra.

### 🆕 Novità nella v3.00

Aggiornamento di solidificazione: il plugin diventa **testabile, diagnosticabile e resiliente a livello industriale**.

- 🔌 **Circuit Breaker su IMDb**: se l'endpoint fallisce 5 volte consecutive, il circuito si apre per 60 secondi.
- 🧱 **Client Torrentio separato**: logica di rete isolata in una classe dedicata.
- 📦 **ParsedStream tipizzato**: metadati estratti con dataclass esplicite.
- 🐍 **Check versione Python**: errore chiaro all'avvio su versioni < 3.8.

### 🆕 Novità nella v2.70

- 🛡️ **Self-Healing Multi-Istanza**: due istanze Torrentio con quarantena automatica.
- 🌐 **Fallback Cloudflare tramite Proxy**: fallback su proxy pubblici in caso di blocco 403.
- ⚡ **Rate Limiting Adattivo**: l'intervallo si adatta automaticamente ai 429.
- 💾 **Caching Intelligente**: cache TTL per IMDb e stream.
- ⏱️ **Timeout Globale**: interruzione della ricerca oltre i 90 secondi.

## 📋 Configurazione

Tutte le costanti principali sono modificabili. Il modo consigliato è **il file `torrentio.json`** che il plugin crea accanto a sé: le modifiche lì sopravvivono agli aggiornamenti, mentre quelle nel `.py` vengono sovrascritte.

| Costante | Default | Descrizione |
|---|---|---|
| `DEBUG` | `False` | Log su file in `/tmp` (o `%TEMP%`) |
| `ONLY_ITA` | `False` | Forza solo risultati italiani |
| `ONLY_ITA_AUDIO` | `False` | Esclude i risultati con solo sottotitoli italiani |
| `TRUST_LANGUAGE_FILTER` | `False` | Tagga `[ITA]`/`[MULTI]` anche senza token esplicito nel nome |
| `SMART_DEDUP` | `True` | Deduplica per titolo + risoluzione + codec + audio + lingua |
| `SORT_STRATEGY` | `'ita_then_size'` | `'seeds'`, `'ita_then_size'` o `'ita_then_seeds'` |
| `MIN_SEEDS_FOR_PRIORITY` | `0` | Sotto questa soglia un ITA perde la priorità (0 = mai) |
| `MIN_RESOLUTION` | `'1080p'` | Risoluzione minima per film e serie (`'720p'`, `'1440p'`, `'4k'`, `None`) |
| `STRICT_RESOLUTION` | `False` | Scarta anche i risultati senza risoluzione riconoscibile |
| `GLOBAL_TIMEOUT` | `90` | Soft deadline della ricerca (s) |
| `MAX_WORKERS` | `4` | Thread paralleli |
| `HTTP_TIMEOUT` / `HTTP_RETRIES` | `10s` / `2` | Timeout e retry per richiesta |
| `RATE_LIMIT_INTERVAL` | `1.0` | Intervallo base rate limiter (s) |
| `HEALTH_COOLDOWN` | `120` | Cooldown blacklist istanze (s). Su 403 è 3× (360s) |
| `USE_PROXY_ON_BLOCK` | `True` | Attiva fallback proxy su 403 |
| `CACHE_ENABLED` | `True` | Abilita cache IMDb (1h) e stream (5min) |
| `SEARCH_ALL_SEASONS` | `False` | Cerca tutte le stagioni 1..`MAX_SEASONS` se non ne specifichi una |
| `MAX_SEASONS` | `10` | Limite massimo di stagioni da cercare |
| `USE_KITSU_FOR_ANIME` | `False` | Abilita ricerca anime via Kitsu |
| `SHOW_RELEASE_SUFFIX` | `False` | Mostra il nome completo del release dopo il titolo |
| `SHOW_TRACKER_IN_NAME` | `False` | Mostra `[Tracker]` in coda al nome |
| `SHOW_AUDIO_INFO` | `True` | Mostra il tag audio in testa |
| `IMDB_CB_FAIL_THRESHOLD` | `5` | Fallimenti IMDb consecutivi prima di aprire il circuit breaker |
| `IMDB_CB_RECOVERY_TIMEOUT` | `60.0` | Secondi di attesa prima del tentativo di recupero IMDb |
| `CONFIG_ENABLED` | `True` | Legge `torrentio.json` accanto al plugin |
| `PERSIST_STATE` | `True` | Salva/ricarica lo stato in `torrentio_state.json` |

## 🎛️ Configurazione automatica

Al primo avvio, il plugin crea accanto al file `torrentio.py` un file **`torrentio.json`** con tutte le impostazioni ai valori di default. Puoi modificarlo con qualsiasi editor di testo.

**Le modifiche a `torrentio.json` sopravvivono agli aggiornamenti del plugin.** Quando aggiorni da Web Link, il `.py` viene sostituito ma il `.json` resta intatto.

Esempio:
```json
{
  "ONLY_ITA": true,
  "ONLY_ITA_AUDIO": true,
  "MIN_RESOLUTION": "1080p",
  "SEARCH_ALL_SEASONS": true,
  "MAX_SEASONS": 5,
  "RATE_LIMIT_INTERVAL": 1.5,
  "SHOW_TRACKER_IN_NAME": true
}
Le chiavi sconosciute vengono ignorate. Se il file è malformato, il plugin lo ignora e continua con i default (log con DEBUG = True). Per disattivare la configurazione esterna, imposta CONFIG_ENABLED = False nel .py.

Come verificare che il JSON venga letto: modifica una costante con effetto visibile immediato (es. "SHOW_TRACKER_IN_NAME": true), salva, fai una nuova ricerca. Se i nomi finiscono con [1337x], [Il Corsaro Nero], ecc., il JSON è stato applicato. Se non cambia nulla, controlla che il nome sia esattamente torrentio.json (non .json.txt), che la sintassi sia valida, e che il file sia nella stessa cartella del .py che qBittorrent sta eseguendo.

💾 Persistenza dello stato
Il plugin salva lo stato in torrentio_state.json nella cartella temporanea del sistema (/tmp su Linux, %TEMP% su Windows). Contiene:

Cache delle ricerche IMDb e dei risultati Torrentio (funziona tra una ricerca e l'altra)

Health tracker delle istanze Torrentio (le istanze in quarantena restano tali anche alla ricerca successiva)

Circuit breaker IMDb (accumula fallimenti tra ricerche diverse)

Intervallo appreso dal rate limiter adattivo

La scrittura è atomica (file temporaneo + os.replace), quindi un crash a metà scrittura non corrompe il file. Se lo stato è corrotto o il disco è pieno, il plugin lo ignora e continua senza persistenza. Per disattivarla, imposta PERSIST_STATE = False nel .py o nel JSON.

⚙️ Come Installare
Ci sono due modi per installare il plugin. Entrambi richiedono che qBittorrent abbia il motore di ricerca abilitato e che Python sia installato sul sistema.

Prerequisiti (Fondamentali)
qBittorrent 4.4 o superiore (consigliata la versione 5.x).

Python 3.8+ installato. Su Windows, le versioni recenti di qBittorrent (5.0+) richiedono Python 3.13 per far funzionare i plugin di ricerca. Se non hai Python, scaricalo da python.org e assicurati di spuntare "Add Python to PATH" durante l'installazione.

Scheda Ricerca abilitata: se non la vedi, vai nel menu in alto Visualizza → Motore di ricerca.

Metodo A — Web Link (Consigliato)
Questo metodo è il più semplice: qBittorrent scarica il plugin direttamente dal repository e lo tiene aggiornabile automaticamente.

Nella scheda Ricerca, clicca sul pulsante Plugin di ricerca... in basso a destra.

Clicca su Installa un nuovo plugin e seleziona l'opzione Web link.

Incolla il link "Raw" ufficiale del file:

text
https://raw.githubusercontent.com/gigio820373/qbittorrent-torrentio-plugin/main/torrentio.py
Clicca OK. Il plugin "Torrentio Ultra ITA" apparirà istantaneamente nella lista.

Nota sugli aggiornamenti: il plugin installato via Web Link può essere aggiornato comodamente. Ti basterà aprire la finestra dei plugin in qBittorrent e cliccare su Controlla aggiornamenti.

Metodo B — File Locale (Manuale)
Utile se preferisci scaricare il file manualmente o se il link diretto non è raggiungibile.

Apri il link del plugin nel browser:

text
https://raw.githubusercontent.com/gigio820373/qbittorrent-torrentio-plugin/main/torrentio.py
Salva la pagina con "Salva con nome..." e assicurati che il file abbia estensione .py (es. torrentio.py). Se il browser salva come .txt, rinominalo.

In qBittorrent, vai nella scheda Ricerca e clicca Plugin di ricerca....

Clicca Installa un nuovo plugin e seleziona File locale.

Seleziona il file torrentio.py che hai appena salvato. Il plugin apparirà nella lista.

Per aggiornare in futuro con questo metodo, ripeti i passaggi: scarica la nuova versione e reinstallala sopra quella vecchia.

Verifica che funzioni
Dopo l'installazione, fai una ricerca di prova (es. Il Padrino 1972). Se compaiono risultati, il plugin è correttamente installato e Python è configurato bene. Se la ricerca non restituisce nulla:

Controlla di avere Python installato e nel PATH.

Attiva DEBUG = True (nel torrentio.json o nel .py), ripeti la ricerca e controlla il file di log in /tmp/torrentio_ultra.log (su Windows, %TEMP%\torrentio_ultra.log).

Se il file di log non viene creato, il plugin non è stato caricato correttamente: verifica la versione di Python e reinstalla.

🛠️ Sviluppo e Test
Per dettagli su architettura, flusso di una ricerca, strategie di resilienza e decisioni di design, vedi ARCHITECTURE.md.

🐛 Segnalazioni e Contributi
Se trovi un bug o vuoi suggerire una funzionalità, apri una Issue su GitHub. Se vuoi contribuire con una modifica, apri una Pull Request.

Prima di segnalare un problema, attiva DEBUG = True, riproduci l'errore e allega il contenuto di /tmp/torrentio_ultra.log: aiuta tantissimo a capire cosa è andato storto.

📜 Disclaimer
Questo progetto è open-source, rilasciato sotto licenza GPL v3 e sviluppato esclusivamente a scopo educativo. Non ospita né trasmette file coperti da copyright.
