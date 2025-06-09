class ProTradeXApp {
    constructor(uiSelectors) {
        this.uiSelectors = uiSelectors;
        this.elements = {}; // To store references to DOM elements

        // State Properties
        this.apiSystem = null; // Will be initialized in setupAPI
        this.isApiConnected = false; // NEW: Tracks API connection status
        this.currentTheme = localStorage.getItem('theme') || 'light';
        this.currentSection = 'dashboard'; // Default section
        this.balance = 10000; // Example starting balance
        this.selectedAsset = null; // e.g., "BTCUSDT"
        this.assetsData = {}; // To store data for all assets received from API

        console.log("ProTradeXApp: Initializing with selectors:", uiSelectors);
        this.initDOMReferences();
        this.attachEventListeners();
    }

    initDOMReferences() {
        console.log("ProTradeXApp: Initializing DOM references.");
        this.elements.themeToggle = document.querySelector(this.uiSelectors.themeToggle);
        this.elements.balanceDisplay = document.querySelector(this.uiSelectors.balanceDisplay);
        this.elements.connectionIndicator = document.getElementById('connectionIndicator'); // Assuming ID
        this.elements.connectionText = document.getElementById('connectionText'); // Assuming ID
        this.elements.assetListContainer = document.querySelector(this.uiSelectors.assetListContainer);
        this.elements.tradeButton = document.querySelector(this.uiSelectors.tradeButton);
        this.elements.notificationArea = document.getElementById('notificationArea'); // Assuming ID
        this.elements.themeIcon = document.getElementById('themeIcon'); // Assuming ID for theme icon
        this.elements.themeText = document.getElementById('themeText'); // Assuming ID for theme text
        this.elements.rsiValue = document.getElementById('rsiValue');
        this.elements.macdValue = document.getElementById('macdValue');
        this.elements.smaValue = document.getElementById('smaValue');


        // Example for sections (if applicable)
        // this.elements.dashboardSection = document.getElementById('dashboardSection');
        // this.elements.tradeSection = document.getElementById('tradeSection');
        console.log("ProTradeXApp: DOM references initialized.", this.elements);
    }

    attachEventListeners() {
        console.log("ProTradeXApp: Attaching event listeners.");
        if (this.elements.themeToggle) {
            this.elements.themeToggle.addEventListener('click', () => this.toggleTheme());
        }
        if (this.elements.tradeButton) {
            this.elements.tradeButton.addEventListener('click', () => this.handleTradeExecution());
        }
        // Add other listeners, e.g., for asset selection from a list
        if (this.elements.assetListContainer) {
            this.elements.assetListContainer.addEventListener('click', (event) => {
                const assetItem = event.target.closest('[data-symbol]');
                if (assetItem && assetItem.dataset.symbol) {
                    this.selectAsset(assetItem.dataset.symbol);
                }
            });
        }
    }

    init() {
        console.log("ProTradeXApp: init() called.");
        this.setupTheme();
        this.updateBalanceDisplay(); // Display initial balance
        this.setupAPI(); // Initialize and connect API
        this.navigateTo(this.currentSection); // Navigate to initial section
        this.showNotification("مرحباً بك في منصة التداول!", "info");
    }

    setupTheme() {
        document.body.className = this.currentTheme + '-theme';
        this.updateThemeButton(); // Call new method to update button state
        console.log(`ProTradeXApp: Theme set to ${this.currentTheme}.`);
    }

    toggleTheme() {
        this.currentTheme = this.currentTheme === 'light' ? 'dark' : 'light';
        localStorage.setItem('theme', this.currentTheme);
        this.setupTheme(); // This will call updateThemeButton
        console.log(`ProTradeXApp: Theme toggled to ${this.currentTheme}.`);
    }

    // Helper function to update DOM element text content
    _updateElementText(elementId, text) {
        // First, try to get from cached elements
        let element = this.elements[elementId];
        if (!element) { // If not cached, try to find it by ID (assuming elementId is actual ID)
            element = document.getElementById(elementId);
            if (element) this.elements[elementId] = element; // Cache it
        }

        if (element) {
            element.textContent = text;
        } else {
            // Allow graceful failure if element is optional (e.g. rsiValue might not be on all pages)
            // console.warn(`Element with ID '${elementId}' not found for text update.`);
        }
    }

    updateThemeButton() {
        // const themeIcon = document.getElementById('themeIcon'); // Now using this.elements.themeIcon
        // const themeTextEl = document.getElementById('themeText'); // Now using this.elements.themeText

        // Ensure elements are cached if not already
        if (!this.elements.themeIcon && this.uiSelectors.themeIcon) this.elements.themeIcon = document.querySelector(this.uiSelectors.themeIcon);
        if (!this.elements.themeText && this.uiSelectors.themeText) this.elements.themeText = document.querySelector(this.uiSelectors.themeText);


        if (this.currentTheme === 'dark') {
            if (this.elements.themeIcon) this.elements.themeIcon.textContent = '🌙';
            this._updateElementText('themeText', 'المظهر الليلي');
        } else {
            if (this.elements.themeIcon) this.elements.themeIcon.textContent = '☀️';
            this._updateElementText('themeText', 'المظهر النهاري');
        }
    }

    updateTechnicalIndicators() {
        const rsi = (Math.random() * 40 + 30).toFixed(1); // Example RSI value
        this._updateElementText('rsiValue', rsi);

        const macd = ((Math.random() - 0.5) * 50).toFixed(1); // Example MACD value
        this._updateElementText('macdValue', macd > 0 ? `+${macd}` : macd);

        const sma = (2000 + Math.random() * 100).toFixed(1); // Example SMA value
        this._updateElementText('smaValue', sma);

        // Periodically update indicators for demo purposes
        // In a real app, this would be driven by actual data updates.
        // setTimeout(() => this.updateTechnicalIndicators(), 5000); // Update every 5s
    }


    setupAPI() {
        console.log("ProTradeXApp: Setting up API.");
        // Assuming TradingAPISystem is available globally or imported
        // For this example, the symbolsConfig is hardcoded for simplicity
        const symbolsConfig = {
            BTCUSDT: { name: "Bitcoin", fiat: "USD", logo: "btc.png" },
            ETHUSDT: { name: "Ethereum", fiat: "USD", logo: "eth.png" },
            ADAUSDT: { name: "Cardano", fiat: "USD", logo: "ada.png" }
        };
        this.apiSystem = new TradingAPISystem("YOUR_API_KEY", symbolsConfig); // Replace with actual API key if needed

        // Modified to handle connectionStatus as the second argument
        this.apiSystem.onUpdate((data, connectionStatus) => {
            if (data) { // If data is not null, it's a symbol update
                if (data.type === 'all_symbols') {
                     this.updateAssetsDisplay(data.payload);
                } else if (data.type === 'symbol_update') {
                     this.updateSingleAssetDisplay(data.payload);
                }
            }

            // Handle connection status
            if (connectionStatus) {
                this.isApiConnected = connectionStatus.connected; // Update internal state
                const indicator = this.elements.connectionIndicator; // Use stored element
                const textEl = this.elements.connectionText;     // Use stored element

                if (indicator && textEl) {
                    indicator.classList.remove('connected', 'disconnected', 'reconnecting'); // Clear previous states

                    if (connectionStatus.connected) {
                        indicator.classList.add('connected');
                        textEl.textContent = 'متصل';
                        // Optional: success notification on first connect or reconnect
                        // if (this.lastConnectionState !== true && connectionStatus.connected) {
                        //     this.showNotification('تم الاتصال بخدمة البيانات المباشرة بنجاح!', 'success', 3000);
                        // }
                    } else { // Disconnected states
                        indicator.classList.add('disconnected');
                        textEl.textContent = connectionStatus.message || 'غير متصل'; // Use message from API if available

                        if (connectionStatus.reconnectAttempts > 0 && connectionStatus.reconnectAttempts < connectionStatus.maxAttempts) {
                            indicator.classList.add('reconnecting');
                            this.showNotification(`انقطع الاتصال. محاولة إعادة الاتصال (${connectionStatus.reconnectAttempts})...`, 'warning', 5000);
                        } else if (connectionStatus.reconnectAttempts >= connectionStatus.maxAttempts) {
                             // textEl.textContent is already "Max reconnection attempts reached..." from api.js
                            this.showNotification('فشل الاتصال بخدمة البيانات بعد عدة محاولات. يتم عرض بيانات احتياطية.', 'error', 10000);
                        } else {
                            // Initial disconnected state or normal disconnect without active retries
                             if(this.isApiConnected === false && !connectionStatus.connected && connectionStatus.reconnectAttempts === 0){
                                // This condition means it's a deliberate disconnect or initial state, not a failed retry loop end.
                                // this.showNotification('تم قطع الاتصال بخدمة البيانات. يتم عرض بيانات احتياطية.', 'warning', 5000);
                             }
                        }
                    }
                }
                // this.lastConnectionState = connectionStatus.connected;
            }
        });

        // API connection attempt
        try {
            this.apiSystem.connectWebSocket();
            // Initial technical indicator update if elements exist
            this.updateTechnicalIndicators();
        } catch (error) {
            console.error("ProTradeXApp: Error setting up API connection.", error);
            // The onUpdate callback will handle connectionStatus object to update UI for error
            // this.showNotification("فشل الاتصال بخادم التداول.", "error"); // this is now handled by onUpdate
        }
    }

    updateAssetsDisplay(symbolsData) {
        console.log("ProTradeXApp: Updating assets display with data:", symbolsData);
        if (!this.elements.assetListContainer) {
            console.warn("ProTradeXApp: Asset list container not found.");
            return;
        }
        this.elements.assetListContainer.innerHTML = ''; // Clear existing assets
        this.assetsData = symbolsData; // Store the full dataset

        for (const symbol in symbolsData) {
            const asset = symbolsData[symbol];
            const assetDiv = document.createElement('div');
            assetDiv.className = 'asset-item';
            assetDiv.dataset.symbol = symbol;
            // Simple display, real app would use templates or more robust DOM creation
            const assetStatus = asset.status || 'pending'; // default to pending if status not set
            let statusClass = assetStatus; // Use status directly as class name
            let statusTitle = assetStatus.charAt(0).toUpperCase() + assetStatus.slice(1); // Capitalize

            // Customize title for clarity
            if (assetStatus === 'live') statusTitle = 'بيانات مباشرة';
            else if (assetStatus === 'simulated') statusTitle = 'بيانات محاكاة';
            else if (assetStatus === 'fallback') statusTitle = 'بيانات احتياطية';
            else if (assetStatus === 'disconnected') statusTitle = 'غير متصل';
            else if (assetStatus === 'pending') statusTitle = 'جاري التحميل...';


            assetDiv.innerHTML = `
                <div class="asset-status-dot ${statusClass}" title="${statusTitle}"></div>
                <img src="logos/${asset.logo}" alt="${asset.name}" class="asset-logo">
                <span class.asset-name">${asset.name} (${symbol})</span>
                <span class="asset-price">${asset.price ? asset.price.toFixed(2) : 'N/A'} ${asset.fiat}</span>
                <span class="asset-change ${asset.change >= 0 ? 'positive' : 'negative'}">${asset.change ? asset.change.toFixed(2) : '0.00'}%</span>
            `;
            this.elements.assetListContainer.appendChild(assetDiv);
        }
        // Removed: Redundant connection status update, now handled by connectionStatus object in onUpdate
    }

    updateSingleAssetDisplay(assetData) {
        const existingAssetData = this.assetsData[assetData.symbol];
        this.assetsData[assetData.symbol] = { ...existingAssetData, ...assetData };

        const assetElement = this.elements.assetListContainer.querySelector(`[data-symbol="${assetData.symbol}"]`);
        if (assetElement) {
            assetElement.querySelector('.asset-price').textContent = `${assetData.price ? assetData.price.toFixed(2) : 'N/A'} ${this.assetsData[assetData.symbol].fiat}`;
            const changeElement = assetElement.querySelector('.asset-change');
            changeElement.textContent = `${assetData.change ? assetData.change.toFixed(2) : '0.00'}%`;
            changeElement.className = `asset-change ${assetData.change >= 0 ? 'positive' : 'negative'}`;

            const statusDot = assetElement.querySelector('.asset-status-dot');
            if (statusDot) {
                statusDot.className = `asset-status-dot ${assetData.status || 'pending'}`;
                let statusTitle = (assetData.status || 'pending').charAt(0).toUpperCase() + (assetData.status || 'pending').slice(1);
                if (assetData.status === 'live') statusTitle = 'بيانات مباشرة';
                else if (assetData.status === 'simulated') statusTitle = 'بيانات محاكاة';
                else if (assetData.status === 'fallback') statusTitle = 'بيانات احتياطية';
                else if (assetData.status === 'disconnected') statusTitle = 'غير متصل';
                else if (assetData.status === 'pending') statusTitle = 'جاري التحميل...';
                statusDot.title = statusTitle;
            }
        } else {
            console.warn(`ProTradeXApp: Received update for asset not in display: ${assetData.symbol}`);
            // Optionally, create the asset card if it's a new symbol not present in initial full load
            // this.updateAssetsDisplay(this.assetsData); // Inefficient, better to add one card.
        }
        // Removed: Redundant connection status update
    }

    selectAsset(symbol) {
        if (typeof symbol !== 'string' || !symbol.trim()) {
            console.warn('⚠️ ProTradeXApp: Attempted to select an invalid symbol.');
            return;
        }
        if (!this.assetsData || !this.assetsData[symbol]) {
             console.warn(`⚠️ ProTradeXApp: Attempted to select non-existent asset: ${symbol}`);
             this.showNotification(`الأصل ${symbol} غير متوفر حالياً.`, 'warning');
             return;
        }

        this.selectedAsset = symbol;
        console.log(`ProTradeXApp: Asset selected: ${symbol}`);

        // Update visual state for selection
        if (this.elements.assetListContainer) {
            this.elements.assetListContainer.querySelectorAll('.asset-item').forEach(item => {
                item.classList.remove('active');
            });
            const selectedElement = this.elements.assetListContainer.querySelector(`[data-symbol="${symbol}"]`);
            if (selectedElement) {
                selectedElement.classList.add('active');
            }
        }
        this.showNotification(`تم اختيار ${this.assetsData[symbol].name للتداول.`, 'info');
    }

    executeTrade(symbol, type, amount) { // Added amount for more realism
        if (typeof symbol !== 'string' || !symbol.trim()) {
            console.error('❌ ProTradeXApp: Trade execution error - Invalid symbol.');
            this.showNotification('خطأ: رمز الأصل غير صالح.', 'error');
            return;
        }
        if (type !== 'buy' && type !== 'sell') {
            console.error(`❌ ProTradeXApp: Trade execution error for ${symbol} - Invalid operation type (${type}).`);
            this.showNotification(`خطأ: نوع العملية (${type}) غير صالح.`, 'error');
            return;
        }
        if (typeof amount !== 'number' || amount <= 0) {
            console.error(`❌ ProTradeXApp: Trade execution error for ${symbol} - Invalid amount (${amount}).`);
            this.showNotification('خطأ: الكمية غير صالحة.', 'error');
            return;
        }

        const asset = this.assetsData[symbol];
        if (!asset || !asset.price) {
            console.error(`❌ ProTradeXApp: Cannot trade ${symbol} - price data unavailable.`);
            this.showNotification(`لا يمكن تداول ${symbol}، بيانات السعر غير متوفرة.`, 'error');
            return;
        }

        const cost = asset.price * amount;
        if (type === 'buy' && this.balance < cost) {
            console.warn(`⚠️ ProTradeXApp: Insufficient balance to buy ${amount} of ${symbol}.`);
            this.showNotification('رصيدك غير كافٍ لإتمام هذه الصفقة.', 'warning');
            return;
        }

        console.log(`ProTradeXApp: Executing ${type} trade for ${amount} of ${symbol} at price ${asset.price}. Cost: ${cost}`);
        // Simulate API call for trade
        // this.apiSystem.executeTrade(symbol, type, amount, asset.price) ...

        if (type === 'buy') {
            this.balance -= cost;
        } else { // sell
            this.balance += cost;
        }
        this.updateBalanceDisplay();
        this.showNotification(`تم ${type === 'buy' ? 'شراء' : 'بيع'} ${amount} ${asset.name} بنجاح.`, 'success');
    }

    updateBalanceDisplay() {
        if (this.elements.balanceDisplay) {
            this.elements.balanceDisplay.textContent = `${this.balance.toFixed(2)} USD`; // Assuming USD
        }
        console.log(`ProTradeXApp: Balance updated to ${this.balance}.`);
    }

    handleTradeExecution() {
        if (!this.selectedAsset) {
            this.showNotification("الرجاء اختيار أصل أولاً لتنفيذ صفقة.", "warning");
            return;
        }
        // For simplicity, hardcoding 'buy' and amount 1.
        // A real app would get these from input fields.
        const tradeType = 'buy';
        const tradeAmount = 1;
        this.executeTrade(this.selectedAsset, tradeType, tradeAmount);
    }

    navigateTo(sectionId) {
        this.currentSection = sectionId;
        // Logic to show/hide sections based on sectionId
        // e.g., document.querySelectorAll('.app-section').forEach(s => s.style.display = 'none');
        // document.getElementById(sectionId).style.display = 'block';
        console.log(`ProTradeXApp: Navigated to section: ${sectionId}.`);
    }

    showNotification(message, type = 'info', isPersistent = false) {
        if (!this.elements.notificationArea) {
            console.warn("ProTradeXApp: Notification area not found. Message:", message);
            alert(message); // Fallback
            return;
        }
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;
        this.elements.notificationArea.appendChild(notification);
        if (!isPersistent) {
            setTimeout(() => notification.remove(), 3000);
        }
    }
}

// Example initialization if this script is loaded directly and TradingAPISystem is available:
// This would typically be done in the main HTML file or a master script.
/*
document.addEventListener('DOMContentLoaded', () => {
    const uiSelectors = {
        themeToggle: '#themeToggle',
        balanceDisplay: '#balanceAmount',
        assetListContainer: '#assetList',
        tradeButton: '#executeTradeBtn',
        // ... other selectors
    };
    const app = new ProTradeXApp(uiSelectors);
    app.init(); // Initialize the app (setup theme, API, etc.)

    // Make app instance global for easy debugging if needed
    window.proTradeXApp = app;
});
*/

if (typeof window !== 'undefined') {
    window.ProTradeXApp = ProTradeXApp;
}
