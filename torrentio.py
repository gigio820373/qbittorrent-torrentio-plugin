# VERSION: 2.10
# AUTHORS: gigio820373
# LICENSING INFORMATION: GPL v3
# DESCRIZIONE: Motore Torrentio Definitivo: Ricerca IMDb Nativa (Zero API) + Multithreading + Fix URL Parsing.

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
        # Configurazioni Torrentio: Il carattere pipe (|) DEVE essere codificato come %7C per evitare eccezioni urllib.error.InvalidURL su Python 3.12+
        self.torrentio_base = "https://torrentio.strem.fun/providers=yts,eztv,rarbg,1337x,thepiratebay,kickasstorrents,torrentgalaxy,ilcorsaronero,magnetdl%7Clanguage=italian"

    def _get_headers(self):
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7'
        }

    def _extract_season_episode(self, query):
        match = re.search(r'\b(?:s|season\s*)(\d{1,2})\s*(?:e|episode\s*|\times\s*)(\d{1,2})\b', query, re.IGNORECASE)
        if match: 
            return int(match.group(1)), int(match.group(2))
        
        match_alt = re.search(r'\b(\d{1,2})x(\d{1,2})\b', query, re.IGNORECASE)
        if match_alt: 
            return int(match_alt.group(1)), int(match_alt.group(2))
            
        return None, None

    def _search_imdb_direct(self, query, cat):
        slug = re.sub(r'[^a-z0-9_]', '', query.lower().replace(' ', '_'))
        if not slug: 
            return []
        
        first_char = slug[0]
        imdb_url = f"https://v3.sg.media-imdb.com/suggestion/{first_char}/{slug}.json"
        
        try:
            req = urllib.request.Request(imdb_url, headers=self._get_headers())
            with urllib.request.urlopen(req, timeout=8) as response:
                data = json.loads(response.read().decode('utf-8'))
        except Exception:
            return []
            
        results = []
        for item in data.get('d', []):
            imdb_id = item.get('id', '')
            if not imdb_id.startswith('tt'):
                continue
                
            item_type = item.get('qid', '')
            
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
            
        return results[:4]

    def _fetch_stream(self, stream_req):
        imdb_id, season, episode, content_type, title, year = stream_req
        
        if content_type == 'series' and season is not None and episode is not None:
            stream_id = f"{imdb_id}:{season}:{episode}"
        else:
            stream_id = imdb_id
            
        req_url = f"{self.torrentio_base}/stream/{content_type}/{stream_id}.json"
        
        try:
            req = urllib.request.Request(req_url, headers=self._get_headers())
            with urllib.request.urlopen(req, timeout=10) as response:
                resp_data = json.loads(response.read().decode('utf-8'))
                return resp_data.get('streams', []), title, year, imdb_id, season, episode
        except Exception:
            return [], title, year, imdb_id, season, episode

    def search(self, what, cat='all'):
        raw_query = urllib.parse.unquote(what).strip()
        if not raw_query: 
            return
        
        season, episode = self._extract_season_episode(raw_query)
        
        clean_query = re.sub(r'\b(?:s|season\s*)\d{1,2}\s*(?:e|episode\s*|\times\s*)\d{1,2}\b', '', raw_query, flags=re.IGNORECASE)
        clean_query = re.sub(r'\b\d{1,2}x\d{1,2}\b', '', clean_query, flags=re.IGNORECASE).strip()

        imdb_results = self._search_imdb_direct(clean_query, cat)
        if not imdb_results: 
            return

        stream_requests = []
        for item in imdb_results:
            c_type = 'series' if season is not None else item['type']
            stream_requests.append((item['id'], season, episode, c_type, item['title'], item['year']))
            
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
                        
                    seeds = '-1'
                    seeds_match = re.search(r'👤\s*(\d+)', raw_title)
                    if seeds_match: 
                        seeds = seeds_match.group(1)
                        
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
