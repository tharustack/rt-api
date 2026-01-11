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
        # Look for YouTube embed
        iframe = soup.find('iframe', src=re.compile(r'youtube|vimeo'))
        if iframe:
            return iframe.get('src')
        
        # Look for video links
        video_link = soup.find('a', href=re.compile(r'youtube\.com/watch|youtu\.be'))
        if video_link:
            return video_link.get('href')
        
        # Look for data attributes with video URLs
        video_elements = soup.find_all(attrs={'data-video-url': True})
        if video_elements:
            return video_elements[0].get('data-video-url')
        
        return None
    
    def _extract_photos(self, soup):
        """Extract movie photo gallery URLs - filtering out ads and newsletters"""
        photos = []
        seen_urls = set()
        
        # Exclusion patterns for unwanted images
        exclude_patterns = [
            'newsletter', 'subscribe', 'logo', 'icon', 'avatar',
            'ad', 'banner', 'promo', 'email', 'footer', 'header',
            'social', 'facebook', 'twitter', 'instagram'
        ]
        
        # Look for images in the main content area
        main_content = soup.find('main') or soup.find('div', class_=re.compile(r'content|main'))
        
        if main_content:
            # Find all images
            images = main_content.find_all('img')
            
            for img in images:
                src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
                
                if not src:
                    continue
                
                # Skip if not a full URL
                if not src.startswith('http'):
                    continue
                
                # Skip small images (likely icons)
                width = img.get('width')
                height = img.get('height')
                if width and height:
                    try:
                        if int(width) < 200 or int(height) < 200:
                            continue
                    except:
                        pass
                
                # Check URL for exclusion patterns
                src_lower = src.lower()
                if any(pattern in src_lower for pattern in exclude_patterns):
                    continue
                
                # Check alt text for exclusion patterns
                alt = (img.get('alt') or '').lower()
                if any(pattern in alt for pattern in exclude_patterns):
                    continue
                
                # Check if we've seen this URL
                if src in seen_urls:
                    continue
                
                # Check if it's a valid image URL
                if any(ext in src_lower for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                    photos.append(src)
                    seen_urls.add(src)
                    
                    if len(photos) >= 10:
                        break
        
        return photos
    
    def _extract_movie_info_detailed(self, soup):
        """Extract detailed movie information - better targeted extraction"""
        info = {}
        
        # Try to find the movie info section more precisely
        # RT often uses these patterns
        info_sections = [
            soup.find('section', attrs={'data-qa': 'movie-info-section'}),
            soup.find('div', class_=re.compile(r'movie-info')),
            soup.find('div', id=re.compile(r'info|details')),
        ]
        
        info_section = None
        for section in info_sections:
            if section:
                info_section = section
                break
        
        if info_section:
            # Look for dt/dd pairs (definition list)
            dts = info_section.find_all('dt')
            for dt in dts:
                label = dt.get_text().strip().lower()
                dd = dt.find_next_sibling('dd')
                
                if not dd:
                    continue
                
                value = dd.get_text().strip()
                
                if 'producer' in label and not info.get('producer'):
                    info['producer'] = value
                elif 'writer' in label or 'screenwriter' in label:
                    if not info.get('screenwriter'):
                        info['screenwriter'] = value
                elif 'distributor' in label and not info.get('distributor'):
                    info['distributor'] = value
                elif 'production' in label and 'co' in label:
                    if not info.get('production_co'):
                        info['production_co'] = value
                elif 'language' in label and 'original' in label:
                    if not info.get('original_language'):
                        info['original_language'] = value
                elif 'release' in label and 'theater' in label:
                    if 'rerelease' in label:
                        info['rerelease_date'] = value
                    elif not info.get('release_date_theaters'):
                        info['release_date_theaters'] = value
                elif 'release' in label and 'streaming' in label:
                    if not info.get('release_date_streaming'):
                        info['release_date_streaming'] = value
                elif 'box office' in label:
                    if not info.get('box_office_usa'):
                        info['box_office_usa'] = value
                elif 'sound' in label and 'mix' in label:
                    if not info.get('sound_mix'):
                        info['sound_mix'] = value
                elif 'aspect' in label and 'ratio' in label:
                    if not info.get('aspect_ratio'):
                        info['aspect_ratio'] = value
            
            # Also try div-based structure
            divs = info_section.find_all('div', class_=re.compile(r'info-item|detail|meta'))
            for div in divs:
                text = div.get_text()
                
                # Use regex to extract label: value pairs
                if 'Producer' in text and not info.get('producer'):
                    match = re.search(r'Producer[s]?:\s*([^\n]+)', text)
                    if match:
                        info['producer'] = match.group(1).strip()
                
                if ('Writer' in text or 'Screenwriter' in text) and not info.get('screenwriter'):
                    match = re.search(r'(?:Screenwriter|Writer)[s]?:\s*([^\n]+)', text)
                    if match:
                        info['screenwriter'] = match.group(1).strip()
                
                if 'Distributor' in text and not info.get('distributor'):
                    match = re.search(r'Distributor:\s*([^\n]+)', text)
                    if match:
                        info['distributor'] = match.group(1).strip()
        
        return info
    
    def _clean_synopsis(self, text):
        """Clean synopsis text - remove RT promotional content"""
        if not text:
            return None
        
        # Common RT promo phrases to remove
        promo_phrases = [
            'discover rotten tomatoes',
            'sign up for rotten tomatoes',
            'subscribe to',
            'newsletter',
            'follow us',
            'download the app',
            'rate and review',
            'what to watch',
            'certified fresh',
        ]
        
        text_lower = text.lower()
        
        # If the text is mostly promotional, return None
        if any(phrase in text_lower for phrase in promo_phrases):
            # Check if there's actual content before the promo
            sentences = text.split('.')
            clean_sentences = []
            
            for sentence in sentences:
                sentence_lower = sentence.lower().strip()
                if not any(phrase in sentence_lower for phrase in promo_phrases):
                    if len(sentence.strip()) > 20:  # Meaningful sentence
                        clean_sentences.append(sentence.strip())
            
            if clean_sentences:
                return '. '.join(clean_sentences) + '.'
            else:
                return None
        
        return text.strip()
    
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
                    cleaned = self._clean_synopsis(data['description'])
                    if cleaned:
                        movie_data['synopsis'] = cleaned
                
                if 'image' in data and not movie_data['image_url']:
                    img = data['image']
                    movie_data['image_url'] = img if isinstance(img, str) else img[0] if isinstance(img, list) else None
                
                if 'datePublished' in data:
                    if not movie_data['release_date_theaters']:
                        movie_data['release_date_theaters'] = data['datePublished']
                    year_match = re.search(r'(19|20)\d{2}', str(data['datePublished']))
                    if year_match and not movie_data['year']:
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
                
                # Extract producer from JSON-LD
                if 'producer' in data and not movie_data['producer']:
                    producer = data['producer']
                    if isinstance(producer, dict) and 'name' in producer:
                        movie_data['producer'] = producer['name']
                    elif isinstance(producer, list):
                        names = [p.get('name', str(p)) if isinstance(p, dict) else str(p) for p in producer]
                        movie_data['producer'] = ', '.join(names[:3])  # First 3 producers
                
                # Extract creator/screenwriter from JSON-LD
                if 'creator' in data and not movie_data['screenwriter']:
                    creator = data['creator']
                    if isinstance(creator, dict) and 'name' in creator:
                        movie_data['screenwriter'] = creator['name']
                    elif isinstance(creator, list):
                        names = [c.get('name', str(c)) if isinstance(c, dict) else str(c) for c in creator]
                        movie_data['screenwriter'] = ', '.join(names[:3])
                
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
                cleaned = self._clean_synopsis(og_desc.get('content', '').strip())
                if cleaned:
                    movie_data['synopsis'] = cleaned
            else:
                meta_desc = soup.find('meta', attrs={'name': 'description'})
                if meta_desc:
                    cleaned = self._clean_synopsis(meta_desc.get('content', '').strip())
                    if cleaned:
                        movie_data['synopsis'] = cleaned
        
        if not movie_data['image_url']:
            og_image = soup.find('meta', property='og:image')
            if og_image:
                img_url = og_image.get('content', '').strip()
                # Validate it's not a generic/newsletter image
                if img_url and 'newsletter' not in img_url.lower():
                    movie_data['image_url'] = img_url
        
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
        
        # Extract synopsis from specific sections
        if not movie_data['synopsis']:
            synopsis_selectors = [
                soup.find('div', attrs={'data-qa': 'synopsis'}),
                soup.find('div', class_=re.compile(r'synopsis|plot|summary')),
                soup.find('p', class_=re.compile(r'synopsis|plot'))
            ]
            
            for selector in synopsis_selectors:
                if selector:
                    text = selector.get_text().strip()
                    cleaned = self._clean_synopsis(text)
                    if cleaned and len(cleaned) > 50:
                        movie_data['synopsis'] = cleaned
                        break
        
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
            
            # Extract detailed movie info
            movie_info = self._extract_movie_info_detailed(soup)
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
