# Architettura — Torrentio Ultra ITA

Documento di riferimento per chi vuole capire come funziona il plugin, come è
strutturato il codice e perché alcune scelte sono state fatte in un certo modo.

---

## 1. Panoramica

Il plugin è un **adattatore** tra qBittorrent e due servizi pubblici:

- l'endpoint di autocompletamento di **IMDb**, usato per tradurre un titolo in un
  identificativo `tt…`;
- **Torrentio**, usato per tradurre un identificativo in una lista di magnet link.

Nessuna API key, nessun account, nessun servizio Debrid. Il plugin opera
interamente nella **standard library** di Python (3.8+), senza dipendenze esterne.

L'installazione avviene tramite Web Link: qBittorrent scarica il file `torrentio.py`
e lo esegue nel proprio processo. Non c'è un demone separato, non ci sono file
di configurazione esterni: tutte le costanti sono attributi di classe modificabili
direttamente nel file.

---

## 2. Pipeline di una ricerca

Il diagramma seguente mostra il percorso di una query dalla barra di ricerca di
qBittorrent fino ai risultati visualizzati.
what (stringa digitata dall'utente)
│
├─► _extract_season_episode ─► (S, E, query pulita)
│
├─► _extract_filters ─► {ita, pack, res}, query ancora più pulita
│
├─► _extract_year ─► (anno, query finale)
│
├─► _find_titles ─► [titolo_1, ..., titolo_N]
│ │
│ ├─ _query_candidates (fallback progressivi sulla query)
│ └─ _search_imdb / _search_kitsu
│ └─ _search_imdb_uncached
│ └─ _http_json
│ ├─ _imdb_circuit_breaker.allow_request()
│ └─ (record_success / record_failure)
│
├─► _make_request (per ogni titolo) ─► richiesta stream pronta
│
└─► _fetch_stream (parallelo, ThreadPoolExecutor)
│
├─ _stream_cache.get(path)
│
└─ _TorrentioClient.fetch_stream(instances, path)
│
├─ _health.get_ordered_instances(instances)
│
└─ per ogni istanza:
└─ _try_instance(base, path)
├─ _http_json(url_con_filtri)
│ ├─ se 403 → _try_proxies(url)
│ └─ se altro → fallback URL pulito
└─ _health.record_success / record_failure

text

Ogni risultato restituito da Torrentio passa infine per `_stream_to_result`, che
estrae i metadati, costruisce il magnet link e formatta il nome visualizzato.
La deduplica (`_dedup_key`) elimina i duplicati prima che i pacchetti raggiungano
`prettyPrinter`.

---

## 3. Moduli e classi

| Simbolo | Ruolo |
|---|---|
| `torrentio` | Orchestratore. Contiene la configurazione, il parsing della query, la deduplica e la formattazione dell'output. |
| `_TorrentioClient` | Solo logica di rete verso Torrentio: istanze multiple, proxy, fallback URL pulito, health tracking. |
| `_CircuitBreaker` | Protegge IMDb dai fallimenti a cascata. Stati: `CLOSED`, `OPEN`, `HALF_OPEN`. |
| `_InstanceHealth` | Blacklist temporanea delle istanze Torrentio che rispondono con errori ripetuti. |
| `_RateLimiter` | Serializza le chiamate HTTP e adatta l'intervallo di attesa in base alle risposte `429`. |
| `_TTLCache` | Cache in-memory con scadenza. Usata per le ricerche IMDb (1 ora) e per gli stream Torrentio (5 minuti). |
| `ParsedStream` | Dataclass con i metadati estratti da uno stream Torrentio: qualità, codec, lingua, seeders, dimensione, ecc. |

---

## 4. Resilienza: quattro livelli

Il plugin è progettato per degradare in modo controllato quando i servizi esterni
non rispondono. I quattro livelli sono indipendenti e si attivano in cascata.

### 4.1 Circuit breaker su IMDb

Se l'endpoint di autocompletamento di IMDb fallisce 5 volte consecutive
(per errori server, timeout, network o rate limit), il circuito si apre per
60 secondi. In quella finestra, le ricerche successive restituiscono una lista
vuota **istantaneamente**, senza toccare la rete e senza far attendere l'utente
per timeout e retry in cascata.

Dopo i 60 secondi, una singola richiesta di prova (`HALF_OPEN`) verifica se il
servizio è tornato disponibile: in caso affermativo il circuito si richiude,
altrimenti si riapre per altri 60 secondi.

Il comportamento è configurabile tramite `IMDB_CB_FAIL_THRESHOLD` e
`IMDB_CB_RECOVERY_TIMEOUT`.

### 4.2 Health tracking su Torrentio

Ogni istanza Torrentio ha un contatore di fallimenti consecutivi. Dopo 2 fallimenti
viene messa in "quarantena" per 120 secondi e riprovata a scadenza. Un errore
`403` (blocco Cloudflare) la mette in quarantena per un periodo triplo (360 secondi).

Quando tutte le istanze sono in quarantena, il plugin continua a provarle in ordine
di scadenza crescente, così la prima che torna disponibile viene usata subito.

### 4.3 Fallback proxy

Quando un'istanza risponde con `403`, il client prova in sequenza una lista di
proxy CORS pubblici (`allorigins`, `codetabs`, `cors.lol`, `cors.eu.org`,
`corsproxy.io` e altri). Il primo che risponde correttamente vince. I proxy hanno
un timeout dedicato più breve (`PROXY_TIMEOUT`) per non bloccare la ricerca su
servizi lenti.

Ogni proxy può richiedere l'URL codificato (`{url}`) o non codificato (`{rawUrl}`):
la funzione `_apply_proxy` gestisce entrambi i formati.

### 4.4 Fallback URL pulito

Se l'URL con i filtri Torrentio fallisce per un errore transitorio (timeout, `5xx`),
il client riprova senza filtri sulla stessa istanza prima di passare alla successiva.
Questo copre i casi in cui i parametri di filtro causano un errore lato server.

---

## 5. Decisioni di design

Le scelte seguenti sono state fatte in modo deliberato. Chi vuole modificare il
plugin dovrebbe conoscerle prima di intervenire.

**Perché `QUALITY_FILTER` esclude `480p`, `other`, `unknown`, `scr`, `cam`?**
L'utente tipico di qBittorrent cerca qualità decente, non screener o telecamere.
Escluderli riduce il rumore e velocizza la selezione. Chi vuole cercare anche
queste qualità può svuotare la costante.

**Perché `TORRENTIO_SORT = 'qualitysize'`?**
Sfrutta l'ordinamento lato server di Torrentio, che tiene conto di qualità e
dimensione file insieme. Riduce la necessità di ordinare localmente e migliora
la qualità percepita dei risultati.

**Perché `SMART_DEDUP` normalizza il titolo?**
Torrentio restituisce spesso lo stesso release da più provider con hash diversi
(es. re-seed). La normalizzazione rimuove lingua, qualità, codec e source dal
nome, lasciando solo il "cuore" del titolo. Due release con lo stesso cuore sono
considerati duplicati.

**Perché il magnet viene costruito partendo da `first_line` e non da `name`?**
`first_line` è il nome effettivo del file torrent, quello che l'utente vede nella
lista. `name` invece è la stringa formattata con i tag `[ITA]`, `[PACK]`, ecc.
Usare `first_line` per il parametro `dn=` rende il magnet più compatibile con
altri client (Deluge, Transmission) che non conoscono i tag del plugin.

**Perché `_fetch_stream` usa un `ThreadPoolExecutor` invece di `asyncio`?**
qBittorrent importa il plugin ed esegue `search()` in modo sincrono. Il plugin
non controlla l'event loop, quindi `asyncio` non è utilizzabile. `concurrent.futures`
è thread-safe e non richiede un loop esterno.

**Perché `MAX_WORKERS = 4` e non di più?**
Oltre 4-5 worker concorrenti, i benefici in latenza sono marginali e il rischio
di essere temporaneamente throttled da Torrentio aumenta. Il valore è configurabile
per chi vuole sperimentare.

**Perché il controllo della versione Python avviene all'import?**
Meglio un errore esplicito con messaggio chiaro all'avvio che un crash oscuro
più avanti (import error, `SyntaxError`, comportamento anomalo). Il check è
economico e non ha impatto sulle performance.

---

## 6. Come estendere

- **Nuovo filtro query**: aggiungere un pattern `RE_TOKEN_*` e il campo
  corrispondente in `_extract_filters`. Aggiornare `_extract_metadata` per
  applicarlo.
- **Nuovo metadato estratto** (es. HDR): aggiungere il campo in `ParsedStream`,
  estrarlo in `_extract_metadata` e usarlo in `_format_display_name` (e in
  `_dedup_key` se ha senso). La dataclass rende immediatamente evidente quali
  punti vanno aggiornati.
- **Nuova istanza Torrentio**: aggiungere l'URL a `TORRENTIO_INSTANCES`. Il
  self-healing la gestisce automaticamente senza altre modifiche.
- **Nuovo proxy**: aggiungere una stringa a `PROXY_URLS`, usando `{url}` o
  `{rawUrl}` a seconda di come il proxy vuole l'URL target.
- **Nuovo provider Torrentio**: aggiungere il nome alla costante `PROVIDERS`,
  separato da virgola. Il plugin lo passerà automaticamente a Torrentio.

---

## 7. Compatibilità

- **qBittorrent**: 4.4+ (testato su 5.x).
- **Python**: 3.8+ (il plugin verifica la versione all'import).
- **Sistema operativo**: qualsiasi, non ci sono dipendenze native.
- **Librerie esterne**: nessuna. Solo standard library.

---

## 8. Licenza

GPL v3. Il progetto è open-source e sviluppato a scopo educativo. Non ospita
né trasmette file coperti da copyright.
