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
        """Extract trailer URL"""
        # Method 1: Look for YouTube iframes
        iframe = soup.find('iframe', src=re.compile(r'youtube\.com/embed|youtube-nocookie\.com/embed'))
        if iframe:
            return iframe.get('src')
        
        # Method 2: Look for YouTube links
        yt_link = soup.find('a', href=re.compile(r'youtube\.com/watch\?v=|youtu\.be/'))
        if yt_link:
            return yt_link.get('href')
        
        # Method 3: Search for video data in script tags
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string:
                # Look for YouTube video IDs in scripts
                match = re.search(r'youtube\.com/watch\?v=([a-zA-Z0-9_-]+)', script.string)
                if match:
                    return f"https://www.youtube.com/watch?v={match.group(1)}"
        
        return None
    
    def _extract_photos(self, soup):
        """Extract photo gallery - get actual movie stills/photos"""
        photos = []
        seen_urls = set()
        
        # Patterns to exclude
        exclude = ['newsletter', 'subscribe', 'logo', 'icon', 'sprite', 
                   'placeholder', 'avatar', 'profile', 'user']
        
        # Method 1: Look for picture elements (modern RT)
        pictures = soup.find_all('picture')
        for pic in pictures:
            sources = pic.find_all('source')
            for source in sources:
                srcset = source.get('srcset')
                if srcset:
                    # Get highest quality image from srcset
                    urls = [url.strip().split(' ')[0] for url in srcset.split(',')]
                    for url in urls:
                        if url and url.startswith('http') and url not in seen_urls:
                            if not any(ex in url.lower() for ex in exclude):
                                photos.append(url)
                                seen_urls.add(url)
                                break
        
        # Method 2: Look for img tags with high-res movie images
        imgs = soup.find_all('img')
        for img in imgs:
            # Get src or data-src
            src = img.get('data-src') or img.get('src')
            if not src or not src.startswith('http'):
                continue
            
            # Skip excluded patterns
            if any(ex in src.lower() for ex in exclude):
                continue
            
            # Check if it's a content image (not UI element)
            classes = ' '.join(img.get('class', [])).lower()
            if any(word in classes for word in ['poster', 'still', 'photo', 'gallery', 'image']):
                if src not in seen_urls:
                    photos.append(src)
                    seen_urls.add(src)
        
        # Method 3: Look for background images in style attributes
        styled_divs = soup.find_all(attrs={'style': re.compile(r'background-image')})
        for div in styled_divs:
            style = div.get('style', '')
            match = re.search(r'url\(["\']?([^"\']+)["\']?\)', style)
            if match:
                url = match.group(1)
                if url.startswith('http') and url not in seen_urls:
                    if not any(ex in url.lower() for ex in exclude):
                        photos.append(url)
                        seen_urls.add(url)
        
        return photos[:10]  # Limit to 10
    
    def _extract_synopsis_smart(self, soup, movie_data):
        """Smart synopsis extraction with multiple fallbacks"""
        synopsis = None
        
        # Method 1: Look for specific synopsis containers
        synopsis_containers = [
            soup.find('div', {'data-qa': 'movie-info-synopsis'}),
            soup.find('div', {'id': 'movieSynopsis'}),
            soup.find('div', class_=re.compile(r'movie.*synopsis')),
            soup.find('p', class_=re.compile(r'synopsis')),
        ]
        
        for container in synopsis_containers:
            if container:
                text = container.get_text(separator=' ', strip=True)
                # Clean up
                text = re.sub(r'\s+', ' ', text)
                
                # Remove common RT additions
                text = re.sub(r'(Read )?the critic reviews.*$', '', text, flags=re.IGNORECASE)
                text = re.sub(r'What to Watch.*$', '', text, flags=re.IGNORECASE)
                
                if text and len(text) > 50 and 'newsletter' not in text.lower():
                    synopsis = text.strip()
                    break
        
        # Method 2: Try getting from structured data
        if not synopsis:
            scripts = soup.find_all('script', type='application/ld+json')
            for script in scripts:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, list):
                        data = data[0]
                    if 'description' in data:
                        desc = data['description']
                        if len(desc) > 50 and 'newsletter' not in desc.lower():
                            synopsis = desc
                            break
                except:
                    pass
        
        # Method 3: Look in meta tags
        if not synopsis:
            meta_desc = soup.find('meta', {'name': 'description'}) or \
                       soup.find('meta', {'property': 'og:description'})
            if meta_desc:
                desc = meta_desc.get('content', '')
                if len(desc) > 50 and 'newsletter' not in desc.lower():
                    synopsis = desc
        
        # Method 4: Find longest paragraph in main content
        if not synopsis:
            main = soup.find('main') or soup.find('article') or soup.find('div', id='main')
            if main:
                paragraphs = main.find_all('p')
                for p in paragraphs:
                    text = p.get_text(strip=True)
                    if len(text) > 100 and 'newsletter' not in text.lower():
                        # Check it's not navigation or UI text
                        if not any(word in text.lower() for word in ['click here', 'sign up', 'subscribe', 'follow us']):
                            synopsis = text
                            break
        
        return synopsis
    
    def _extract_movie_info_comprehensive(self, soup):
        """Comprehensive extraction of all movie metadata"""
        info = {}
        
        # Find all text on the page
        page_text = soup.get_text()
        
        # Method 1: Look for labeled data (RT uses various structures)
        # Common pattern: "Label: Value" or "Label Value"
        
        patterns = {
            'producer': r'Producer[s]?[:\s]+([^\n\r]+?)(?=\n|Director|Writer|$)',
            'screenwriter': r'(?:Screenwriter|Writer)[s]?[:\s]+([^\n\r]+?)(?=\n|Director|Producer|$)',
            'distributor': r'Distributor[:\s]+([^\n\r]+?)(?=\n|$)',
            'production_co': r'Production\s+Co[:\s]+([^\n\r]+?)(?=\n|$)',
            'original_language': r'Original\s+Language[:\s]+([^\n\r]+?)(?=\n|$)',
            'release_date_theaters': r'(?:Release\s+Date\s+\(Theaters?\)|In\s+Theaters?)[:\s]+([^\n\r]+?)(?=\n|$)',
            'release_date_streaming': r'(?:Release\s+Date\s+\(Streaming\)|Streaming)[:\s]+([^\n\r]+?)(?=\n|$)',
            'box_office_usa': r'Box\s+Office\s+\(Gross\s+USA\)[:\s]+([^\n\r]+?)(?=\n|$)',
            'sound_mix': r'Sound\s+Mix[:\s]+([^\n\r]+?)(?=\n|$)',
            'aspect_ratio': r'Aspect\s+Ratio[:\s]+([^\n\r]+?)(?=\n|$)',
        }
        
        for key, pattern in patterns.items():
            match = re.search(pattern, page_text, re.IGNORECASE | re.MULTILINE)
            if match:
                value = match.group(1).strip()
                # Clean up the value
                value = re.sub(r'\s+', ' ', value)
                # Remove trailing punctuation
                value = value.rstrip('.,;')
                if value and len(value) > 1:
                    info[key] = value
        
        # Method 2: Look for dl/dt/dd structures
        dls = soup.find_all('dl')
        for dl in dls:
            dts = dl.find_all('dt')
            for dt in dts:
                label = dt.get_text(strip=True).lower()
                dd = dt.find_next_sibling('dd')
                if dd:
                    value = dd.get_text(strip=True)
                    
                    if 'producer' in label and 'producer' not in info:
                        info['producer'] = value
                    elif ('writer' in label or 'screenwriter' in label) and 'screenwriter' not in info:
                        info['screenwriter'] = value
                    elif 'distributor' in label and 'distributor' not in info:
                        info['distributor'] = value
                    elif 'production' in label and 'production_co' not in info:
                        info['production_co'] = value
                    elif 'language' in label and 'original_language' not in info:
                        info['original_language'] = value
        
        # Method 3: Look for divs with specific attributes
        info_divs = soup.find_all('div', attrs={'data-qa': re.compile(r'movie-info')})
        for div in info_divs:
            text = div.get_text()
            
            # Try to extract from this div
            for key, pattern in patterns.items():
                if key not in info:
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        info[key] = match.group(1).strip()
        
        return info
    
    def _extract_from_json_ld(self, soup, movie_data):
        """Extract from JSON-LD"""
        scripts = soup.find_all('script', {'type': 'application/ld+json'})
        
        for script in scripts:
            try:
                data = json.loads(script.string)
                if isinstance(data, list):
                    data = data[0] if data else {}
                
                # Basic fields
                if 'name' in data and not movie_data['title']:
                    movie_data['title'] = data['name']
                
                if 'image' in data and not movie_data['image_url']:
                    img = data['image']
                    movie_data['image_url'] = img if isinstance(img, str) else (img[0] if isinstance(img, list) else None)
                
                if 'datePublished' in data:
                    if not movie_data['release_date_theaters']:
                        movie_data['release_date_theaters'] = data['datePublished']
                    if not movie_data['year']:
                        year_match = re.search(r'(19|20)\d{2}', str(data['datePublished']))
                        if year_match:
                            movie_data['year'] = year_match.group(0)
                
                if 'genre' in data and not movie_data['genres']:
                    genres = data['genre']
                    movie_data['genres'] = [genres] if isinstance(genres, str) else (genres if isinstance(genres, list) else [])
                
                if 'director' in data and not movie_data['director']:
                    director = data['director']
                    if isinstance(director, dict):
                        movie_data['director'] = director.get('name', '')
                    elif isinstance(director, list) and len(director) > 0:
                        movie_data['director'] = director[0].get('name', '') if isinstance(director[0], dict) else str(director[0])
                    else:
                        movie_data['director'] = str(director)
                
                if 'actor' in data and not movie_data['cast']:
                    actors = data['actor']
                    if isinstance(actors, list):
                        movie_data['cast'] = [
                            a.get('name', str(a)) if isinstance(a, dict) else str(a)
                            for a in actors[:20]  # Limit cast
                        ]
                
                if 'aggregateRating' in data and not movie_data['tomatometer']:
                    rating = data['aggregateRating']
                    if 'ratingValue' in rating:
                        movie_data['tomatometer'] = f"{rating['ratingValue']}%"
                
            except:
                continue
        
        return movie_data
    
    def _extract_from_html(self, soup, movie_data):
        """Extract from HTML"""
        
        if not movie_data['title']:
            h1 = soup.find('h1')
            if h1:
                title = h1.get_text(strip=True)
                title = re.sub(r'\s*\(\d{4}\)\s*$', '', title)
                movie_data['title'] = title
        
        if not movie_data['year']:
            h1 = soup.find('h1')
            if h1:
                year_match = re.search(r'\((\d{4})\)', h1.get_text())
                if year_match:
                    movie_data['year'] = year_match.group(1)
        
        if not movie_data['runtime']:
            runtime_match = re.search(r'(\d+h\s*\d+m|\d+\s*min)', soup.get_text())
            if runtime_match:
                movie_data['runtime'] = runtime_match.group(1).strip()
        
        if not movie_data['rating']:
            rating_match = re.search(r'\b(G|PG|PG-13|R|NC-17|NR|Not Rated)\b', soup.get_text())
            if rating_match:
                movie_data['rating'] = rating_match.group(1)
        
        self._extract_scores(soup, movie_data)
        
        return movie_data
    
    def _extract_scores(self, soup, movie_data):
        """Extract scores"""
        all_percents = []
        seen_percents = {}
        
        for elem in soup.find_all(string=re.compile(r'\d+%')):
            match = re.search(r'(\d+)%', str(elem))
            if match:
                val = match.group(1)
                parent_text = elem.parent.get_text().lower() if elem.parent else ""
                
                if val not in seen_percents:
                    seen_percents[val] = {'contexts': []}
                
                seen_percents[val]['contexts'].append(parent_text)
                if val not in all_percents:
                    all_percents.append(val)
        
        if not movie_data['tomatometer'] and all_percents:
            for val in all_percents:
                contexts = ' '.join(seen_percents[val]['contexts'])
                if any(w in contexts for w in ['critic', 'tomato', 'tomatometer']):
                    movie_data['tomatometer'] = f"{val}%"
                    break
            if not movie_data['tomatometer']:
                movie_data['tomatometer'] = f"{all_percents[0]}%"
        
        if not movie_data['audience_score'] and len(all_percents) > 1:
            tomatometer_val = movie_data['tomatometer'].replace('%', '') if movie_data['tomatometer'] else None
            for val in all_percents:
                if val != tomatometer_val:
                    contexts = ' '.join(seen_percents[val]['contexts'])
                    if any(w in contexts for w in ['audience', 'user', 'popcorn']):
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
        """Get all movie data"""
        try:
            time.sleep(0.5)
            response = requests.get(movie_url, headers=self.headers, timeout=15)
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
            
            # Extract data
            movie_data = self._extract_from_json_ld(soup, movie_data)
            movie_data = self._extract_from_html(soup, movie_data)
            
            # Synopsis
            if not movie_data['synopsis']:
                movie_data['synopsis'] = self._extract_synopsis_smart(soup, movie_data)
            
            # Movie info
            info = self._extract_movie_info_comprehensive(soup)
            for key, value in info.items():
                if not movie_data.get(key):
                    movie_data[key] = value
            
            # Media
            if not movie_data['trailer_url']:
                movie_data['trailer_url'] = self._extract_trailer(soup)
            
            if not movie_data['photos'] or len(movie_data['photos']) < 2:
                movie_data['photos'] = self._extract_photos(soup)
            
            return movie_data
            
        except Exception as e:
            raise Exception(f"Error: {str(e)}")
    
    def get_movie_ratings(self, movie_name):
        """Main method"""
        movie_url = self.search_movie(movie_name)
        if not movie_url:
            return None
        return self.get_all_movie_data(movie_url)


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
                response = {'success': True, 'data': movie_data}
            else:
                response = {'success': False, 'error': 'Movie not found'}
            
            self.wfile.write(json.dumps(response, indent=2).encode())
            
        except Exception as e:
            response = {'success': False, 'error': str(e)}
            self.wfile.write(json.dumps(response, indent=2).encode())
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
