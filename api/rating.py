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
            
            # Find all links with /m/ pattern
            links = soup.find_all('a', {'href': re.compile(r'/m/[\w_\-]+')})
            
            if not links:
                return None
            
            search_term = movie_name.lower().strip()
            best_match = None
            best_score = 0
            
            # Find best title match
            for link in links:
                title = link.text.strip().lower()
                
                # Exact match wins
                if title == search_term:
                    best_match = link
                    break
                
                # Check if all main words from search are in title
                search_words = [w for w in search_term.split() if len(w) > 2]
                if all(w in title for w in search_words):
                    score = sum(len(w) for w in search_words)
                    if score > best_score:
                        best_score = score
                        best_match = link
            
            # Fallback to first link if no good match
            if not best_match:
                best_match = links[0]
            
            if best_match:
                href = best_match.get('href')
                movie_url = self.base_url + href if not href.startswith('http') else href
                return movie_url
            
            return None
            
        except Exception as e:
            raise Exception(f"Search error: {str(e)}")
    
    def get_rating(self, movie_url):
        """Get Rotten Tomatoes ratings from movie page"""
        try:
            time.sleep(0.5)  # Reduced delay for API
            
            response = requests.get(movie_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            ratings = {
                'title': None,
                'year': None,
                'description': None,
                'tomatometer': None,
                'audience_score': None,
                'casts': [],
                'poster_url': None,
                'backdrop_url': None,
                'url': movie_url
            }
            
            # Get movie title from h1
            title_tag = soup.find('h1')
            if title_tag:
                ratings['title'] = title_tag.text.strip()
            
            # Get year
            all_text = soup.get_text()
            year_matches = re.findall(r'\b(19|20)\d{2}\b', all_text)
            if year_matches:
                idx = all_text.find(year_matches[0])
                if idx != -1:
                    year_str = all_text[idx:idx+4]
                    if year_str.isdigit():
                        ratings['year'] = year_str
            
            # Try JSON-LD first
            json_ld = soup.find('script', {'type': 'application/ld+json'})
            if json_ld:
                try:
                    import json as js
                    data = js.loads(json_ld.string)
                    if 'aggregateRating' in data:
                        rating = data['aggregateRating']
                        if 'ratingValue' in rating:
                            ratings['tomatometer'] = f"{rating['ratingValue']}%"
                    if 'description' in data:
                        ratings['description'] = data['description']
                    if 'actors' in data:
                        for actor in data['actors']:
                            ratings['casts'].append({
                                'actor': actor.get('name'),
                                'character': None
                            })
                    if 'image' in data:
                        ratings['poster_url'] = data['image']

                    # Search for backdrop in other scripts
                    media_hero_script = soup.find('script', {'id': 'media-hero-json'})
                    if media_hero_script:
                        try:
                            media_hero_data = js.loads(media_hero_script.string)
                            if 'backdropImage' in media_hero_data:
                                ratings['backdrop_url'] = media_hero_data['backdropImage'].get('url')
                        except js.JSONDecodeError as e:
                            print(f"Error parsing media-hero-json: {e}")
                except (KeyError, js.JSONDecodeError) as e:
                    print(f"Error parsing JSON-LD: {e}")
            
            # Find all percentages
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
            
            # Get tomatometer
            if not ratings['tomatometer'] and all_percents:
                for val in all_percents:
                    if any(word in ' '.join(seen_percents[val]['contexts']) for word in ['critic', 'tomato', 'tomatometer']):
                        ratings['tomatometer'] = f"{val}%"
                        break
                
                if not ratings['tomatometer']:
                    ratings['tomatometer'] = f"{all_percents[0]}%"
            
            # Get audience score
            if len(all_percents) > 1:
                for val in all_percents:
                    if val != (ratings['tomatometer'].replace('%', '') if ratings['tomatometer'] else None):
                        if any(word in ' '.join(seen_percents[val]['contexts']) for word in ['audience', 'user', 'popcorn']):
                            ratings['audience_score'] = f"{val}%"
                            break
                
                if not ratings['audience_score'] and len(all_percents) > 1:
                    for val in all_percents:
                        if val != (ratings['tomatometer'].replace('%', '') if ratings['tomatometer'] else None):
                            ratings['audience_score'] = f"{val}%"
                            break
            
            if not ratings['audience_score']:
                ratings['audience_score'] = "N/A"
            
            return ratings
            
        except Exception as e:
            raise Exception(f"Rating fetch error: {str(e)}")
    
    def get_movie_ratings(self, movie_name):
        """Main method: Search and get ratings for a movie"""
        movie_url = self.search_movie(movie_name)
        
        if not movie_url:
            return None
        
        ratings = self.get_rating(movie_url)
        return ratings


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Parse query parameters
        parsed_path = urlparse(self.path)
        query_params = parse_qs(parsed_path.query)
        
        # Set CORS headers
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        
        # Check if movie parameter exists
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
            ratings = scraper.get_movie_ratings(movie_name)
            
            if ratings:
                response = {
                    'success': True,
                    'data': ratings
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
