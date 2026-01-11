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
    
    def _extract_trailer_aggressive(self, soup, movie_url):
        """AGGRESSIVE trailer extraction with multiple methods"""
        
        # Method 1: Direct YouTube iframe
        iframes = soup.find_all('iframe')
        for iframe in iframes:
            src = iframe.get('src', '')
            if 'youtube' in src or 'youtube-nocookie' in src:
                return src
        
        # Method 2: YouTube links
        links = soup.find_all('a', href=True)
        for link in links:
            href = link.get('href', '')
            if 'youtube.com/watch' in href or 'youtu.be/' in href:
                return href
        
        # Method 3: Check all script tags for YouTube URLs
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string:
                # Look for YouTube video IDs
                yt_matches = re.findall(r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})', script.string)
                if yt_matches:
                    return f"https://www.youtube.com/watch?v={yt_matches[0]}"
        
        # Method 4: Look for data attributes
        video_elements = soup.find_all(attrs={'data-video': True})
        for elem in video_elements:
            video_data = elem.get('data-video')
            if video_data and 'youtube' in video_data:
                return video_data
        
        # Method 5: Try to fetch from the movie's videos page
        try:
            videos_url = movie_url.rstrip('/') + '/videos'
            response = requests.get(videos_url, headers=self.headers, timeout=5)
            if response.status_code == 200:
                videos_soup = BeautifulSoup(response.content, 'html.parser')
                iframe = videos_soup.find('iframe', src=re.compile(r'youtube'))
                if iframe:
                    return iframe.get('src')
        except:
            pass
        
        return None
    
    def _extract_photos_aggressive(self, soup, movie_url):
        """AGGRESSIVE photo extraction"""
        photos = []
        seen = set()
        
        # Exclusion keywords
        exclude_keywords = ['newsletter', 'subscribe', 'logo', 'icon', 'sprite', 
                           'placeholder', 'avatar', 'profile', 'user', 'button',
                           'arrow', 'star', 'badge', 'award']
        
        # Method 1: All picture elements
        for picture in soup.find_all('picture'):
            # Try source srcset
            for source in picture.find_all('source'):
                srcset = source.get('srcset', '')
                if srcset:
                    urls = [u.strip().split()[0] for u in srcset.split(',') if u.strip()]
                    for url in urls:
                        if url.startswith('http') and url not in seen:
                            if not any(kw in url.lower() for kw in exclude_keywords):
                                if any(ext in url.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                                    photos.append(url)
                                    seen.add(url)
            
            # Try img inside picture
            img = picture.find('img')
            if img:
                src = img.get('src') or img.get('data-src')
                if src and src.startswith('http') and src not in seen:
                    if not any(kw in src.lower() for kw in exclude_keywords):
                        photos.append(src)
                        seen.add(src)
        
        # Method 2: All img tags
        for img in soup.find_all('img'):
            src = img.get('data-src') or img.get('src') or img.get('data-lazy-src')
            if not src or not src.startswith('http'):
                continue
            
            if src in seen:
                continue
            
            # Filter out small images by checking natural size or file path
            if any(kw in src.lower() for kw in exclude_keywords):
                continue
            
            # Look for high-quality images
            if any(indicator in src.lower() for indicator in ['original', 'large', '1920', '1080', '720', 'gallery', 'still']):
                photos.append(src)
                seen.add(src)
            elif re.search(r'\d{3,4}x\d{3,4}', src):  # Has dimensions like 1920x1080
                photos.append(src)
                seen.add(src)
            elif len(photos) < 5:  # If we don't have many, be less strict
                photos.append(src)
                seen.add(src)
        
        # Method 3: Check style attributes for background images
        for elem in soup.find_all(attrs={'style': True}):
            style = elem.get('style', '')
            if 'background-image' in style:
                match = re.search(r'url\(["\']?([^"\'()]+)["\']?\)', style)
                if match:
                    url = match.group(1)
                    if url.startswith('http') and url not in seen:
                        if not any(kw in url.lower() for kw in exclude_keywords):
                            photos.append(url)
                            seen.add(url)
        
        # Method 4: Try accessing the photos page
        try:
            photos_url = movie_url.rstrip('/') + '/pictures'
            response = requests.get(photos_url, headers=self.headers, timeout=5)
            if response.status_code == 200:
                photos_soup = BeautifulSoup(response.content, 'html.parser')
                for img in photos_soup.find_all('img'):
                    src = img.get('src') or img.get('data-src')
                    if src and src.startswith('http') and src not in seen:
                        if not any(kw in src.lower() for kw in exclude_keywords):
                            photos.append(src)
                            seen.add(src)
        except:
            pass
        
        return photos[:15]  # Return up to 15 photos
    
    def _extract_synopsis_aggressive(self, soup):
        """AGGRESSIVE synopsis extraction"""
        
        # Bad words that indicate it's not the real synopsis
        bad_indicators = ['newsletter', 'subscribe', 'sign up', 'follow us', 
                         'download', 'app store', 'google play', 'certified fresh',
                         'discover rotten tomatoes', 'what to watch']
        
        candidates = []
        
        # Method 1: Look for any element with "synopsis" in class or id
        synopsis_elements = soup.find_all(['div', 'p', 'section'], 
                                         class_=re.compile(r'synopsis|plot|summary|description', re.I))
        synopsis_elements += soup.find_all(['div', 'p', 'section'], 
                                          id=re.compile(r'synopsis|plot|summary|description', re.I))
        
        for elem in synopsis_elements:
            text = elem.get_text(separator=' ', strip=True)
            text = re.sub(r'\s+', ' ', text)
            
            if len(text) > 50 and not any(bad in text.lower() for bad in bad_indicators):
                candidates.append((len(text), text))
        
        # Method 2: JSON-LD structured data
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script.string)
                if isinstance(data, list):
                    data = data[0]
                if 'description' in data:
                    desc = data['description']
                    if len(desc) > 50 and not any(bad in desc.lower() for bad in bad_indicators):
                        candidates.append((len(desc), desc))
            except:
                pass
        
        # Method 3: Meta tags
        for meta in soup.find_all('meta'):
            if meta.get('name') in ['description', 'og:description'] or meta.get('property') == 'og:description':
                content = meta.get('content', '')
                if len(content) > 50 and not any(bad in content.lower() for bad in bad_indicators):
                    candidates.append((len(content), content))
        
        # Method 4: Find all paragraphs and pick the longest meaningful one
        for p in soup.find_all('p'):
            text = p.get_text(strip=True)
            if len(text) > 100:
                # Check if it's actual content (not UI text)
                text_lower = text.lower()
                if not any(bad in text_lower for bad in bad_indicators):
                    # Check if it doesn't have too many links (navigation)
                    links = p.find_all('a')
                    if len(links) < 3:  # Real synopsis shouldn't have many links
                        candidates.append((len(text), text))
        
        # Method 5: Look in specific data attributes
        for elem in soup.find_all(attrs={'data-qa': re.compile(r'synopsis|description', re.I)}):
            text = elem.get_text(strip=True)
            if len(text) > 50 and not any(bad in text.lower() for bad in bad_indicators):
                candidates.append((len(text), text))
        
        # Sort by length and return the longest valid one
        if candidates:
            candidates.sort(reverse=True)
            # Return the longest one between 100-2000 characters (typical synopsis length)
            for length, text in candidates:
                if 100 <= length <= 2000:
                    return text
            # If nothing in that range, return the longest
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
    
    def _extract_movie_info_comprehensive(self, soup):
        """Extract movie metadata"""
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
                'trailer_url': None,
                'photos': [],
                'url': movie_url
            }
            
            # Extract data
            movie_data = self._extract_from_json_ld(soup, movie_data)
            movie_data = self._extract_from_html(soup, movie_data)
            
            # AGGRESSIVE extraction for the problematic fields
            if not movie_data['synopsis']:
                movie_data['synopsis'] = self._extract_synopsis_aggressive(soup)
            
            if not movie_data['trailer_url']:
                movie_data['trailer_url'] = self._extract_trailer_aggressive(soup, movie_url)
            
            if not movie_data['photos'] or len(movie_data['photos']) < 2:
                movie_data['photos'] = self._extract_photos_aggressive(soup, movie_url)
            
            # Movie info
            info = self._extract_movie_info_comprehensive(soup)
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
