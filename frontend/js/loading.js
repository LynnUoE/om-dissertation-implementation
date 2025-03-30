// loading.js - Define loading indicator functions
(function() {
    // Define loading functions immediately
    window.showLoading = function(message) {
        console.log('Loading started:', message || 'Processing request...');
        
        // Create a loading overlay if it doesn't exist
        let loadingOverlay = document.getElementById('loading-overlay');
        if (!loadingOverlay) {
            loadingOverlay = document.createElement('div');
            loadingOverlay.id = 'loading-overlay';
            loadingOverlay.style.position = 'fixed';
            loadingOverlay.style.top = '0';
            loadingOverlay.style.left = '0';
            loadingOverlay.style.width = '100%';
            loadingOverlay.style.height = '100%';
            loadingOverlay.style.backgroundColor = 'rgba(0, 0, 0, 0.7)';
            loadingOverlay.style.display = 'flex';
            loadingOverlay.style.justifyContent = 'center';
            loadingOverlay.style.alignItems = 'center';
            loadingOverlay.style.zIndex = '9999';
            
            const spinnerContainer = document.createElement('div');
            spinnerContainer.style.textAlign = 'center';
            spinnerContainer.style.color = 'white';
            
            const spinner = document.createElement('div');
            spinner.style.border = '5px solid rgba(255, 255, 255, 0.3)';
            spinner.style.borderTop = '5px solid white';
            spinner.style.borderRadius = '50%';
            spinner.style.width = '50px';
            spinner.style.height = '50px';
            spinner.style.margin = '0 auto 15px auto';
            spinner.style.animation = 'spin 1s linear infinite';
            
            const style = document.createElement('style');
            style.textContent = '@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }';
            
            const text = document.createElement('p');
            text.textContent = message || 'Processing request...';
            
            spinnerContainer.appendChild(spinner);
            spinnerContainer.appendChild(text);
            loadingOverlay.appendChild(spinnerContainer);
            document.head.appendChild(style);
            document.body.appendChild(loadingOverlay);
        } else {
            loadingOverlay.style.display = 'flex';
            const messageElement = loadingOverlay.querySelector('p');
            if (messageElement && message) {
                messageElement.textContent = message;
            }
        }
    };

    window.hideLoading = function() {
        console.log('Loading finished');
        const loadingOverlay = document.getElementById('loading-overlay');
        if (loadingOverlay) {
            loadingOverlay.style.display = 'none';
        }
    };
})();