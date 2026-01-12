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
            'Referer': 'https://www.rottentomatoes.com/',
        }
    
    def search_movie(self, movie_name):
        """Search for a movie and return the first result's URL"""
        try:
            search_url = f"{self.base_url}/search?search={quote(movie_name)}"
            response = requests.get(search_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            links = soup.find_all('a', {'href': re.compile(r'/m/[\w_\-]+$')})
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
    
    def _extract_photos(self, soup, movie_url):
        """Extract movie photos"""
        photos = []
        seen = set()
        
        exclude_keywords = ['logo', 'icon', 'sprite', 'placeholder', 'avatar', 
                           'profile', 'button', 'arrow', 'star', 'badge', 'award']
        
        def is_valid_image(url):
            if not url or url in seen:
                return False
            if not url.startswith('http'):
                return False
            url_lower = url.lower()
            if any(kw in url_lower for kw in exclude_keywords):
                return False
            if 'flixster.com' in url or 'rottentomatoes.com' in url:
                return True
            if any(ext in url_lower for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                return True
            return False
        
        # Extract from main page
        for img in soup.find_all('img'):
            for attr in ['data-src', 'src', 'data-lazy-src']:
                src = img.get(attr)
                if src:
                    if src.startswith('//'):
                        src = 'https:' + src
                    elif src.startswith('/'):
                        src = self.base_url + src
                    
                    if is_valid_image(src):
                        photos.append(src)
                        seen.add(src)
        
        # Check srcset
        for elem in soup.find_all(['img', 'source'], srcset=True):
            srcset = elem.get('srcset', '')
            urls = re.findall(r'(https?://[^\s,]+)', srcset)
            for url in urls:
                if is_valid_image(url):
                    photos.append(url)
                    seen.add(url)
        
        # Try photos pages
        for endpoint in ['/pictures', '/photos']:
            try:
                photos_url = movie_url.rstrip('/') + endpoint
                response = requests.get(photos_url, headers=self.headers, timeout=5)
                
                if response.status_code == 200:
                    photos_soup = BeautifulSoup(response.content, 'html.parser')
                    
                    for img in photos_soup.find_all('img'):
                        for attr in ['data-src', 'src', 'data-lazy-src']:
                            src = img.get(attr)
                            if src:
                                if src.startswith('//'):
                                    src = 'https:' + src
                                elif src.startswith('/'):
                                    src = self.base_url + src
                                
                                if is_valid_image(src):
                                    photos.append(src)
                                    seen.add(src)
                    
                    for elem in photos_soup.find_all(['img', 'source'], srcset=True):
                        srcset = elem.get('srcset', '')
                        urls = re.findall(r'(https?://[^\s,]+)', srcset)
                        for url in urls:
                            if is_valid_image(url):
                                photos.append(url)
                                seen.add(url)
                    
                    if len(photos) >= 10:
                        break
            except:
                pass
        
        # JSON-LD
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script.string)
                if isinstance(data, list):
                    data = data[0] if data else {}
                
                for field in ['image', 'images']:
                    if field in data:
                        img_data = data[field]
                        if isinstance(img_data, str):
                            if is_valid_image(img_data):
                                photos.append(img_data)
                                seen.add(img_data)
                        elif isinstance(img_data, list):
                            for img in img_data:
                                if isinstance(img, str) and is_valid_image(img):
                                    photos.append(img)
                                    seen.add(img)
            except:
                pass
        
        return photos[:25]
    
    def _extract_synopsis(self, soup):
        """Extract synopsis"""
        exclude_patterns = [
            r'newsletter', r'subscribe', r'sign up', r'follow us',
            r'download', r'app store', r'google play', r'certified fresh',
            r'discover rotten tomatoes', r'what to watch', r'©', r'copyright'
        ]
        
        def is_valid_synopsis(text):
            if len(text) < 50:
                return False
            if any(re.search(pattern, text, re.I) for pattern in exclude_patterns):
                return False
            if text.count('.') < 1:
                return False
            return True
        
        candidates = []
        
        # data-qa attributes
        for elem in soup.find_all(attrs={'data-qa': re.compile(r'synopsis|movie-info-synopsis', re.I)}):
            text = elem.get_text(separator=' ', strip=True)
            text = re.sub(r'\s+', ' ', text)
            if is_valid_synopsis(text):
                return text
        
        # JSON-LD
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script.string)
                if isinstance(data, list):
                    data = data[0]
                if 'description' in data:
                    desc = data['description']
                    if is_valid_synopsis(desc):
                        candidates.append((len(desc), desc))
            except:
                pass
        
        # Meta tags
        meta_desc = soup.find('meta', property='og:description') or soup.find('meta', attrs={'name': 'description'})
        if meta_desc:
            content = meta_desc.get('content', '')
            if is_valid_synopsis(content):
                candidates.append((len(content), content))
        
        # Class-based
        for cls in ['synopsis', 'plot', 'movie-info-synopsis', 'description']:
            for elem in soup.find_all(class_=re.compile(cls, re.I)):
                text = elem.get_text(separator=' ', strip=True)
                text = re.sub(r'\s+', ' ', text)
                if is_valid_synopsis(text):
                    candidates.append((len(text), text))
        
        if candidates:
            candidates.sort(key=lambda x: abs(x[0] - 300))
            for length, text in candidates:
                if 100 <= length <= 1500:
                    return text
            return candidates[0][1]
        
        return None
    
    def _extract_from_json_ld(self, soup, movie_data):
        """Extract from JSON-LD"""
        scripts = soup.find_all('script', {'type': 'application/ld+json'})
        
        for script in scripts:
            try:
                data = json.loads(script.string)
                if isinstance(data, list):
                    data = data[0] if data else {}
                
                if 'name' in data and not movie_data['title']:
                    movie_data['title'] = data['name']
                
                if 'image' in data and not movie_data['image_url']:
                    img = data['image']
                    movie_data['image_url'] = img if isinstance(img, str) else (img[0] if isinstance(img, list) else None)
                
                if 'datePublished' in data:
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
                            for a in actors[:20]
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
    
    def _extract_movie_info(self, soup):
        """Extract metadata"""
        info = {}
        page_text = soup.get_text()
        
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
                value = re.sub(r'\s+', ' ', value)
                value = value.rstrip('.,;')
                if value and len(value) > 1:
                    info[key] = value
        
        return info
    
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
                'photos': [],
                'url': movie_url
            }
            
            movie_data = self._extract_from_json_ld(soup, movie_data)
            movie_data = self._extract_from_html(soup, movie_data)
            
            if not movie_data['synopsis']:
                movie_data['synopsis'] = self._extract_synopsis(soup)
            
            movie_data['photos'] = self._extract_photos(soup, movie_url)
            
            info = self._extract_movie_info(soup)
            for key, value in info.items():
                if not movie_data.get(key):
                    movie_data[key] = value
            
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
        
        # Route handling for different endpoints
        if parsed_path.path == '/api/rotten-tomatoes':
            if 'movie' not in query_params:
                response = {
                    'error': 'Missing movie parameter',
                    'usage': 'GET /api/rotten-tomatoes?movie=Inception'
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
                        'source': 'rotten-tomatoes',
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
        
        else:
            # 404 for unknown endpoints
            response = {
                'error': 'Endpoint not found',
                'available_endpoints': [
                    '/api/rotten-tomatoes?movie=MovieName'
                ]
            }
            self.wfile.write(json.dumps(response, indent=2).encode())
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
