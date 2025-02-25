// Main application entry point 
const express = require('express');
const path = require('path');
const bodyParser = require('body-parser');
const setupProxy = require('./config/proxy');
require('dotenv').config();

// Import routes
const indexRoutes = require('./routes/index');

// Initialize application
const app = express();
const PORT = process.env.PORT || 3000;

// Set view engine
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

// Middleware
app.use(bodyParser.urlencoded({ extended: false }));
app.use(bodyParser.json());
app.use(express.static(path.join(__dirname, 'public')));

// Setup API proxy
setupProxy(app);

// Routes
app.use('/', indexRoutes);

// Error handling
app.use((req, res) => {
  res.status(404).render('error', { 
    title: 'Page Not Found',
    message: 'The page you requested does not exist',
    error: { status: 404 }
  });
});

app.use((err, req, res, next) => {
  console.error(err.stack);
  res.status(err.status || 500).render('error', { 
    title: 'Server Error',
    message: 'An error occurred while processing your request',
    error: { 
      status: err.status || 500, 
      stack: process.env.NODE_ENV === 'development' ? err.stack : '' 
    }
  });
});

// Start server
app.listen(PORT, () => {
  console.log(`Frontend server started on port: ${PORT}`);
  console.log(`API requests will be proxied to: ${process.env.PYTHON_API_URL || 'http://localhost:5000'}`);
});

module.exports = app;