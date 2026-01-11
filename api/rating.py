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
            
            # Look for movie links in search results
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
    
    def _extract_trailer_url(self, soup, movie_url):
        """Extract trailer URL with multiple strategies"""
        
        # Strategy 1: Look in media-modal or trailer sections
        trailer_sections = soup.find_all(['section', 'div'], class_=re.compile(r'trailer|media', re.I))
        for section in trailer_sections:
            # Check for YouTube iframes
            iframe = section.find('iframe', src=re.compile(r'youtube|youtube-nocookie', re.I))
            if iframe:
                src = iframe.get('src', '')
                # Extract video ID and return clean YouTube URL
                video_id_match = re.search(r'(?:embed/|v=)([a-zA-Z0-9_-]{11})', src)
                if video_id_match:
                    return f"https://www.youtube.com/watch?v={video_id_match.group(1)}"
                return src
        
        # Strategy 2: Look for data attributes containing YouTube URLs
        for elem in soup.find_all(attrs={'data-video-id': True}):
            video_id = elem.get('data-video-id')
            if video_id and len(video_id) == 11:
                return f"https://www.youtube.com/watch?v={video_id}"
        
        # Strategy 3: Search all <a> tags for YouTube links
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            if 'youtube.com/watch' in href or 'youtu.be/' in href:
                # Clean up the URL
                video_id_match = re.search(r'(?:watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})', href)
                if video_id_match:
                    return f"https://www.youtube.com/watch?v={video_id_match.group(1)}"
        
        # Strategy 4: Parse all script tags for YouTube video IDs
        for script in soup.find_all('script'):
            if script.string:
                # Look for YouTube video IDs in various formats
                matches = re.findall(r'"videoId"\s*:\s*"([a-zA-Z0-9_-]{11})"', script.string)
                if matches:
                    return f"https://www.youtube.com/watch?v={matches[0]}"
                
                matches = re.findall(r'youtube\.com/(?:embed/|watch\?v=)([a-zA-Z0-9_-]{11})', script.string)
                if matches:
                    return f"https://www.youtube.com/watch?v={matches[0]}"
        
        # Strategy 5: Try fetching the videos page directly
        try:
            videos_url = movie_url.rstrip('/') + '/videos'
            response = requests.get(videos_url, headers=self.headers, timeout=5)
            if response.status_code == 200:
                videos_soup = BeautifulSoup(response.content, 'html.parser')
                
                # Look for YouTube iframe
                iframe = videos_soup.find('iframe', src=re.compile(r'youtube', re.I))
                if iframe:
                    src = iframe.get('src')
                    video_id_match = re.search(r'(?:embed/|v=)([a-zA-Z0-9_-]{11})', src)
                    if video_id_match:
                        return f"https://www.youtube.com/watch?v={video_id_match.group(1)}"
        except:
            pass
        
        return None
    
    def _extract_photos(self, soup, movie_url):
        """Extract movie photos with better filtering"""
        photos = []
        seen = set()
        
        # Keywords to exclude UI elements
        exclude_keywords = ['newsletter', 'subscribe', 'logo', 'icon', 'sprite', 
                           'placeholder', 'avatar', 'profile', 'user', 'button',
                           'arrow', 'star', 'badge', 'award', 'certified', 'fresh',
                           'rotten', 'header', 'footer', 'nav', 'menu']
        
        # Strategy 1: Target gallery/photos page directly
        try:
            photos_url = movie_url.rstrip('/') + '/pictures'
            response = requests.get(photos_url, headers=self.headers, timeout=5)
            if response.status_code == 200:
                photos_soup = BeautifulSoup(response.content, 'html.parser')
                
                # Look for gallery images
                for img in photos_soup.find_all('img'):
                    src = img.get('data-src') or img.get('src')
                    if not src or not src.startswith('http'):
                        continue
                    
                    if src in seen:
                        continue
                    
                    # Filter out small icons and UI elements
                    if any(kw in src.lower() for kw in exclude_keywords):
                        continue
                    
                    # Look for actual movie stills/photos
                    if any(indicator in src.lower() for indicator in ['_gallery_', 'still', 'photo', '/pictures/', 'original']):
                        photos.append(src)
                        seen.add(src)
                        
                    # Accept images with large dimensions in filename
                    elif re.search(r'(\d{3,4})[x_](\d{3,4})', src):
                        match = re.search(r'(\d{3,4})[x_](\d{3,4})', src)
                        width, height = int(match.group(1)), int(match.group(2))
                        if width >= 300 and height >= 200:
                            photos.append(src)
                            seen.add(src)
        except Exception as e:
            pass
        
        # Strategy 2: Look for poster and hero images on main page
        poster_selectors = [
            'img[class*="poster"]',
            'img[data-qa*="poster"]',
            'picture img',
            'div[class*="poster"] img'
        ]
        
        for selector in poster_selectors:
            for img in soup.select(selector):
                src = img.get('data-src') or img.get('src')
                if src and src.startswith('http') and src not in seen:
                    if not any(kw in src.lower() for kw in exclude_keywords):
                        photos.append(src)
                        seen.add(src)
        
        # Strategy 3: Look in srcset attributes for high-quality versions
        for elem in soup.find_all(['img', 'source'], srcset=True):
            srcset = elem.get('srcset', '')
            urls = [u.strip().split()[0] for u in srcset.split(',') if u.strip()]
            
            for url in urls:
                if url.startswith('http') and url not in seen:
                    if not any(kw in url.lower() for kw in exclude_keywords):
                        # Prefer larger images
                        if re.search(r'(\d{3,4})[wx]', url):
                            photos.append(url)
                            seen.add(url)
        
        return photos[:20]  # Return up to 20 photos
    
    def _extract_synopsis(self, soup):
        """Extract movie synopsis with improved accuracy"""
        
        # Exclude these patterns from synopsis
        exclude_patterns = [
            r'newsletter', r'subscribe', r'sign up', r'follow us',
            r'download', r'app store', r'google play', r'certified fresh',
            r'discover rotten tomatoes', r'what to watch', r'©', r'copyright'
        ]
        
        def is_valid_synopsis(text):
            """Check if text looks like a real synopsis"""
            if len(text) < 50:
                return False
            if any(re.search(pattern, text, re.I) for pattern in exclude_patterns):
                return False
            # Synopsis should have sentences
            if text.count('.') < 1:
                return False
            return True
        
        candidates = []
        
        # Strategy 1: Look for data-qa attributes (most reliable)
        for elem in soup.find_all(attrs={'data-qa': re.compile(r'synopsis|movie-info-synopsis', re.I)}):
            text = elem.get_text(separator=' ', strip=True)
            text = re.sub(r'\s+', ' ', text)
            if is_valid_synopsis(text):
                return text  # This is usually the most accurate
        
        # Strategy 2: JSON-LD structured data
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
        
        # Strategy 3: Meta description
        meta_desc = soup.find('meta', property='og:description') or soup.find('meta', attrs={'name': 'description'})
        if meta_desc:
            content = meta_desc.get('content', '')
            if is_valid_synopsis(content):
                candidates.append((len(content), content))
        
        # Strategy 4: Look for specific class patterns
        synopsis_classes = ['synopsis', 'plot', 'movie-info-synopsis', 'description']
        for cls in synopsis_classes:
            for elem in soup.find_all(class_=re.compile(cls, re.I)):
                text = elem.get_text(separator=' ', strip=True)
                text = re.sub(r'\s+', ' ', text)
                if is_valid_synopsis(text):
                    candidates.append((len(text), text))
        
        # Return the most appropriate synopsis
        if candidates:
            # Prefer synopses between 100-1000 characters
            candidates.sort(key=lambda x: abs(x[0] - 300))
            for length, text in candidates:
                if 100 <= length <= 1500:
                    return text
            return candidates[0][1]
        
        return None
    
    def _extract_release_dates(self, soup, movie_data):
        """Extract release dates with better parsing"""
        
        # Look for specific date patterns in the page
        page_text = soup.get_text()
        
        # Strategy 1: Look for structured date information
        date_patterns = {
            'theaters': [
                r'Release\s+Date\s+\(Theaters?\)\s*:?\s*([A-Z][a-z]+\s+\d{1,2},\s+\d{4})',
                r'In\s+Theaters?\s*:?\s*([A-Z][a-z]+\s+\d{1,2},\s+\d{4})',
                r'Theatrical\s+Release\s*:?\s*([A-Z][a-z]+\s+\d{1,2},\s+\d{4})',
            ],
            'streaming': [
                r'Release\s+Date\s+\(Streaming\)\s*:?\s*([A-Z][a-z]+\s+\d{1,2},\s+\d{4})',
                r'Streaming\s*:?\s*([A-Z][a-z]+\s+\d{1,2},\s+\d{4})',
                r'On\s+Streaming\s*:?\s*([A-Z][a-z]+\s+\d{1,2},\s+\d{4})',
            ]
        }
        
        # Try to find theater release date
        if not movie_data.get('release_date_theaters'):
            for pattern in date_patterns['theaters']:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    date_str = match.group(1)
                    # Validate it's not "Opening This Week" or similar
                    if re.match(r'^[A-Z][a-z]+\s+\d{1,2},\s+\d{4}$', date_str):
                        movie_data['release_date_theaters'] = date_str
                        break
        
        # Try to find streaming release date
        if not movie_data.get('release_date_streaming'):
            for pattern in date_patterns['streaming']:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    date_str = match.group(1)
                    if re.match(r'^[A-Z][a-z]+\s+\d{1,2},\s+\d{4}$', date_str):
                        movie_data['release_date_streaming'] = date_str
                        break
        
        # Strategy 2: Look in specific sections
        info_sections = soup.find_all(['div', 'section'], class_=re.compile(r'movie-info|info-item', re.I))
        for section in info_sections:
            text = section.get_text()
            
            if 'Release Date (Theaters)' in text or 'In Theaters' in text:
                date_match = re.search(r'([A-Z][a-z]+\s+\d{1,2},\s+\d{4})', text)
                if date_match and not movie_data.get('release_date_theaters'):
                    movie_data['release_date_theaters'] = date_match.group(1)
            
            if 'Release Date (Streaming)' in text or 'Streaming' in text:
                date_match = re.search(r'([A-Z][a-z]+\s+\d{1,2},\s+\d{4})', text)
                if date_match and not movie_data.get('release_date_streaming'):
                    movie_data['release_date_streaming'] = date_match.group(1)
        
        # Strategy 3: JSON-LD fallback
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script.string)
                if isinstance(data, list):
                    data = data[0]
                
                if 'datePublished' in data and not movie_data.get('release_date_theaters'):
                    movie_data['release_date_theaters'] = data['datePublished']
            except:
                pass
        
        return movie_data
    
    def _extract_from_json_ld(self, soup, movie_data):
        """Extract from JSON-LD structured data"""
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
        """Extract from HTML elements"""
        
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
        """Extract Tomatometer and Audience scores"""
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
        """Extract additional movie metadata"""
        info = {}
        page_text = soup.get_text()
        
        patterns = {
            'producer': r'Producer[s]?[:\s]+([^\n\r]+?)(?=\n|Director|Writer|$)',
            'screenwriter': r'(?:Screenwriter|Writer)[s]?[:\s]+([^\n\r]+?)(?=\n|Director|Producer|$)',
            'distributor': r'Distributor[:\s]+([^\n\r]+?)(?=\n|$)',
            'production_co': r'Production\s+Co[:\s]+([^\n\r]+?)(?=\n|$)',
            'original_language': r'Original\s+Language[:\s]+([^\n\r]+?)(?=\n|$)',
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
        """Get all movie data from Rotten Tomatoes"""
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
            
            # Extract data from various sources
            movie_data = self._extract_from_json_ld(soup, movie_data)
            movie_data = self._extract_from_html(soup, movie_data)
            
            # Extract synopsis
            if not movie_data['synopsis']:
                movie_data['synopsis'] = self._extract_synopsis(soup)
            
            # Extract trailer
            if not movie_data['trailer_url']:
                movie_data['trailer_url'] = self._extract_trailer_url(soup, movie_url)
            
            # Extract photos
            if not movie_data['photos'] or len(movie_data['photos']) < 2:
                movie_data['photos'] = self._extract_photos(soup, movie_url)
            
            # Extract release dates
            movie_data = self._extract_release_dates(soup, movie_data)
            
            # Extract additional movie info
            info = self._extract_movie_info(soup)
            for key, value in info.items():
                if not movie_data.get(key):
                    movie_data[key] = value
            
            return movie_data
            
        except Exception as e:
            raise Exception(f"Error fetching movie data: {str(e)}")
    
    def get_movie_ratings(self, movie_name):
        """Main method to get movie ratings and data"""
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
