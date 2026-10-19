qbittorrent-torrentio-plugin
Un potente plugin di ricerca per qBittorrent che interroga Torrentio e IMDb in parallelo tramite multithreading. Zero API, ottimizzato per l'italiano.

🎬 qBittorrent Torrentio Search Plugin (Ultra ITA)
Un motore di ricerca non ufficiale e ad alte prestazioni per qBittorrent che integra l'immenso database di Torrentio direttamente nel tuo client torrent.

Questo script Python colma il divario tra l'ecosistema di Stremio e qBittorrent, permettendoti di cercare film e serie TV in modo infallibile senza dover configurare servizi esterni.

✨ Caratteristiche Principali
🚫 Zero API Key / Zero Account: Nessuna registrazione richiesta. Nessun limite. Nessun servizio Debrid obbligatorio. Funziona "out of the box".

🧠 Motore IMDb Integrato: Risoluzione nativa dei titoli tramite l'API di autocompletamento pubblica di IMDb. Trova sempre il film o la serie corretta, anche se digiti il titolo in italiano.

⚡ Multithreading Parallelo: Elaborazione simultanea delle richieste tramite la libreria concurrent.futures. Risultati caricati in frazioni di secondo.

🇮🇹 Ottimizzato per l'Italia: Filtra e privilegia automaticamente le release con audio italiano o tracce multilingua (MULTi, Dual Audio), interrogando anche tracker nostrani come Il Corsaro Nero.

📊 Parsing Avanzato: Estrazione chirurgica della dimensione dei file (GB/MB) e del numero di seeder, per permettere a qBittorrent di ordinare correttamente i risultati.

🎞️ Metadati Arricchiti: Riconosce e mostra codec video (H264/H265/HEVC/AV1), codec audio (AAC/AC3/EAC3/DTS/TRUEHD/ATMOS/DD) e tag MULTI/Dual Audio direttamente nel nome del risultato.

🏷️ Tag Visivi Chiari: Ogni risultato è etichettato con [ITA], [SUB ITA], [PACK], [1080p], [H265|AAC|MULTI] per una lettura immediata a colpo d'occhio.

🧹 Deduplica Intelligente: Oltre all'infoHash, normalizza il titolo rimuovendo lingua, qualità, codec e source prima del confronto. Elimina i duplicati "mascherati" e mantiene la release con più seeders.

🔍 Filtri Query Inline: Puoi raffinare la ricerca direttamente dalla barra di qBittorrent scrivendo ita, pack, 4k, 1080p, 720p o 480p insieme al titolo. Esempio: Il Padrino 1080p ita.

📅 Riconoscimento Anno: Se scrivi Il Padrino 1972, il plugin estrae l'anno, valida che non sia nel futuro e lo usa per prioritizzare il risultato corretto.

🎌 Supporto Anime (opzionale): Integrazione con l'API di Kitsu per la ricerca anime, attivabile con USE_KITSU_FOR_ANIME = True.

🆕 Novità nella v2.70
Se hai già installato una versione precedente, ecco cosa è cambiato. Non serve reinstallare: qBittorrent aggiornerà il plugin automaticamente al prossimo controllo.

🛡️ Self-Healing Multi-Istanza: Il plugin ora usa due istanze Torrentio (torrentio.strem.fun e torrentio.elfhosted.com). Se una fallisce, passa automaticamente all'altra. Le istanze che rispondono con errori ripetuti vengono messe in "quarantena" per 120 secondi e riprovate a scadenza.

🌐 Fallback Cloudflare tramite Proxy: Quando un'istanza risponde con 403 (blocco Cloudflare), il plugin prova in sequenza una lista di proxy CORS pubblici (allorigins, codetabs, cors.lol, cors.eu.org, corsproxy.io e altri). Primo proxy funzionante vince.

⚡ Rate Limiting Adattivo: Le chiamate HTTP sono serializzate con un intervallo configurabile. Su risposta 429 l'intervallo aumenta automaticamente (fino a 5s); su successo si riduce gradualmente. Il plugin "impara" il ritmo accettato dal server.

💾 Caching Intelligente: Cache TTL separata per le ricerche IMDb (1 ora) e per i risultati Torrentio (5 minuti). Evita richieste ripetute e riduce latenza e rischio di blocco.

⏱️ Timeout Globale: Se una ricerca si trascina troppo (istanze lente + retry + proxy), il plugin interrompe dopo 90 secondi e restituisce quello che ha già raccolto, invece di far aspettare l'utente indefinitamente.

🔧 Fallback URL Pulito: Se l'URL con i filtri Torrentio fallisce, il plugin riprova senza filtri sulla stessa istanza prima di passare oltre.

🎯 Ordinamento per Seeders: I risultati finali vengono ordinati localmente per numero di seeders, indipendentemente dall'ordine di arrivo dei worker.

🧪 Error Typing Strutturato: Ogni errore HTTP viene classificato (blocked, ratelimit, server, timeout, network, invalid_json) e ha una strategia di recovery dedicata.

🧽 Provider Ripuliti: Rimossi rarbg (defunto) e horriblesubs (non più attivo). Aggiunto filtro qualità esteso che esclude anche 480p, other e unknown.

📝 Logging Opzionale su File: Attivabile con DEBUG = True, scrive su /tmp/torrentio_ultra.log senza inquinare l'output di qBittorrent.

🎭 User-Agent Rotanti: Cinque stringhe reali (Chrome, Firefox, Safari, Linux, macOS) per ridurre il fingerprinting.

📋 Configurazione
Tutte le costanti principali sono modificabili direttamente nel file, senza toccare la logica. Le più utili:

Costante	Default	Descrizione
DEBUG	False	Log su file in /tmp
ONLY_ITA	False	Forza solo risultati italiani
SMART_DEDUP	True	Deduplica per titolo normalizzato
SORT_BY_SEEDS	True	Ordina per seeders
GLOBAL_TIMEOUT	90	Timeout totale ricerca (s)
MAX_WORKERS	4	Thread paralleli
HTTP_TIMEOUT / HTTP_RETRIES	10s / 2	Timeout e retry per richiesta
RATE_LIMIT_INTERVAL	1.0	Intervallo base rate limiter (s)
HEALTH_COOLDOWN	120	Cooldown blacklist istanze (s)
USE_PROXY_ON_BLOCK	True	Attiva fallback proxy su 403
USE_KITSU_FOR_ANIME	False	Abilita ricerca anime via Kitsu
⚙️ Come Installare (Metodo Web Link)
Per installare questo plugin, non è necessario scaricare alcun file manualmente. Ti basta usare la funzione di importazione web di qBittorrent.

Apri qBittorrent.

Nota: Se non vedi la scheda Ricerca, vai nel menu in alto: Visualizza → Spunta Motore di ricerca (affinché funzioni, devi avere Python 3 installato sul tuo sistema).

Vai sulla scheda Ricerca e clicca sul pulsante Plugin di ricerca... in basso a destra.

Clicca su Installa un nuovo plugin e seleziona l'opzione Web link.

Incolla il link "Raw" ufficiale del file:

text
https://raw.githubusercontent.com/gigio820373/qbittorrent-torrentio-plugin/main/torrentio.py
Clicca su OK. Il plugin "Torrentio Ultra ITA" apparirà istantaneamente nella lista.

🔄 Aggiornamenti
Dato che il plugin viene installato tramite Web Link, potrai aggiornarlo comodamente in futuro. Ti basterà aprire la finestra dei plugin in qBittorrent e cliccare su Controlla aggiornamenti.

Se hai modificato il codice localmente e vuoi forzare l'aggiornamento all'ultima versione del repository, disinstalla e reinstalla il plugin dal Web Link.

🐛 Segnalazioni e Contributi
Se trovi un bug o vuoi suggerire una funzionalità, apri una Issue su GitHub. Se vuoi contribuire con una modifica, apri una Pull Request.

Prima di segnalare un problema, attiva DEBUG = True nel file, riproduci l'errore e allega il contenuto di /tmp/torrentio_ultra.log: aiuta tantissimo a capire cosa è andato storto.

📜 Disclaimer
Questo progetto è open-source, rilasciato sotto licenza GPL v3 e sviluppato esclusivamente a scopo educativo. Non ospita né trasmette file coperti da copyright.

 e sviluppato esclusivamente a scopo educativo. Non ospita né trasmette file coperti da copyright.
