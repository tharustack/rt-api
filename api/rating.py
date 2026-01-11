from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
import json
import requests
from bs4 import BeautifulSoup
import time
import re
from urllib.parse import quote

class RottenTomatoesScraper:
    def __init__(self):
        self.base_url = "https://www.rottentomatoes.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        }
    
    def search_movie(self, movie_name):
        """Search for a movie and return the first result's URL"""
        try:
            search_url = f"{self.base_url}/search?search={quote(movie_name)}"
            response = requests.get(search_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            links = soup.find_all('a', {'href': re.compile(r'/m/[\w_\-]+')})
            if not links:
                return None
            
            search_term = movie_name.lower().strip()
            best_match = None
            best_score = 0
            
            for link in links:
                title = link.text.strip().lower()
                if title == search_term:
                    best_match = link
                    break
                
                search_words = [w for w in search_term.split() if len(w) > 2]
                if all(w in title for w in search_words):
                    score = sum(len(w) for w in search_words)
                    if score > best_score:
                        best_score = score
                        best_match = link
            
            if not best_match:
                best_match = links[0]
            
            if best_match:
                href = best_match.get('href')
                movie_url = self.base_url + href if not href.startswith('http') else href
                return movie_url
            
            return None
            
        except Exception as e:
            raise Exception(f"Search error: {str(e)}")
    
    def _extract_trailer(self, soup):
        """Extract trailer URL from page"""
        # Look for YouTube embed or video player
        iframe = soup.find('iframe', src=re.compile(r'youtube|vimeo'))
        if iframe:
            return iframe.get('src')
        
        # Look for video links
        video_link = soup.find('a', href=re.compile(r'youtube\.com|youtu\.be'))
        if video_link:
            return video_link.get('href')
        
        return None
    
    def _extract_photos(self, soup):
        """Extract photo gallery URLs"""
        photos = []
        
        # Look for gallery images
        gallery_imgs = soup.find_all('img', src=re.compile(r'(cloudfront|image|photo|gallery)'))
        
        for img in gallery_imgs[:10]:  # Limit to 10 photos
            src = img.get('src') or img.get('data-src')
            if src and src.startswith('http') and 'logo' not in src.lower():
                photos.append(src)
        
        return list(set(photos))  # Remove duplicates
    
    def _extract_movie_info(self, soup):
        """Extract detailed movie information from the info section"""
        info = {}
        
        # Look for info sections - common patterns on RT
        info_section = soup.find('section', {'data-qa': 'movie-info-section'}) or \
                      soup.find('div', class_=re.compile(r'movie.*info|info.*section'))
        
        if info_section:
            # Extract all text content
            all_text = info_section.get_text()
            
            # Producer
            producer_match = re.search(r'Producer[s]?[:\s]+([^\n]+)', all_text, re.IGNORECASE)
            if producer_match:
                info['producer'] = producer_match.group(1).strip()
            
            # Screenwriter
            writer_match = re.search(r'(Screenwriter|Writer)[s]?[:\s]+([^\n]+)', all_text, re.IGNORECASE)
            if writer_match:
                info['screenwriter'] = writer_match.group(2).strip()
            
            # Distributor
            dist_match = re.search(r'Distributor[s]?[:\s]+([^\n]+)', all_text, re.IGNORECASE)
            if dist_match:
                info['distributor'] = dist_match.group(1).strip()
            
            # Production Company
            prod_match = re.search(r'Production\s+Co[:\s]+([^\n]+)', all_text, re.IGNORECASE)
            if prod_match:
                info['production_co'] = prod_match.group(1).strip()
            
            # Original Language
            lang_match = re.search(r'Original\s+Language[:\s]+([^\n]+)', all_text, re.IGNORECASE)
            if lang_match:
                info['original_language'] = lang_match.group(1).strip()
            
            # Release Dates
            theater_match = re.search(r'Release\s+Date\s+\(Theater[s]?\)[:\s]+([^\n]+)', all_text, re.IGNORECASE)
            if theater_match:
                info['release_date_theaters'] = theater_match.group(1).strip()
            
            rerelease_match = re.search(r'Rerelease\s+Date[:\s]+([^\n]+)', all_text, re.IGNORECASE)
            if rerelease_match:
                info['rerelease_date'] = rerelease_match.group(1).strip()
            
            streaming_match = re.search(r'Release\s+Date\s+\(Streaming\)[:\s]+([^\n]+)', all_text, re.IGNORECASE)
            if streaming_match:
                info['release_date_streaming'] = streaming_match.group(1).strip()
            
            # Box Office
            box_office_match = re.search(r'Box\s+Office\s+\(Gross\s+USA\)[:\s]+([^\n]+)', all_text, re.IGNORECASE)
            if box_office_match:
                info['box_office_usa'] = box_office_match.group(1).strip()
            
            # Sound Mix
            sound_match = re.search(r'Sound\s+Mix[:\s]+([^\n]+)', all_text, re.IGNORECASE)
            if sound_match:
                info['sound_mix'] = sound_match.group(1).strip()
            
            # Aspect Ratio
            aspect_match = re.search(r'Aspect\s+Ratio[:\s]+([^\n]+)', all_text, re.IGNORECASE)
            if aspect_match:
                info['aspect_ratio'] = aspect_match.group(1).strip()
        
        # Also try structured approach - look for dt/dd pairs
        info_items = soup.find_all(['dt', 'dd', 'div'], class_=re.compile(r'info|meta|detail'))
        
        for i, item in enumerate(info_items):
            text = item.get_text().strip()
            
            if 'producer' in text.lower() and i + 1 < len(info_items):
                if not info.get('producer'):
                    info['producer'] = info_items[i + 1].get_text().strip()
            
            elif 'screenwriter' in text.lower() or 'writer' in text.lower():
                if i + 1 < len(info_items) and not info.get('screenwriter'):
                    info['screenwriter'] = info_items[i + 1].get_text().strip()
            
            elif 'distributor' in text.lower() and i + 1 < len(info_items):
                if not info.get('distributor'):
                    info['distributor'] = info_items[i + 1].get_text().strip()
        
        return info
    
    def _extract_from_json_ld(self, soup, movie_data):
        """Extract data from JSON-LD structured data"""
        json_ld_scripts = soup.find_all('script', {'type': 'application/ld+json'})
        
        for script in json_ld_scripts:
            try:
                data = json.loads(script.string)
                
                if isinstance(data, list):
                    data = data[0] if data else {}
                
                if 'name' in data and not movie_data['title']:
                    movie_data['title'] = data['name']
                
                if 'description' in data and not movie_data['synopsis']:
                    movie_data['synopsis'] = data['description']
                
                if 'image' in data and not movie_data['image_url']:
                    img = data['image']
                    movie_data['image_url'] = img if isinstance(img, str) else img[0] if isinstance(img, list) else None
                
                if 'datePublished' in data and not movie_data['release_date_theaters']:
                    movie_data['release_date_theaters'] = data['datePublished']
                    year_match = re.search(r'(19|20)\d{2}', str(data['datePublished']))
                    if year_match:
                        movie_data['year'] = year_match.group(0)
                
                if 'genre' in data and not movie_data['genres']:
                    genres = data['genre']
                    movie_data['genres'] = [genres] if isinstance(genres, str) else genres if isinstance(genres, list) else []
                
                if 'director' in data and not movie_data['director']:
                    director = data['director']
                    if isinstance(director, dict) and 'name' in director:
                        movie_data['director'] = director['name']
                    elif isinstance(director, list) and len(director) > 0:
                        movie_data['director'] = director[0].get('name', str(director[0])) if isinstance(director[0], dict) else str(director[0])
                    elif isinstance(director, str):
                        movie_data['director'] = director
                
                if 'actor' in data and not movie_data['cast']:
                    actors = data['actor']
                    if isinstance(actors, list):
                        movie_data['cast'] = [
                            actor.get('name', str(actor)) if isinstance(actor, dict) else str(actor)
                            for actor in actors
                        ]
                
                if 'aggregateRating' in data and not movie_data['tomatometer']:
                    rating = data['aggregateRating']
                    if 'ratingValue' in rating:
                        movie_data['tomatometer'] = f"{rating['ratingValue']}%"
                
            except json.JSONDecodeError:
                continue
        
        return movie_data
    
    def _extract_from_meta_tags(self, soup, movie_data):
        """Extract data from Open Graph and meta tags"""
        
        if not movie_data['title']:
            og_title = soup.find('meta', property='og:title')
            if og_title:
                movie_data['title'] = og_title.get('content', '').strip()
        
        if not movie_data['synopsis']:
            og_desc = soup.find('meta', property='og:description')
            if og_desc:
                movie_data['synopsis'] = og_desc.get('content', '').strip()
            else:
                meta_desc = soup.find('meta', attrs={'name': 'description'})
                if meta_desc:
                    movie_data['synopsis'] = meta_desc.get('content', '').strip()
        
        if not movie_data['image_url']:
            og_image = soup.find('meta', property='og:image')
            if og_image:
                movie_data['image_url'] = og_image.get('content', '').strip()
        
        return movie_data
    
    def _extract_from_html(self, soup, movie_data):
        """Extract data from HTML elements"""
        
        if not movie_data['title']:
            h1_tag = soup.find('h1')
            if h1_tag:
                title_text = h1_tag.get_text().strip()
                title_clean = re.sub(r'\s*\(\d{4}\)\s*$', '', title_text)
                movie_data['title'] = title_clean
        
        if not movie_data['year']:
            h1_tag = soup.find('h1')
            if h1_tag:
                year_in_title = re.search(r'\((\d{4})\)', h1_tag.get_text())
                if year_in_title:
                    movie_data['year'] = year_in_title.group(1)
                else:
                    parent_text = h1_tag.parent.get_text() if h1_tag.parent else ''
                    year_match = re.search(r'\b(19|20)\d{2}\b', parent_text)
                    if year_match:
                        movie_data['year'] = year_match.group(0)
        
        if not movie_data['runtime']:
            runtime_pattern = re.compile(r'(\d+h\s*\d+m|\d+\s*min)')
            runtime_match = runtime_pattern.search(soup.get_text())
            if runtime_match:
                movie_data['runtime'] = runtime_match.group(1).strip()
        
        if not movie_data['rating']:
            rating_pattern = re.compile(r'\b(G|PG|PG-13|R|NC-17|NR|Not Rated)\b')
            rating_match = rating_pattern.search(soup.get_text())
            if rating_match:
                movie_data['rating'] = rating_match.group(1)
        
        self._extract_scores(soup, movie_data)
        
        return movie_data
    
    def _extract_scores(self, soup, movie_data):
        """Extract Tomatometer and Audience scores"""
        all_percents = []
        seen_percents = {}
        
        for elem in soup.find_all(string=re.compile(r'\d+%')):
            match = re.search(r'(\d+)%', str(elem))
            if match:
                val = match.group(1)
                parent = elem.parent
                parent_text = parent.get_text().lower() if parent else ""
                
                if val not in seen_percents:
                    seen_percents[val] = {'contexts': [], 'count': 0}
                
                seen_percents[val]['count'] += 1
                seen_percents[val]['contexts'].append(parent_text)
                
                if val not in all_percents:
                    all_percents.append(val)
        
        if not movie_data['tomatometer'] and all_percents:
            for val in all_percents:
                contexts = ' '.join(seen_percents[val]['contexts'])
                if any(word in contexts for word in ['critic', 'tomato', 'tomatometer']):
                    movie_data['tomatometer'] = f"{val}%"
                    break
            
            if not movie_data['tomatometer']:
                movie_data['tomatometer'] = f"{all_percents[0]}%"
        
        if not movie_data['audience_score'] and len(all_percents) > 1:
            tomatometer_val = movie_data['tomatometer'].replace('%', '') if movie_data['tomatometer'] else None
            
            for val in all_percents:
                if val != tomatometer_val:
                    contexts = ' '.join(seen_percents[val]['contexts'])
                    if any(word in contexts for word in ['audience', 'user', 'popcorn']):
                        movie_data['audience_score'] = f"{val}%"
                        break
            
            if not movie_data['audience_score']:
                for val in all_percents:
                    if val != tomatometer_val:
                        movie_data['audience_score'] = f"{val}%"
                        break
        
        if not movie_data['audience_score']:
            movie_data['audience_score'] = "N/A"
    
    def get_all_movie_data(self, movie_url):
        """Get comprehensive movie data"""
        try:
            time.sleep(0.5)
            response = requests.get(movie_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            movie_data = {
                'title': None,
                'year': None,
                'synopsis': None,
                'genres': [],
                'director': None,
                'producer': None,
                'screenwriter': None,
                'cast': [],
                'distributor': None,
                'production_co': None,
                'rating': None,
                'original_language': None,
                'release_date_theaters': None,
                'rerelease_date': None,
                'release_date_streaming': None,
                'box_office_usa': None,
                'runtime': None,
                'sound_mix': None,
                'aspect_ratio': None,
                'tomatometer': None,
                'audience_score': None,
                'image_url': None,
                'trailer_url': None,
                'photos': [],
                'url': movie_url
            }
            
            # Extract from different sources
            movie_data = self._extract_from_json_ld(soup, movie_data)
            movie_data = self._extract_from_meta_tags(soup, movie_data)
            movie_data = self._extract_from_html(soup, movie_data)
            
            # Extract additional info
            movie_info = self._extract_movie_info(soup)
            for key, value in movie_info.items():
                if not movie_data.get(key):
                    movie_data[key] = value
            
            # Extract trailer and photos
            if not movie_data['trailer_url']:
                movie_data['trailer_url'] = self._extract_trailer(soup)
            
            if not movie_data['photos']:
                movie_data['photos'] = self._extract_photos(soup)
            
            return movie_data
            
        except Exception as e:
            raise Exception(f"Data extraction error: {str(e)}")
    
    def get_movie_ratings(self, movie_name):
        """Main method: Search and get all data"""
        movie_url = self.search_movie(movie_name)
        
        if not movie_url:
            return None
        
        movie_data = self.get_all_movie_data(movie_url)
        return movie_data


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urlparse(self.path)
        query_params = parse_qs(parsed_path.query)
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        
        if 'movie' not in query_params:
            response = {
                'error': 'Missing movie parameter',
                'usage': 'GET /api/rating?movie=Inception'
            }
            self.wfile.write(json.dumps(response, indent=2).encode())
            return
        
        movie_name = query_params['movie'][0]
        
        try:
            scraper = RottenTomatoesScraper()
            movie_data = scraper.get_movie_ratings(movie_name)
            
            if movie_data:
                response = {
                    'success': True,
                    'data': movie_data
                }
            else:
                response = {
                    'success': False,
                    'error': 'Movie not found'
                }
            
            self.wfile.write(json.dumps(response, indent=2).encode())
            
        except Exception as e:
            response = {
                'success': False,
                'error': str(e)
            }
            self.wfile.write(json.dumps(response, indent=2).encode())
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
