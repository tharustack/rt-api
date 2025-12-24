# 🍅 Rotten Tomatoes Rating API

A serverless API to fetch Rotten Tomatoes ratings deployed on Vercel.

## 🚀 Deploy to Vercel

### Method 1: Using Vercel CLI (Recommended)

1. **Install Vercel CLI:**
```bash
npm install -g vercel
```

2. **Login to Vercel:**
```bash
vercel login
```

3. **Deploy:**
```bash
vercel
```

Follow the prompts:
- Set up and deploy? **Y**
- Which scope? Select your account
- Link to existing project? **N**
- Project name? (press enter for default)
- Directory? `./` (press enter)
- Want to override settings? **N**

4. **Deploy to Production:**
```bash
vercel --prod
```

### Method 2: Using GitHub + Vercel Dashboard

1. **Push to GitHub:**
```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

2. **Connect to Vercel:**
   - Go to [vercel.com](https://vercel.com)
   - Click "Add New" → "Project"
   - Import your GitHub repository
   - Click "Deploy"

## 📁 Project Structure

```
your-project/
├── api/
│   └── rating.py          # API endpoint
├── vercel.json            # Vercel configuration
├── requirements.txt       # Python dependencies
└── README.md             # This file
```

## 🔧 API Usage

### Endpoint
```
GET /api/rating?movie=MOVIE_NAME
```

### Example Requests

**Using cURL:**
```bash
curl "https://your-project.vercel.app/api/rating?movie=Inception"
```

**Using JavaScript (fetch):**
```javascript
fetch('https://your-project.vercel.app/api/rating?movie=Inception')
  .then(response => response.json())
  .then(data => console.log(data));
```

**Using Python:**
```python
import requests

response = requests.get('https://your-project.vercel.app/api/rating', 
                       params={'movie': 'Inception'})
print(response.json())
```

### Response Format

**Success Response:**
```json
{
  "success": true,
  "data": {
    "title": "Inception",
    "year": "2010",
    "tomatometer": "87%",
    "audience_score": "91%",
    "url": "https://www.rottentomatoes.com/m/inception"
  }
}
```

**Error Response:**
```json
{
  "success": false,
  "error": "Movie not found"
}
```

## 🧪 Test Locally

1. **Install dependencies:**
```bash
pip install -r requirements.txt
pip install vercel
```

2. **Run locally:**
```bash
vercel dev
```

3. **Test:**
```bash
curl "http://localhost:3000/api/rating?movie=Inception"
```

## 🎯 Example Movies to Test

- Inception
- The Shawshank Redemption
- The Dark Knight
- Interstellar
- Pulp Fiction

## ⚠️ Important Notes

1. **Rate Limiting:** Be respectful with requests. Add delays between calls.
2. **Caching:** Consider implementing caching for frequently requested movies.
3. **Terms of Service:** Review Rotten Tomatoes' ToS before heavy usage.
4. **Timeouts:** Serverless functions have execution time limits (10s on free tier).

## 🔒 Environment Variables (Optional)

If you want to add API key protection:

1. Add to `vercel.json`:
```json
{
  "env": {
    "API_KEY": "@api-key"
  }
}
```

2. Set in Vercel dashboard or CLI:
```bash
vercel env add API_KEY
```

3. Check in your API:
```python
api_key = os.environ.get('API_KEY')
if request_key != api_key:
    return error
```

## 📝 License

MIT License - Feel free to use and modify!

## 🤝 Contributing

Pull requests are welcome! For major changes, please open an issue first.

## 📧 Support

Having issues? Check:
1. Vercel deployment logs
2. Browser console for CORS errors
3. Test with simple movie names first

Happy coding! 🎬🍿
