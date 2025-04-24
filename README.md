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
- NodeJS (optional, for development tools)

### Backend Setup

1. Clone the repository
   ```
   git clone https://github.com/yourusername/litfinder.git
   cd litfinder
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

4. Create a `.env` file in the root directory with the following variables:
   ```
   OPENAI_API_KEY=your_openai_api_key
   RESEARCHER_EMAIL=your_email@example.com  # Used for OpenAlex API identification
   STATIC_FOLDER=../frontend
   DEBUG=True  # Set to False in production
   HOST=0.0.0.0
   PORT=5000
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
server {
    listen 80;
    server_name localhost;  # Replace with your domain in production

    # Serve static frontend files
    location / {
        root /path/to/litfinder/frontend;  # Update with your actual path
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    # Proxy API requests to the Flask backend
    location /api/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
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
litfinder/
├── api_server.py               # Main Flask API server
├── query_processor.py          # Natural language query processing
├── literature_searcher.py      # Publication search functionality
├── openalex_client.py          # Interface to OpenAlex API
├── research_analyzer.py        # Publication analysis functionality
├── requirements.txt            # Python dependencies
├── .env                        # Environment variables (not in repo)
└── frontend/                   # Static frontend files
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

2. For development, you can use a simple HTTP server:
   ```
   cd frontend
   python -m http.server 8080
   ```

3. Access the frontend at http://localhost:8080

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
   - Interdisciplinary search
   - Viewing publication details
   - Saving publications

## Deployment

For production deployment:

1. Update the `.env` file with production settings:
   ```
   DEBUG=False
   HOST=0.0.0.0
   PORT=5000
   ```

2. Configure a production WSGI server (e.g., Gunicorn):
   ```
   pip install gunicorn
   gunicorn -w 4 -b 0.0.0.0:5000 api_server:app
   ```

3. Configure Nginx with HTTPS:
   ```nginx
   server {
       listen 443 ssl;
       server_name yourdomain.com;
       
       ssl_certificate /path/to/cert.pem;
       ssl_certificate_key /path/to/key.pem;
       
       # Frontend and API proxy configurations as before
   }
   ```

4. Set up a systemd service for automatic startup:
   ```
   [Unit]
   Description=LitFinder API Server
   After=network.target

   [Service]
   User=www-data
   WorkingDirectory=/path/to/litfinder
   ExecStart=/path/to/litfinder/venv/bin/gunicorn -w 4 -b 0.0.0.0:5000 api_server:app
   Restart=on-failure

   [Install]
   WantedBy=multi-user.target
   ```

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
   - Check environment variable configuration
   - Verify Python dependencies are correctly installed

### Logs

- **Backend Logs**: Check the Flask server output or configured log file
- **Nginx Logs**: `/var/log/nginx/access.log` and `/var/log/nginx/error.log`
- **Browser Console**: Check for JavaScript errors in the browser developer tools

## Future Work

Potential enhancements for the system:

1. Implement user authentication and saved searches
2. Add visualization tools for research topics and connections
3. Incorporate advanced filtering options
4. Implement citation network analysis
5. Add export functionality for search results
6. Develop personalized recommendation features
7. Implement Retrieval-Augmented Generation (RAG) for improved analysis

## License

[Your license information here]

## Acknowledgments

- OpenAlex for providing the comprehensive academic database
- OpenAI for GPT-4o API access
