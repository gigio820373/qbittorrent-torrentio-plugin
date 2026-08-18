# qbittorrent-torrentio-plugin
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

⚙️ Come Installare (Metodo Web Link)
Per installare questo plugin, non è necessario scaricare alcun file manualmente. Ti basta usare la funzione di importazione web di qBittorrent.  

Apri qBittorrent.

Nota: Se non vedi la scheda Ricerca, vai nel menu in alto: Visualizza -> Spunta Motore di ricerca (Affinché funzioni, devi avere Python 3 installato sul tuo sistema).  

Vai sulla scheda Ricerca e clicca sul pulsante Plugin di ricerca... in basso a destra.  

Clicca su Installa un nuovo plugin e seleziona l'opzione Web link.  

Incolla il link "Raw" ufficiale del file:
[https://raw.githubusercontent.com/Gian10501/qbittorrent-torrentio-plugin/main/torrentio.py](https://raw.githubusercontent.com/Gian10501/qbittorrent-torrentio-plugin/main/torrentio.py)

Clicca su OK. Il plugin "Torrentio Ultra ITA" apparirà istantaneamente nella lista.  

🔄 Aggiornamenti
Dato che il plugin viene installato tramite Web Link, potrai aggiornarlo comodamente in futuro. Ti basterà aprire la finestra dei plugin in qBittorrent e cliccare su Controlla aggiornamenti.  

Disclaimer: Questo progetto è open-source, rilasciato sotto licenza GPL v3 e sviluppato esclusivamente a scopo educativo. Non ospita né trasmette file coperti da copyright.
