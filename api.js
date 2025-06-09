class TradingAPISystem {
    constructor(apiKey, symbolsConfig) {
        this.apiKey = apiKey;
        this.symbolsConfig = symbolsConfig;
        this.symbols = {};
        this.subscribers = []; // Changed from updateCallbacks to subscribers
        this.websocket = null;
        this.websocketUrl = 'wss://stream.binance.com:9443/ws';
        this.simulationInterval = null;
        this.fallbackData = {
            BTCUSDT: { price: 48000, change: -1.5, name: "Bitcoin", fiat: "USD", status: "fallback" },
            ETHUSDT: { price: 3200, change: 0.5, name: "Ethereum", fiat: "USD", status: "fallback" }
        };

        this.isConnected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5; // Max 5 attempts
        this.reconnectDelay = 5000; // 5 seconds

        this.initializeSymbols();
        console.log("TradingAPISystem initialized.");
    }

    // Helper method to update symbol data consistently
    _updateSymbolData(symbol, price, change, status, priceDirection = null, lastUpdate = Date.now()) {
        if (!this.symbols[symbol]) {
            console.warn(`⚠️ Attempted to update non-existent symbol: ${symbol}`);
            return false;
        }
        if (typeof price !== 'number' || isNaN(price)) {
            console.warn(`⚠️ Invalid price for symbol ${symbol} in _updateSymbolData: ${price}`);
            return false;
        }
        // Change can be 0, so checking for undefined or non-number for stricter validation
        if (typeof change === 'undefined' || typeof change !== 'number' || isNaN(change)) {
            console.warn(`⚠️ Invalid change for symbol ${symbol} in _updateSymbolData: ${change}`);
            return false;
        }

        const oldPrice = this.symbols[symbol].price;
        this.symbols[symbol].price = price;
        this.symbols[symbol].change = change; // This is often price change percentage
        this.symbols[symbol].status = status;
        this.symbols[symbol].lastUpdate = lastUpdate;

        if (priceDirection) {
            this.symbols[symbol].priceDirection = priceDirection;
        } else if (oldPrice !== 0 && price !== oldPrice && oldPrice !== price) { // Ensure actual change
            this.symbols[symbol].priceDirection = price > oldPrice ? 'up' : 'down';
        } else if (oldPrice === 0 && price !== 0) {
             this.symbols[symbol].priceDirection = 'up'; // Default if starting from 0
        }

        // this.addToPriceHistory(symbol, price); // Placeholder for price history logic
        return true;
    }

    initializeSymbols() {
        for (const symbol in this.symbolsConfig) {
            this.symbols[symbol] = {
                price: 0,
                change: 0, // Typically percentage change
                fiat: this.symbolsConfig[symbol].fiat,
                name: this.symbolsConfig[symbol].name,
                lastUpdate: Date.now(),
                status: "pending", // Initial status
                priceDirection: "neutral" // up, down, neutral
                // priceHistory: [] // Could be initialized here if addToPriceHistory is used
            };
        }
    }

    // Renamed from subscribe to onUpdate to match prompt's usage in app.js context
    onUpdate(callback) {
        this.subscribers.push(callback);
    }

    // Notify subscribers with symbol data
    notifySymbolUpdate(symbolKey) {
        const symbolData = { ...this.symbols[symbolKey], symbol: symbolKey, status: this.isConnected ? 'live' : this.symbols[symbolKey].status };
        this.subscribers.forEach(callback => {
            try {
                // Pass symbol data object and current connection status
                callback({ type: 'symbol_update', payload: symbolData }, this.getConnectionStatus());
            } catch (error) {
                console.error('❌ خطأ في callback تحديث الرمز:', error);
            }
        });
    }

    // Notify subscribers with all symbols (e.g., after fallback or initial load)
    notifyAllSymbolsUpdate() {
        const allSymbolsPayload = {};
        for (const symbol in this.symbols) {
            allSymbolsPayload[symbol] = { ...this.symbols[symbol], status: this.isConnected ? 'live' : this.symbols[symbol].status };
        }
         this.subscribers.forEach(callback => {
            try {
                callback({ type: 'all_symbols', payload: allSymbolsPayload }, this.getConnectionStatus());
            } catch (error) {
                console.error('❌ خطأ في callback تحديث كل الرموز:', error);
            }
        });
    }


    // Notify subscribers specifically about connection status changes
    notifyStatusUpdate() {
        const status = this.getConnectionStatus();
        console.log(`TradingAPISystem: Notifying status update - Connected: ${status.connected}, Attempts: ${status.reconnectAttempts}, Message: ${status.message}`);
        this.subscribers.forEach(callback => {
            try {
                // Pass null for symbols if it's purely a status update, or current symbols
                callback(null, status); // Or callback({type: 'status_update', payload: status}, status)
            } catch (error) {
                console.error('❌ خطأ في callback تحديث الحالة:', error);
            }
        });
    }

    getConnectionStatus() {
        let message = this.isConnected ? "Connected" : "Disconnected";
        if (this.reconnectAttempts > 0 && this.reconnectAttempts < this.maxReconnectAttempts && !this.isConnected) {
            message = `Reconnecting (attempt ${this.reconnectAttempts})...`;
        } else if (this.reconnectAttempts >= this.maxReconnectAttempts && !this.isConnected) {
            message = "Max reconnection attempts reached. Using fallback data.";
        }
        return {
            connected: this.isConnected,
            reconnectAttempts: this.reconnectAttempts,
            maxAttempts: this.maxReconnectAttempts,
            message: message
        };
    }

    connectWebSocket() {
        if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
            console.log("WebSocket already open.");
            return;
        }
        if (!this.symbolsConfig || Object.keys(this.symbolsConfig).length === 0) {
            console.warn("⚠️ No symbols configured for WebSocket. Using fallback data simulation.");
            this.loadFallbackData(); // This will call notifyAllSymbolsUpdate
            this.startPriceSimulation(); // Uses its own notify
            this.isConnected = false; // Explicitly not connected via WebSocket
            this.notifyStatusUpdate();
            return;
        }

        const streams = Object.keys(this.symbolsConfig).map(s => `${s.toLowerCase()}@ticker`).join('/');
        this.websocket = new WebSocket(`${this.websocketUrl}/${streams}`);
        console.log("Attempting to connect to WebSocket...");
        // No explicit "connecting" status sent here, relies on onclose/onerror/onopen to dictate state.

        this.websocket.onopen = () => {
            console.log('📊 WebSocket connection established for Binance.');
            this.isConnected = true;
            this.reconnectAttempts = 0;
            // Update status for all symbols to 'live'
            for (const symbol in this.symbols) this.symbols[symbol].status = 'live';
            this.notifyStatusUpdate(); // Notify connection is truly open
            // Potentially notify all symbols once connected if needed, or let individual updates flow
            this.notifyAllSymbolsUpdate();
        };

        this.websocket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.processBinanceData(data); // This will call notifySymbolUpdate
        };

        this.websocket.onerror = (error) => {
            console.error('❌ WebSocket error:', error);
            this.isConnected = false;
            // Do not call notifyStatusUpdate() here directly, onclose will handle it.
            // If onclose doesn't always fire after onerror, then call it:
            // this.notifyStatusUpdate();
            // this.scheduleReconnection(); // onclose will also schedule.
        };

        this.websocket.onclose = () => {
            console.log('🔌 WebSocket connection closed.');
            const wasConnected = this.isConnected;
            this.isConnected = false;
            // Update status for all symbols
            for (const symbol in this.symbols) {
                if (this.symbols[symbol].status === 'live') { // If it was live, now it's not
                    this.symbols[symbol].status = 'disconnected'; // Or some other status indicating data is stale
                }
            }
            this.notifyStatusUpdate(); // Notify about disconnection

            if (wasConnected || this.reconnectAttempts < this.maxReconnectAttempts) {
                 this.scheduleReconnection();
            } else {
                console.log("Max reconnection attempts reached or was not previously connected, not attempting further reconnections.");
                this.loadFallbackData(); // Ensure fallback is loaded if all reconnections failed
                this.startPriceSimulation();
            }
        };
    }

    scheduleReconnection() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            console.log(`Scheduling reconnection attempt ${this.reconnectAttempts} in ${this.reconnectDelay / 1000}s.`);
            this.notifyStatusUpdate(); // Notify that a reconnection attempt is scheduled

            setTimeout(() => {
                console.log(`Attempting reconnection ${this.reconnectAttempts}...`);
                this.connectWebSocket();
            }, this.reconnectDelay);
        } else {
            console.log("Max reconnection attempts reached. Not scheduling further reconnections.");
            this.notifyStatusUpdate(); // Final status update
            this.loadFallbackData();
            this.startPriceSimulation();
        }
    }


    processBinanceData(data) {
        if (!data || typeof data !== 'object') {
            console.warn('⚠️ بيانات Binance غير صالحة: البيانات مفقودة أو ليست كائنًا');
            return;
        }
        const symbol = data.s;
        if (typeof symbol !== 'string' || !symbol || !this.symbols[symbol]) {
            // console.warn(`⚠️ رمز Binance غير صالح أو غير مهيأ: ${symbol}`);
            return;
        }

        const newPriceStr = data.c;
        const changePercentStr = data.P; // This is typically 24h change %
        if (typeof newPriceStr === 'undefined' || typeof changePercentStr === 'undefined') {
            console.warn(`⚠️ بيانات Binance غير صالحة لـ ${symbol}: السعر أو نسبة التغيير مفقودة.`);
            return;
        }
        const newPrice = parseFloat(newPriceStr);
        const changePercent = parseFloat(changePercentStr); // Use this as the 'change' value

        if (this._updateSymbolData(symbol, newPrice, changePercent, 'live')) {
            this.notifySymbolUpdate(symbol);
        }
    }

    loadFallbackData() {
        console.log("📉 Loading fallback data.");
        let updatedAnySymbol = false;
        for (const symbol in this.fallbackData) {
            if (this.symbols[symbol]) { // Check if the symbol is configured in the main symbols object
                const fallbackPrice = this.fallbackData[symbol].price;
                const fallbackChange = this.fallbackData[symbol].change; // This is a direct change value for fallback

                if (this._updateSymbolData(symbol, fallbackPrice, fallbackChange, 'fallback')) {
                    updatedAnySymbol = true;
                }
            }
        }
        if(updatedAnySymbol) this.notifyAllSymbolsUpdate(); // Notify once after all fallbacks are processed
    }

    startPriceSimulation() {
        if (this.simulationInterval) clearInterval(this.simulationInterval);
        console.log("⏳ Starting price simulation for symbols.");

        this.simulationInterval = setInterval(() => {
            let updatedAnySymbol = false;
            for (const symbol in this.symbols) {
                if (!this.symbols[symbol] || this.symbols[symbol].status === 'live') continue;

                let currentPrice = this.symbols[symbol].price;
                if (typeof currentPrice !== 'number' || isNaN(currentPrice) || currentPrice === 0) {
                    currentPrice = this.fallbackData[symbol] ? this.fallbackData[symbol].price : 1; // Start from fallback or 1
                }

                const volatility = (Math.random() - 0.5) * 0.01; // Small % change for the tick
                const newPrice = currentPrice * (1 + volatility);
                const calculatedChangePercent = volatility * 100; // Change for this tick

                // The priceDirection will be determined by _updateSymbolData based on price change from oldPrice
                if (this._updateSymbolData(symbol, newPrice, calculatedChangePercent, 'simulated')) {
                    updatedAnySymbol = true;
                }
            }
            if(updatedAnySymbol) this.notifyAllSymbolsUpdate(); // Notify once per simulation interval for all simulated symbols
        }, 2000);
    }

    disconnectWebSocket() {
        if (this.simulationInterval) clearInterval(this.simulationInterval);
        this.simulationInterval = null;
        if (this.websocket) {
            this.websocket.close(); // This will trigger onclose, then notifyStatusUpdate and fallback logic.
        } else {
            this.isConnected = false;
            this.notifyStatusUpdate();
        }
        console.log("🛑 WebSocket disconnected and simulation stopped.");
    }
}

if (typeof window !== 'undefined') {
    window.TradingAPISystem = TradingAPISystem;
}
