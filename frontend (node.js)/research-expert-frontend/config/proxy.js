const { createProxyMiddleware } = require('http-proxy-middleware');

module.exports = function setupProxy(app) {
  // Proxy API requests to Python backend
  app.use(
    '/api',
    createProxyMiddleware({
      target: process.env.PYTHON_API_URL || 'http://localhost:5000',
      changeOrigin: true,
      pathRewrite: { '^/api': '/api' },
      logLevel: 'debug',
      onError: (err, req, res) => {
        console.error('Proxy error:', err);
        res.status(500).json({ error: 'Internal server error, please try again later' });
      }
    })
  );
};