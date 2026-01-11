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
            
            # Find all movie links
            links = soup.find_all('a', {'href': re.compile(r'/m/[\w_\-]+')})
            if not links:
                return None
            
            search_term = movie_name.lower().strip()
            best_match = None
            best_score = 0
            
            # Find best matching title
            for link in links:
                title = link.text.strip().lower()
                
                # Exact match wins immediately
                if title == search_term:
                    best_match = link
                    break
                
                # Score based on word matches
                search_words = [w for w in search_term.split() if len(w) > 2]
                if all(w in title for w in search_words):
                    score = sum(len(w) for w in search_words)
                    if score > best_score:
                        best_score = score
                        best_match = link
            
            # Fallback to first link
            if not best_match:
                best_match = links[0]
            
            if best_match:
                href = best_match.get('href')
                movie_url = self.base_url + href if not href.startswith('http') else href
                return movie_url
            
            return None
            
        except Exception as e:
            raise Exception(f"Search error: {str(e)}")
    
    def _extract_from_json_ld(self, soup, movie_data):
        """Extract data from JSON-LD structured data - most reliable source"""
        json_ld_scripts = soup.find_all('script', {'type': 'application/ld+json'})
        
        for script in json_ld_scripts:
            try:
                data = json.loads(script.string)
                
                # Handle both single objects and arrays
                if isinstance(data, list):
                    data = data[0] if data else {}
                
                # Title
                if 'name' in data and not movie_data['title']:
                    movie_data['title'] = data['name']
                
                # Description
                if 'description' in data and not movie_data['description']:
                    movie_data['description'] = data['description']
                
                # Image URL
                if 'image' in data and not movie_data['image_url']:
                    img = data['image']
                    if isinstance(img, str):
                        movie_data['image_url'] = img
                    elif isinstance(img, list) and len(img) > 0:
                        movie_data['image_url'] = img[0]
                
                # Year from datePublished
                if 'datePublished' in data and not movie_data['year']:
                    date_pub = data['datePublished']
                    year_match = re.search(r'(19|20)\d{2}', str(date_pub))
                    if year_match:
                        movie_data['year'] = year_match.group(0)
                
                # Genres
                if 'genre' in data and not movie_data['genres']:
                    genres = data['genre']
                    if isinstance(genres, str):
                        movie_data['genres'] = [genres]
                    elif isinstance(genres, list):
                        movie_data['genres'] = genres
                
                # Director
                if 'director' in data and not movie_data['director']:
                    director = data['director']
                    if isinstance(director, dict) and 'name' in director:
                        movie_data['director'] = director['name']
                    elif isinstance(director, list) and len(director) > 0:
                        if isinstance(director[0], dict):
                            movie_data['director'] = director[0].get('name', None)
                        else:
                            movie_data['director'] = str(director[0])
                    elif isinstance(director, str):
                        movie_data['director'] = director
                
                # Cast (actors)
                if 'actor' in data and not movie_data['cast']:
                    actors = data['actor']
                    if isinstance(actors, list):
                        cast_list = []
                        for actor in actors:
                            if isinstance(actor, dict) and 'name' in actor:
                                cast_list.append(actor['name'])
                            else:
                                cast_list.append(str(actor))
                        movie_data['cast'] = cast_list
                
                # Ratings
                if 'aggregateRating' in data and not movie_data['tomatometer']:
                    rating = data['aggregateRating']
                    if 'ratingValue' in rating:
                        movie_data['tomatometer'] = f"{rating['ratingValue']}%"
                
            except json.JSONDecodeError:
                continue
        
        return movie_data
    
    def _extract_from_meta_tags(self, soup, movie_data):
        """Extract data from Open Graph and meta tags"""
        
        # Title from og:title
        if not movie_data['title']:
            og_title = soup.find('meta', property='og:title')
            if og_title:
                movie_data['title'] = og_title.get('content', '').strip()
        
        # Description from og:description or meta description
        if not movie_data['description']:
            og_desc = soup.find('meta', property='og:description')
            if og_desc:
                movie_data['description'] = og_desc.get('content', '').strip()
            else:
                meta_desc = soup.find('meta', attrs={'name': 'description'})
                if meta_desc:
                    movie_data['description'] = meta_desc.get('content', '').strip()
        
        # Image from og:image
        if not movie_data['image_url']:
            og_image = soup.find('meta', property='og:image')
            if og_image:
                movie_data['image_url'] = og_image.get('content', '').strip()
        
        return movie_data
    
    def _extract_from_html(self, soup, movie_data):
        """Extract data from HTML elements - fallback method"""
        
        # Title from h1 tag
        if not movie_data['title']:
            h1_tag = soup.find('h1')
            if h1_tag:
                title_text = h1_tag.get_text().strip()
                # Remove year in parentheses if present
                title_clean = re.sub(r'\s*\(\d{4}\)\s*$', '', title_text)
                movie_data['title'] = title_clean
        
        # Year extraction
        if not movie_data['year']:
            h1_tag = soup.find('h1')
            if h1_tag:
                # Look for (YYYY) format in title
                year_in_title = re.search(r'\((\d{4})\)', h1_tag.get_text())
                if year_in_title:
                    movie_data['year'] = year_in_title.group(1)
                else:
                    # Look in parent container
                    parent_text = h1_tag.parent.get_text() if h1_tag.parent else ''
                    year_match = re.search(r'\b(19|20)\d{2}\b', parent_text)
                    if year_match:
                        movie_data['year'] = year_match.group(0)
        
        # Runtime (e.g., "1h 30m" or "90 min")
        if not movie_data['runtime']:
            runtime_pattern = re.compile(r'(\d+h\s*\d+m|\d+\s*min)')
            runtime_match = runtime_pattern.search(soup.get_text())
            if runtime_match:
                movie_data['runtime'] = runtime_match.group(1).strip()
        
        # MPAA Rating (G, PG, PG-13, R, etc.)
        if not movie_data['rating']:
            rating_pattern = re.compile(r'\b(G|PG|PG-13|R|NC-17|NR|Not Rated)\b')
            rating_match = rating_pattern.search(soup.get_text())
            if rating_match:
                movie_data['rating'] = rating_match.group(1)
        
        # Extract scores
        self._extract_scores(soup, movie_data)
        
        return movie_data
    
    def _extract_scores(self, soup, movie_data):
        """Extract Tomatometer and Audience scores"""
        all_percents = []
        seen_percents = {}
        
        # Find all percentage values
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
        
        # Extract Tomatometer (Critics Score)
        if not movie_data['tomatometer'] and all_percents:
            for val in all_percents:
                contexts = ' '.join(seen_percents[val]['contexts'])
                if any(word in contexts for word in ['critic', 'tomato', 'tomatometer']):
                    movie_data['tomatometer'] = f"{val}%"
                    break
            
            # Fallback to first percentage
            if not movie_data['tomatometer']:
                movie_data['tomatometer'] = f"{all_percents[0]}%"
        
        # Extract Audience Score
        if not movie_data['audience_score'] and len(all_percents) > 1:
            tomatometer_val = movie_data['tomatometer'].replace('%', '') if movie_data['tomatometer'] else None
            
            for val in all_percents:
                if val != tomatometer_val:
                    contexts = ' '.join(seen_percents[val]['contexts'])
                    if any(word in contexts for word in ['audience', 'user', 'popcorn']):
                        movie_data['audience_score'] = f"{val}%"
                        break
            
            # Fallback to second percentage
            if not movie_data['audience_score']:
                for val in all_percents:
                    if val != tomatometer_val:
                        movie_data['audience_score'] = f"{val}%"
                        break
        
        # Set N/A if not found
        if not movie_data['audience_score']:
            movie_data['audience_score'] = "N/A"
    
    def get_all_movie_data(self, movie_url):
        """Get comprehensive movie data from movie page"""
        try:
            time.sleep(0.5)  # Be nice to the server
            response = requests.get(movie_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Initialize data structure
            movie_data = {
                'title': None,
                'year': None,
                'description': None,
                'genres': [],
                'director': None,
                'cast': [],
                'runtime': None,
                'rating': None,  # MPAA rating (PG, R, etc.)
                'tomatometer': None,
                'audience_score': None,
                'image_url': None,
                'url': movie_url
            }
            
            # Extract in order of reliability: JSON-LD → Meta Tags → HTML
            movie_data = self._extract_from_json_ld(soup, movie_data)
            movie_data = self._extract_from_meta_tags(soup, movie_data)
            movie_data = self._extract_from_html(soup, movie_data)
            
            return movie_data
            
        except Exception as e:
            raise Exception(f"Data extraction error: {str(e)}")
    
    def get_movie_ratings(self, movie_name):
        """Main method: Search and get all data for a movie"""
        movie_url = self.search_movie(movie_name)
        
        if not movie_url:
            return None
        
        movie_data = self.get_all_movie_data(movie_url)
        return movie_data


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urlparse(self.path)
        query_params = parse_qs(parsed_path.query)
        
        # Set CORS headers
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        
        # Check for movie parameter
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
