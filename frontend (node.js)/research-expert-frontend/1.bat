@echo off
echo Creating directory structure for Research Expert Finder Frontend...

:: Create main project directory
mkdir research-expert-frontend
cd research-expert-frontend

:: Create config directory
mkdir config
echo // Proxy configuration file > config\proxy.js

:: Create controllers directory
mkdir controllers
echo // View controller file > controllers\viewController.js

:: Create public directory and subdirectories
mkdir public
mkdir public\css
mkdir public\js
mkdir public\images
echo /* Styles for the application */ > public\css\styles.css
echo // Client-side JavaScript code > public\js\main.js

:: Create routes directory
mkdir routes
echo // Main routes definition > routes\index.js

:: Create views directory and subdirectories
mkdir views
mkdir views\layouts
mkdir views\partials
echo <!-- Main layout template --> > views\layouts\main.ejs
echo <!-- Header partial --> > views\partials\header.ejs
echo <!-- Footer partial --> > views\partials\footer.ejs
echo <!-- Home page --> > views\index.ejs
echo <!-- Results page --> > views\results.ejs
echo <!-- Expert profile page --> > views\expert.ejs
echo <!-- Error page --> > views\error.ejs
echo <!-- About page --> > views\about.ejs

:: Create main application files
echo // Main application entry point > app.js
echo PORT=3000 > .env
echo PYTHON_API_URL=http://localhost:5000 >> .env
echo NODE_ENV=development >> .env

:: Create package.json with basic configuration
echo {
echo   "name": "research-expert-frontend",
echo   "version": "1.0.0",
echo   "description": "Frontend for Research Expert Finder System",
echo   "main": "app.js",
echo   "scripts": {
echo     "start": "node app.js",
echo     "dev": "nodemon app.js"
echo   },
echo   "dependencies": {
echo     "express": "^4.17.1",
echo     "ejs": "^3.1.6",
echo     "body-parser": "^1.19.0",
echo     "http-proxy-middleware": "^2.0.1",
echo     "axios": "^0.24.0",
echo     "dotenv": "^10.0.0"
echo   },
echo   "devDependencies": {
echo     "nodemon": "^2.0.15"
echo   }
echo } > package.json

echo Directory structure has been created successfully!
echo To install dependencies, run: npm install
echo To start the development server, run: npm run dev

cd ..