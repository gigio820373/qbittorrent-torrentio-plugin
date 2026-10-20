qbittorrent-torrentio-plugin
Un potente plugin di ricerca per qBittorrent che interroga Torrentio e IMDb in parallelo tramite multithreading. Zero API, ottimizzato per l'italiano.

**Versione corrente:** v3.00 — stabile, testata, senza dipendenze esterne.

## 🎬 qBittorrent Torrentio Search Plugin (Ultra ITA)

Un motore di ricerca non ufficiale e ad alte prestazioni per qBittorrent che integra l'immenso database di Torrentio direttamente nel tuo client torrent.

Questo script Python colma il divario tra l'ecosistema di Stremio e qBittorrent, permettendoti di cercare film e serie TV in modo infallibile senza dover configurare servizi esterni.

## ✨ Caratteristiche Principali

- 🚫 **Zero API Key / Zero Account**: Nessuna registrazione richiesta. Nessun limite. Nessun servizio Debrid obbligatorio. Funziona "out of the box".
- 🧠 **Motore IMDb Integrato**: Risoluzione nativa dei titoli tramite l'API di autocompletamento pubblica di IMDb. Trova sempre il film o la serie corretta, anche se digiti il titolo in italiano.
- ⚡ **Multithreading Parallelo**: Elaborazione simultanea delle richieste tramite la libreria `concurrent.futures`. Risultati caricati in frazioni di secondo.
- 🇮🇹 **Ottimizzato per l'Italia**: Filtra e privilegia automaticamente le release con audio italiano o tracce multilingua (MULTi, Dual Audio), interrogando anche tracker nostrani come Il Corsaro Nero.
- 📊 **Parsing Avanzato**: Estrazione chirurgica della dimensione dei file (GB/MB) e del numero di seeder, per permettere a qBittorrent di ordinare correttamente i risultati.
- 🎞️ **Metadati Arricchiti**: Riconosce e mostra codec video (H264/H265/HEVC/AV1), codec audio (AAC/AC3/EAC3/DTS/TRUEHD/ATMOS/DD) e tag MULTI/Dual Audio direttamente nel nome del risultato.
- 🏷️ **Tag Visivi Chiari**: Ogni risultato è etichettato con `[ITA]`, `[SUB ITA]`, `[PACK]`, `[1080p]`, `[H265|AAC|MULTI]` per una lettura immediata a colpo d'occhio.
- 🧹 **Deduplica Intelligente**: Oltre all'`infoHash`, normalizza il titolo rimuovendo lingua, qualità, codec e source prima del confronto. Elimina i duplicati "mascherati" e mantiene la release con più seeders.
- 🔍 **Filtri Query Inline**: Puoi raffinare la ricerca direttamente dalla barra di qBittorrent scrivendo `ita`, `pack`, `4k`, `1080p`, `720p` o `480p` insieme al titolo. Esempio: `Il Padrino 1080p ita`.
- 📅 **Riconoscimento Anno**: Se scrivi `Il Padrino 1972`, il plugin estrae l'anno, valida che non sia nel futuro e lo usa per prioritizzare il risultato corretto.
- 🎌 **Supporto Anime (opzionale)**: Integrazione con l'API di Kitsu per la ricerca anime, attivabile con `USE_KITSU_FOR_ANIME = True`.

## 🆕 Novità nella v2.70

Se hai già installato una versione precedente, ecco cosa è cambiato. Non serve reinstallare: qBittorrent aggiornerà il plugin automaticamente al prossimo controllo.

- 🛡️ **Self-Healing Multi-Istanza**: Il plugin ora usa due istanze Torrentio (`torrentio.strem.fun` e `torrentio.elfhosted.com`). Se una fallisce, passa automaticamente all'altra. Le istanze che rispondono con errori ripetuti vengono messe in "quarantena" per 120 secondi e riprovate a scadenza.
- 🌐 **Fallback Cloudflare tramite Proxy**: Quando un'istanza risponde con `403` (blocco Cloudflare), il plugin prova in sequenza una lista di proxy CORS pubblici (`allorigins`, `codetabs`, `cors.lol`, `cors.eu.org`, `corsproxy.io` e altri). Primo proxy funzionante vince.
- ⚡ **Rate Limiting Adattivo**: Le chiamate HTTP sono serializzate con un intervallo configurabile. Su risposta `429` l'intervallo aumenta automaticamente (fino a 5s); su successo si riduce gradualmente. Il plugin "impara" il ritmo accettato dal server.
- 💾 **Caching Intelligente**: Cache TTL separata per le ricerche IMDb (1 ora) e per i risultati Torrentio (5 minuti). Evita richieste ripetute e riduce latenza e rischio di blocco.
- ⏱️ **Timeout Globale**: Se una ricerca si trascina troppo (istanze lente + retry + proxy), il plugin interrompe dopo 90 secondi e restituisce quello che ha già raccolto, invece di far aspettare l'utente indefinitamente.
- 🔧 **Fallback URL Pulito**: Se l'URL con i filtri Torrentio fallisce, il plugin riprova senza filtri sulla stessa istanza prima di passare oltre.
- 🎯 **Ordinamento per Seeders**: I risultati finali vengono ordinati localmente per numero di seeders, indipendentemente dall'ordine di arrivo dei worker.
- 🧪 **Error Typing Strutturato**: Ogni errore HTTP viene classificato (`blocked`, `ratelimit`, `server`, `timeout`, `network`, `invalid_json`) e ha una strategia di recovery dedicata.
- 🧽 **Provider Ripuliti**: Rimossi `rarbg` (defunto) e `horriblesubs` (non più attivo). Aggiunto filtro qualità esteso che esclude anche `480p`, `other` e `unknown`.
- 📝 **Logging Opzionale su File**: Attivabile con `DEBUG = True`, scrive su `/tmp/torrentio_ultra.log` senza inquinare l'output di qBittorrent.
- 🎭 **User-Agent Rotanti**: Cinque stringhe reali (Chrome, Firefox, Safari, Linux, macOS) per ridurre il fingerprinting.

## 🆕 Novità nella v3.00

Aggiornamento di solidificazione: nessuna nuova funzionalità visibile, ma il plugin diventa **testabile, diagnosticabile e resiliente a livello industriale**. Il motore è lo stesso della v2.70; cambia ciò che sta sotto il cofano.

- 🔌 **Circuit Breaker su IMDb**: se l'endpoint IMDb fallisce 5 volte consecutive (server down, timeout, network), il plugin apre il circuito per 60 secondi. Le ricerche successive tornano vuote **istantaneamente**, senza far attendere l'utente per timeout+retry in cascata. Dopo i 60 secondi, una richiesta di prova verifica se il servizio è tornato disponibile.
- 🧱 **Client Torrentio separato**: la logica di rete (istanze multiple, proxy, fallback) è stata estratta in una classe dedicata `_TorrentioClient`. Comportamento identico alla v2.70, ma il codice è ora testabile in isolamento.
- 📦 **ParsedStream tipizzato**: i metadati estratti da uno stream non sono più un dizionario con chiavi arbitrarie, ma una dataclass con campi espliciti. Se in futuro aggiungi una metrica (es. HDR), il type checker ti segnala tutti i punti da aggiornare.
- 📚 **Documentazione architetturale**: nuovo file `ARCHITECTURE.md` che spiega pipeline di ricerca, ruolo di ogni classe, strategie di resilienza e motivazioni delle scelte di design.
- 🐍 **Check versione Python**: se il plugin viene caricato su Python < 3.8, solleva un errore chiaro all'avvio invece di fallire in modo oscuro.
- 🐛 **Bug fix minori**: `_RateLimiter` espone `current` come property thread-safe; il circuit breaker IMDb riceve correttamente `record_success`/`record_failure` in base all'esito delle chiamate.

## 📋 Configurazione

Tutte le costanti principali sono modificabili direttamente nel file, senza toccare la logica. Le più utili:

| Costante | Default | Descrizione |
|---|---|---|
| `DEBUG` | `False` | Log su file in `/tmp` |
| `ONLY_ITA` | `False` | Forza solo risultati italiani |
| `SMART_DEDUP` | `True` | Deduplica per titolo normalizzato |
| `SORT_BY_SEEDS` | `True` | Ordina per seeders |
| `GLOBAL_TIMEOUT` | `90` | Timeout totale ricerca (s) |
| `MAX_WORKERS` | `4` | Thread paralleli |
| `HTTP_TIMEOUT` / `HTTP_RETRIES` | `10s` / `2` | Timeout e retry per richiesta |
| `RATE_LIMIT_INTERVAL` | `1.0` | Intervallo base rate limiter (s) |
| `HEALTH_COOLDOWN` | `120` | Cooldown blacklist istanze (s) |
| `USE_PROXY_ON_BLOCK` | `True` | Attiva fallback proxy su 403 |
| `USE_KITSU_FOR_ANIME` | `False` | Abilita ricerca anime via Kitsu |
| `IMDB_CB_FAIL_THRESHOLD` | `5` | Fallimenti IMDb consecutivi prima di aprire il circuit breaker |
| `IMDB_CB_RECOVERY_TIMEOUT` | `60.0` | Secondi di attesa prima del tentativo di recupero IMDb |

## ⚙️ Come Installare

Ci sono due modi per installare il plugin. Entrambi richiedono che qBittorrent abbia il **motore di ricerca abilitato** e che **Python** sia installato sul sistema.

### Prerequisiti

1. **qBittorrent 4.4 o superiore** (consigliata la versione 5.x).
2. **Python 3.8+** installato. Su Windows, le versioni recenti di qBittorrent (5.0+) richiedono **Python 3.13** per far funzionare i plugin di ricerca. Se non hai Python, scaricalo da [python.org](https://www.python.org/downloads/) e assicurati di spuntare **"Add Python to PATH"** durante l'installazione.
3. **Scheda Ricerca abilitata**: se non la vedi, vai nel menu in alto **Visualizza → Motore di ricerca**.

### Metodo A — Web Link (consigliato)

Questo metodo è il più semplice: qBittorrent scarica il plugin direttamente dal repository e lo tiene aggiornabile.

1. Nella scheda **Ricerca**, clicca sul pulsante **Plugin di ricerca...** in basso a destra.
2. Clicca su **Installa un nuovo plugin** e seleziona **Web link**.
3. Incolla il link "Raw" ufficiale:
https://raw.githubusercontent.com/gigio820373/qbittorrent-torrentio-plugin/main/torrentio.py

text
4. Clicca **OK**. Il plugin **"Torrentio Ultra ITA"** apparirà nella lista.

> **Nota sugli aggiornamenti**: il plugin installato via Web Link può essere aggiornato comodamente. Ti basterà aprire la finestra dei plugin in qBittorrent e cliccare su **Controlla aggiornamenti**.

### Metodo B — File locale

Utile se preferisci scaricare il file manualmente o se il link diretto non è raggiungibile.

1. Apri il link del plugin nel browser:
https://raw.githubusercontent.com/gigio820373/qbittorrent-torrentio-plugin/main/torrentio.py

text
2. Salva la pagina con **"Salva con nome..."** e assicurati che il file abbia estensione **`.py`** (es. `torrentio.py`). Se il browser salva come `.txt`, rinominalo.
3. In qBittorrent, vai nella scheda **Ricerca** e clicca **Plugin di ricerca...**.
4. Clicca **Installa un nuovo plugin** e seleziona **File locale**.
5. Seleziona il file `torrentio.py` che hai appena salvato. Il plugin apparirà nella lista.

Per aggiornare in futuro con questo metodo, ripeti i passaggi: scarica la nuova versione e reinstallala sopra quella vecchia.

### Verifica che funzioni

Dopo l'installazione, fai una ricerca di prova (es. `Il Padrino 1972`). Se compaiono risultati, il plugin è correttamente installato e Python è configurato bene. Se la ricerca non restituisce nulla:

- Controlla di avere Python installato e nel `PATH`.
- Attiva `DEBUG = True` nel file del plugin, ripeti la ricerca e controlla il file di log in `/tmp/torrentio_ultra.log` (su Windows, `%TEMP%\torrentio_ultra.log`).
- Se il file di log non viene creato, il plugin non è stato caricato correttamente: verifica la versione di Python e reinstalla.

## 🛠️ Sviluppo e Test

Per dettagli su architettura, flusso di una ricerca, strategie di resilienza e decisioni di design, vedi [`ARCHITECTURE.md`](ARCHITECTURE.md).

## 🐛 Segnalazioni e Contributi

Se trovi un bug o vuoi suggerire una funzionalità, apri una **Issue** su GitHub. Se vuoi contribuire con una modifica, apri una **Pull Request**.

Prima di segnalare un problema, attiva `DEBUG = True` nel file, riproduci l'errore e allega il contenuto di `/tmp/torrentio_ultra.log`: aiuta tantissimo a capire cosa è andato storto.

## 📜 Disclaimer

Questo progetto è open-source, rilasciato sotto licenza **GPL v3** e sviluppato esclusivamente a scopo educativo. Non ospita né trasmette file coperti da copyright.

