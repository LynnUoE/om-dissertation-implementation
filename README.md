# LitFinder - Academic Literature Search System

LitFinder is an LLM-enhanced academic expertise search system that helps users discover relevant research publications using natural language queries. The system bridges the vocabulary gap between natural language and academic terminology, particularly focusing on interdisciplinary research discovery.

## System Architecture

The system follows a service-oriented architecture with:

- **Frontend**: A responsive web application built with HTML, CSS, and JavaScript
- **Backend**: A Python-based API server using Flask
- **Deployment**: Nginx for serving static content and proxying API requests

### Core Components

1. **Query Processor**: Transforms natural language queries into structured search parameters using GPT-4o
2. **Literature Searcher**: Interfaces with the OpenAlex API to find relevant academic publications
3. **Research Analyzer**: Evaluates and contextualizes search results to provide meaningful insights

## Setup and Installation

### Prerequisites

- Python 3.12+
- Nginx
- OpenAI API key

### Backend Setup

1. Clone the repository
   ```
   git clone https://github.com/LynnUoE/om-dissertation-implementation.git
   ```

2. Create a virtual environment
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows, use: venv\Scripts\activate
   ```

3. Install dependencies
   ```
   pip install -r requirements.txt
   ```

4. Edit the  `.env` file in the backend directory with the following variables:
   ```
   OPENAI_API_KEY=your_openai_api_key
   RESEARCHER_EMAIL=your_email@example.com 
   STATIC_FOLDER=../frontend
   DEBUG=True  # Set to False in production
   # Flask Configuration
   FLASK_ENV=development
   FLASK_DEBUG=1
   ```

5. Run the backend server
   ```
   python api_server.py
   ```

### Frontend Setup

The frontend is static HTML, CSS, and JavaScript that can be served directly by Nginx.

1. Configure Nginx to serve the frontend and proxy API requests:

Create a configuration file at `/etc/nginx/sites-available/litfinder.conf` (Linux) or in your Nginx configuration directory (Windows):

```nginx
worker_processes 1;

events {
    worker_connections 1024;
}

http {
    include       mime.types;
    default_type  application/octet-stream;
    sendfile      on;
    keepalive_timeout 65;
    
    # Performance optimizations
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;
    gzip_comp_level 6;
    client_max_body_size 10M;

    server {
        listen       80 default_server;
        server_name  localhost;
        
        # Root directory for frontend static files
        root "path to your frontend";
        
        # Main location block for frontend
        location / {
            index  index.html;
            try_files $uri $uri/ /index.html;
        }
        
        # Handle API requests and proxy to Flask backend
        location /api/ {
            proxy_pass http://localhost:5000/api/;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_connect_timeout 60s;
            proxy_read_timeout 120s;
            proxy_send_timeout 120s;
            
            # CORS headers for API requests
            add_header 'Access-Control-Allow-Origin' '*' always;
            add_header 'Access-Control-Allow-Methods' 'GET, POST, OPTIONS, PUT, DELETE' always;
            add_header 'Access-Control-Allow-Headers' 'DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range,Authorization' always;
            
            # Handle OPTIONS method for CORS preflight
            if ($request_method = 'OPTIONS') {
                add_header 'Access-Control-Allow-Origin' '*';
                add_header 'Access-Control-Allow-Methods' 'GET, POST, OPTIONS, PUT, DELETE';
                add_header 'Access-Control-Allow-Headers' 'DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range,Authorization';
                add_header 'Access-Control-Max-Age' 1728000;
                add_header 'Content-Type' 'text/plain; charset=utf-8';
                add_header 'Content-Length' 0;
                return 204;
            }
        }
        
        # JS files
        location ~ \.js$ {
            root "path to your frontend";
            expires 7d;
            add_header Cache-Control "public, max-age=604800";
            add_header Content-Type "application/javascript";
            try_files $uri =404;
        }
        
        # CSS files
        location ~ \.css$ {
            root "path to your frontend";
            expires 7d;
            add_header Cache-Control "public, max-age=604800";
            add_header Content-Type "text/css";
            try_files $uri =404;
        }
        
        # HTML files
        location ~ \.html$ {
            root "path to your frontend";
            expires -1;
            add_header Cache-Control "no-store, no-cache, must-revalidate, proxy-revalidate, max-age=0";
            try_files $uri /index.html;
        }
        
        # Media files
        location ~* \.(jpg|jpeg|png|gif|ico|svg|woff|woff2|ttf|eot)$ {
            root "path to your frontend";
            expires 30d;
            add_header Cache-Control "public, max-age=2592000";
            try_files $uri =404;
        }
        
        # Error pages
        error_page 404 /index.html;
        error_page 500 502 503 504 /50x.html;
        location = /50x.html {
            root html;
        }
    }
}
```

2. Enable the configuration and restart Nginx:
   ```
   sudo ln -s /etc/nginx/sites-available/litfinder.conf /etc/nginx/sites-enabled/
   sudo nginx -t  # Test configuration
   sudo systemctl restart nginx
   ```

## Project Structure

```
backend/
├── api_server.py               # Main Flask API server
├── query_processor.py          # Natural language query processing
├── literature_searcher.py      # Publication search functionality
├── openalex_client.py          # Interface to OpenAlex API
├── research_analyzer.py        # Publication analysis functionality
├── requirements.txt            # Python dependencies
└── .env                        # Environment variables (not in repo)
frontend/                   # Static frontend files
├── index.html              # Home page with search form
├── result.html             # Search results page
├── publication.html        # Publication details page
├── css/                    # Stylesheets
│   ├── style.css           # Global styles
│   ├── result.css          # Results page styles
│   └── publication.css     # Publication page styles
└── js/                     # JavaScript files
     ├── main.js             # Common functionality
     ├── api-service.js      # API communication service
     ├── query-processor.js  # Frontend query handling
     ├── result-handler.js   # Results page script
     └── publication-view.js # Publication details script
```

## API Endpoints

The backend provides the following API endpoints:

- `POST /api/search` - Search for literature based on natural language query
- `POST /api/advanced-search` - Search with specific research areas and topics
- `POST /api/interdisciplinary-search` - Specialized search for interdisciplinary research
- `GET /api/publication/{id}` - Get detailed information about a publication
- `GET /api/publication/{id}/analyze` - Analyze a publication in the context of a query
- `POST /api/process-query` - Process a query without performing search
- `GET /api/health_check` - Check API health status

## Development

### Backend Development

1. Activate the virtual environment
   ```
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Run the server in debug mode
   ```
   python api_server.py
   ```

3. Test API endpoints using tools like Postman or curl

### Frontend Development

The frontend can be developed independently from the backend by ensuring the API service URLs point to your development backend.

1. Edit `js/api-service.js` to set the correct API base URL for development:
   ```javascript
   const API_BASE_URL = 'http://localhost:5000/api';
   ```

2. Access the frontend at http://localhost

## Integration Testing

To test the full frontend-backend integration:

1. Start the Flask backend server
   ```
   python api_server.py
   ```

2. Ensure Nginx is configured and running to serve the frontend and proxy API requests

3. Access the application via Nginx URL (e.g., http://localhost or your domain)

4. Test the following workflows:
   - Simple search from the home page
   - Advanced search with research areas and topics
   - Viewing publication details


## Troubleshooting

### Common Issues

1. **API Connection Errors**
   - Check if the Flask server is running
   - Verify Nginx proxy configuration
   - Ensure the API_BASE_URL in api-service.js matches your setup

2. **OpenAI API Issues**
   - Verify your API key in the .env file
   - Check API usage limits and quotas
   - Review network connectivity to OpenAI services

3. **OpenAlex API Issues**
   - Confirm internet connectivity
   - Check the email address used for identification
   - Review the OpenAlex API documentation for changes

4. **Frontend Not Loading**
   - Check Nginx error logs: `/var/log/nginx/error.log`
   - Verify file permissions on frontend files
   - Check for JavaScript console errors in the browser

5. **Backend Server Errors**
   - Review Flask server logs for error messages
   - Check the environment variable configuration
   - Verify Python dependencies are correctly installed

### Logs

- **Backend Logs**: Check the Flask server output or configured log file
- **Nginx Logs**: `/var/log/nginx/access.log` and `/var/log/nginx/error.log`
- **Browser Console**: Check for JavaScript errors in the browser developer tools


## Acknowledgments

- OpenAlex for providing the comprehensive academic database
- OpenAI for GPT-4o API access
