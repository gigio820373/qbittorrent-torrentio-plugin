# VERSION: 2.00
# AUTHORS: gigio820373
# LICENSING INFORMATION: GPL v3
# DESCRIZIONE: Motore Torrentio Definitivo: Ricerca IMDb Nativa (Zero API esterne) + Multithreading Parallelo.

import urllib.request
import urllib.parse
import json
import re
import concurrent.futures

from novaprinter import prettyPrinter

class torrentio(object):
    url = 'https://torrentio.strem.fun'
    name = 'Torrentio Ultra ITA'
    
    supported_categories = {
        'all': 'all',
        'movies': 'movie',
        'tv': 'series'
    }

    def __init__(self):
        # Configurazioni Torrentio: P2P puro, provider gratuiti, filtro rigido in lingua.
        self.torrentio_base = "https://torrentio.strem.fun/providers=yts,eztv,rarbg,1337x,thepiratebay,kickasstorrents,torrentgalaxy,ilcorsaronero,magnetdl|language=italian,foreign"

    def _extract_season_episode(self, query):
        """Estrae con precisione chirurgica le direttive di Stagione ed Episodio."""
        match = re.search(r'\b(?:s|season\s*)(\d{1,2})\s*(?:e|episode\s*|\times\s*)(\d{1,2})\b', query, re.IGNORECASE)
        if match: 
            return int(match.group(1)), int(match.group(2))
        
        match_alt = re.search(r'\b(\d{1,2})x(\d{1,2})\b', query, re.IGNORECASE)
        if match_alt: 
            return int(match_alt.group(1)), int(match_alt.group(2))
            
        return None, None

    def _search_imdb_direct(self, query, cat):
        """
        Sfrutta l'API di autocompletamento pubblica di IMDb aggirando la necessità
        di qualsiasi API Key o servizio ponte.
        """
        # Creazione di uno "slug" stringa compatibile con l'infrastruttura AWS/WAF di IMDb
        slug = re.sub(r'[^a-z0-9_]', '', query.lower().replace(' ', '_'))
        if not slug: 
            return []
        
        first_char = slug[0]
        imdb_url = f"https://v3.sg.media-imdb.com/suggestion/{first_char}/{slug}.json"
        
        try:
            req = urllib.request.Request(imdb_url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode('utf-8'))
        except Exception:
            return []
            
        results = []
        for item in data.get('d', []):
            imdb_id = item.get('id', '')
            if not imdb_id.startswith('tt'):
                continue
                
            item_type = item.get('qid', '')
            
            # Applicazione logica del filtro categorie di qBittorrent
            if cat == 'movies' and item_type not in ('movie', 'tvMovie'):
                continue
            if cat == 'tv' and item_type not in ('tvSeries', 'tvMiniSeries'):
                continue
                
            content_type = 'series' if item_type in ('tvSeries', 'tvMiniSeries') else 'movie'
            
            results.append({
                'id': imdb_id,
                'title': item.get('l', 'Sconosciuto'),
                'year': item.get('y', ''),
                'type': content_type
            })
            
        return results[:4] # Trattiene solo i 4 candidati più probabili

    def _fetch_stream(self, stream_req):
        """Funzione worker atomica per il multithreading."""
        imdb_id, season, episode, content_type, title, year = stream_req
        
        if content_type == 'series' and season is not None and episode is not None:
            stream_id = f"{imdb_id}:{season}:{episode}"
        else:
            stream_id = imdb_id
            
        req_url = f"{self.torrentio_base}/stream/{content_type}/{stream_id}.json"
        
        try:
            req = urllib.request.Request(req_url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
            with urllib.request.urlopen(req, timeout=8) as response:
                return json.loads(response.read().decode('utf-8')).get('streams', []), title, year, imdb_id, season, episode
        except Exception:
            return [], title, year, imdb_id, season, episode

    def search(self, what, cat='all'):
        raw_query = urllib.parse.unquote(what).strip()
        if not raw_query: 
            return
        
        season, episode = self._extract_season_episode(raw_query)
        
        # Sterilizza la query asportando parametri di episodi prima di inviarla a IMDb
        clean_query = re.sub(r'\b(?:s|season\s*)\d{1,2}\s*(?:e|episode\s*|\times\s*)\d{1,2}\b', '', raw_query, flags=re.IGNORECASE)
        clean_query = re.sub(r'\b\d{1,2}x\d{1,2}\b', '', clean_query, flags=re.IGNORECASE).strip()

        # Step 1: Risoluzione IMDb pura
        imdb_results = self._search_imdb_direct(clean_query, cat)
        if not imdb_results: 
            return

        # Costruzione del pool di richieste
        stream_requests = []
        for item in imdb_results:
            c_type = 'series' if season is not None else item['type']
            stream_requests.append((item['id'], season, episode, c_type, item['title'], item['year']))
            
        # Step 2: Aggregazione Torrentio in Multithreading Parallelo
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(self._fetch_stream, req) for req in stream_requests]
            
            for future in concurrent.futures.as_completed(futures):
                streams, title, year, imdb_id, s, e = future.result()
                year_str = f" ({year})" if year else ""
                
                for stream in streams:
                    raw_title = stream.get('title', '')
                    first_line = raw_title.split('\n')[0] if raw_title else ""
                    provider = stream.get('name', '').replace('\n', ' ').strip()
                    
                    if s and e:
                        display_name = f"[Torrentio] {title} S{s:02d}E{e:02d}{year_str} - {first_line} [{provider}]"
                    else:
                        display_name = f"[Torrentio] {title}{year_str} - {first_line} [{provider}]"
                        
                    # Motore RegEx per l'isolamento dei Seeds
                    seeds = '-1'
                    seeds_match = re.search(r'👤\s*(\d+)', raw_title)
                    if seeds_match: 
                        seeds = seeds_match.group(1)
                        
                    # Conversione Byte Automatica
                    size_bytes = '-1'
                    size_match = re.search(r'💾\s*([\d\.]+)\s*([GMK]?B|GiB|MiB|KiB)', raw_title, re.IGNORECASE)
                    if size_match:
                        val = float(size_match.group(1))
                        unit = size_match.group(2).upper()
                        if 'G' in unit: val *= (1024**3)
                        elif 'M' in unit: val *= (1024**2)
                        elif 'K' in unit: val *= 1024
                        size_bytes = str(int(val))
                        
                    link = stream.get('magnet')
                    if not link and stream.get('infoHash'):
                        link = f"magnet:?xt=urn:btih:{stream.get('infoHash')}"
                        
                    if not link: 
                        continue
                        
                    data_packet = {
                        'link': link,
                        'name': display_name,
                        'size': size_bytes,
                        'seeds': seeds,
                        'leech': '-1',
                        'engine_url': self.url,
                        'desc_link': f"https://www.imdb.com/title/{imdb_id}/",
                        'pub_date': '-1'
                    }
                    
                    prettyPrinter(data_packet)