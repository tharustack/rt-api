# 🎬 Rotten Tomatoes API

A free, open-source REST API that provides comprehensive movie data from Rotten Tomatoes. Get ratings, cast information, synopsis, photos, and much more - all without any authentication!

[![API Status](https://img.shields.io/badge/status-active-success.svg)]()
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

## 🌐 Live Demo & Documentation

**Full Documentation:** [https://www.cineapi.mywire.org/](https://www.cineapi.mywire.org/)

**API Endpoint:** `https://rt-api-jade.vercel.app/api/rotten-tomatoes?movie=Inception`

## ✨ Features

- 🍅 **Tomatometer & Audience Scores** - Get both critic and audience ratings
- 🎭 **Complete Movie Info** - Title, year, runtime, rating, genres
- 📝 **Synopsis** - Full movie plot description
- 👥 **Cast & Crew** - Director, producer, screenwriter, actors
- 📸 **Movie Photos** - High-quality images and posters (up to 25)
- 📅 **Release Dates** - Theater, streaming, and rerelease dates
- 💰 **Box Office Data** - US gross earnings
- 🎬 **Production Details** - Distributor, production company, sound mix, aspect ratio
- 🌍 **Original Language** - Movie's original language
- 🔗 **Direct RT Link** - Link to Rotten Tomatoes page

## 🚀 Quick Start

### Making a Request
```bash
curl "https://rt-api-jade.vercel.app/rotten-tomatoes?movie=Inception"
```

### Example Response
```json
{
  "success": true,
  "data": {
    "title": "Inception",
    "year": "2010",
    "tomatometer": "87%",
    "audience_score": "91%",
    "synopsis": "Dom Cobb is a skilled thief...",
    "genres": ["Action", "Sci-Fi", "Thriller"],
    "director": "Christopher Nolan",
    "cast": ["Leonardo DiCaprio", "Tom Hardy", "Elliot Page"],
    "rating": "PG-13",
    "runtime": "2h 28m",
    "release_date_theaters": "July 16, 2010",
    "image_url": "https://...",
    "photos": ["https://...", "https://..."],
    "url": "https://www.rottentomatoes.com/m/inception"
  }
}
```

## 📚 API Documentation

### Endpoint
```
GET /api/rotten-tomatoes
```

### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `movie` | string | Yes | Movie name to search for |

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Request success status |
| `data` | object | Movie data object |
| `title` | string | Movie title |
| `year` | string | Release year |
| `synopsis` | string | Movie plot description |
| `genres` | array | List of genres |
| `director` | string | Director name |
| `producer` | string | Producer name(s) |
| `screenwriter` | string | Screenwriter name(s) |
| `cast` | array | List of main actors |
| `distributor` | string | Distribution company |
| `production_co` | string | Production company |
| `rating` | string | MPAA rating (G, PG, PG-13, R, etc.) |
| `original_language` | string | Original language |
| `release_date_theaters` | string | Theater release date |
| `rerelease_date` | string | Rerelease date (if applicable) |
| `release_date_streaming` | string | Streaming release date |
| `box_office_usa` | string | US box office gross |
| `runtime` | string | Movie duration |
| `sound_mix` | string | Audio format |
| `aspect_ratio` | string | Screen aspect ratio |
| `tomatometer` | string | Critic score percentage |
| `audience_score` | string | Audience score percentage |
| `image_url` | string | Main poster image URL |
| `photos` | array | Array of movie photo URLs (up to 25) |
| `url` | string | Rotten Tomatoes page URL |

### Error Response
```json
{
  "success": false,
  "error": "Movie not found"
}
```

## 💻 Code Examples

### JavaScript (Fetch)
```javascript
const movieName = 'Inception';
const response = await fetch(`https://your-api-domain.com/api/rotten-tomatoes?movie=${encodeURIComponent(movieName)}`);
const data = await response.json();

if (data.success) {
  console.log(`${data.data.title} - Tomatometer: ${data.data.tomatometer}`);
}
```

### Python (Requests)
```python
import requests

movie_name = 'Inception'
response = requests.get(f'https://your-api-domain.com/api/rotten-tomatoes?movie={movie_name}')
data = response.json()

if data['success']:
    print(f"{data['data']['title']} - Tomatometer: {data['data']['tomatometer']}")
```

### cURL
```bash
curl "https://your-api-domain.com/api/rotten-tomatoes?movie=The%20Godfather"
```

### Node.js (Axios)
```javascript
const axios = require('axios');

async function getMovieData(movieName) {
  const response = await axios.get('https://your-api-domain.com/api/rotten-tomatoes', {
    params: { movie: movieName }
  });
  return response.data;
}

getMovieData('Inception').then(data => console.log(data));
```

## 🛠️ Tech Stack

- **Python 3.8+** - Core language
- **BeautifulSoup4** - Web scraping
- **Requests** - HTTP library
- **Vercel** - Serverless deployment (recommended)

## 📦 Installation (Self-Hosting)

### Prerequisites

- Python 3.8 or higher
- pip package manager

### Local Setup

1. Clone the repository
```bash
git clone https://github.com/tharustack/rt-api.git
cd rt-api
```

2. Install dependencies
```bash
pip install requests beautifulsoup4
```

3. Run locally
```bash
python -m http.server 8000
```

4. Test the API
```bash
curl "http://localhost:8000/api/rotten-tomatoes?movie=Inception"
```

### Deploy to Vercel

1. Install Vercel CLI
```bash
npm i -g vercel
```

2. Deploy
```bash
vercel
```

## ⚠️ Rate Limits & Fair Use

- This API uses web scraping and should be used responsibly
- Recommended: Cache responses to minimize requests
- Fair use policy: Don't spam requests
- No authentication required, but please be respectful

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🔗 Links

- **Website:** [https://www.cineapi.mywire.org/](https://www.cineapi.mywire.org/)
- **Documentation:** [https://www.cineapi.mywire.org/docs](https://www.cineapi.mywire.org/docs)
- **Playground:** [https://www.cineapi.mywire.org/playground](https://www.cineapi.mywire.org/playground)
- **Telegram Channel:** [https://t.me/tharustack](https://t.me/tharustack)
- **GitHub:** [https://github.com/tharustack/rt-api](https://github.com/tharustack/rt-api)

## 🙏 Acknowledgments

- Data source: [Rotten Tomatoes](https://www.rottentomatoes.com)
- Built with ❤️ using Python and BeautifulSoup

## ⚖️ Disclaimer

This API is for educational purposes only. All movie data belongs to Rotten Tomatoes and their respective owners. This project is not affiliated with or endorsed by Rotten Tomatoes.

---

**Made with ❤️ by Tharusha Dilshan**

[![Star on GitHub](https://img.shields.io/github/stars/tharustack/rt-api?style=social)](https://github.com/tharustack/rt-api)


---

## **📄 Additional Files**

### **LICENSE (MIT)**
```
MIT License

Copyright (c) 2025 Tharusha Dilshan

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

### **.gitignore**
```
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
ENV/
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Vercel
.vercel
.env
.env.local
.env.production

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db
