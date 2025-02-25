// Main routes definition 
const express = require('express');
const router = express.Router();
const viewController = require('../controllers/viewController');

// Home page
router.get('/', viewController.showHomePage);

// Search processing
router.post('/search', viewController.handleSearch);

// Expert details
router.get('/expert/:id', viewController.showExpertDetails);

// About page
router.get('/about', (req, res) => {
  res.render('about', { title: 'About the System', path: '/about' });
});

module.exports = router;