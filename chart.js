class TradingChart {
    constructor(containerId, symbol, settings = {}) {
        this.container = document.getElementById(containerId);
        this.symbol = symbol; // e.g., BTCUSDT
        this.settings = {
            width: 800,
            height: 400,
            backgroundColor: '#1E1E1E', // Dark theme
            gridColor: '#444',
            textColor: '#CCC',
            priceUpColor: '#00B16A', // Green
            priceDownColor: '#CF000F', // Red
            font: '12px Arial',
            tooltipBackgroundColor: 'rgba(50, 50, 50, 0.8)',
            tooltipTextColor: '#FFF',
            padding: { top: 20, right: 50, bottom: 40, left: 50 },
            maxDataPoints: 100, // Max data points to display
            ...settings
        };
        this.initialSettings = { ...this.settings }; // For responsive resizing

        this.canvas = null;
        this.ctx = null;
        this.data = []; // Stores { timestamp, price }
        this.lastMouseX = null; // For tooltip and crosshair
        this.animationFrameId = null;
        this.simulationIntervalId = null; // For simulating new data

        if (!this.container) {
            console.error(`TradingChart: Container with ID '${containerId}' not found.`);
            return;
        }

        this.init();
    }

    init() {
        this.canvas = document.createElement('canvas');
        this.canvas.width = this.settings.width;
        this.canvas.height = this.settings.height;
        this.container.innerHTML = ''; // Clear container
        this.container.appendChild(this.canvas);
        this.ctx = this.canvas.getContext('2d');

        this.generateInitialData(); // Generate some dummy data to start
        this.attachEventListeners();
        this.startAnimation(); // Start the drawing loop
        // this.startSimulation(); // Optionally start data simulation

        console.log(`TradingChart for ${this.symbol} initialized.`);
    }

    attachEventListeners() {
        this.canvas.addEventListener('mousemove', (e) => this.handleMouseMove(e));
        this.canvas.addEventListener('mouseleave', () => this.handleMouseLeave());

        // Store the bound function for correct removal
        this.boundUpdateCanvasSize = () => this.updateCanvasSize();
        window.addEventListener('resize', this.boundUpdateCanvasSize);
        this.updateCanvasSize(); // Initial size adjustment
    }

    generateInitialData() {
        const now = Date.now();
        let price = 50000 + Math.random() * 1000; // Initial base price
        for (let i = 0; i < 50; i++) { // Generate 50 initial data points
            price += (Math.random() - 0.5) * 500;
            this.data.push({ timestamp: now - (50 - i) * 60000, price: price }); // Data every minute
        }
    }

    addDataPoint(price, timestamp = Date.now()) {
        if (typeof price !== 'number' || isNaN(price)) {
            console.warn(`⚠️ TradingChart: Invalid price data point: ${price}. Skipping.`);
            return;
        }
        this.data.push({ timestamp, price });
        if (this.data.length > this.settings.maxDataPoints) {
            this.data.shift(); // Keep data array size limited
        }
        // No direct call to draw() here; requestAnimationFrame loop handles drawing
    }

    simulateNewData() {
        if (this.data.length === 0) return; // Should not happen if initial data is generated
        const lastPrice = this.data[this.data.length - 1].price;
        let newPrice = lastPrice + (Math.random() - 0.5) * (lastPrice * 0.005); // Simulate small % change
        if (newPrice <= 0) newPrice = lastPrice * 0.5; // Prevent negative or zero price in simulation

        if (isNaN(newPrice)) {
            console.warn(`⚠️ TradingChart: Simulated newPrice is NaN for symbol ${this.symbol}. Skipping.`);
            return;
        }
        this.addDataPoint(newPrice);
    }

    startSimulation() {
        if (this.simulationIntervalId) clearInterval(this.simulationIntervalId);
        this.simulationIntervalId = setInterval(() => this.simulateNewData(), 2000); // New data every 2s
        console.log(`TradingChart: Data simulation started for ${this.symbol}.`);
    }

    stopSimulation() {
        if (this.simulationIntervalId) clearInterval(this.simulationIntervalId);
        this.simulationIntervalId = null;
        console.log(`TradingChart: Data simulation stopped for ${this.symbol}.`);
    }

    startAnimation() {
        if (!this.animationFrameId) {
            this.animationFrameId = requestAnimationFrame(() => this.drawLoop());
        }
    }

    stopAnimation() {
        if (this.animationFrameId) {
            cancelAnimationFrame(this.animationFrameId);
            this.animationFrameId = null;
        }
    }

    drawLoop() {
        this.draw();
        this.animationFrameId = requestAnimationFrame(() => this.drawLoop());
    }

    draw() {
        if (!this.ctx || !this.canvas || this.data.length === 0) {
            // console.warn("TradingChart: Canvas context not available or no data to draw.");
            return;
        }
        this.ctx.clearRect(0, 0, this.settings.width, this.settings.height);
        this.ctx.fillStyle = this.settings.backgroundColor;
        this.ctx.fillRect(0, 0, this.settings.width, this.settings.height);

        this.drawGrid();
        this.drawAxes();
        this.drawChart();
        if (this.lastMouseX !== null) {
            this.drawCrosshair(this.lastMouseX);
            const dataIndex = this.getDataIndexFromX(this.lastMouseX);
            if (dataIndex !== -1) {
                this.drawTooltip(this.data[dataIndex], this.lastMouseX);
            }
        }
        this.drawInfo(); // Draw symbol name, current price etc.
    }

    drawGrid() {
        this.ctx.strokeStyle = this.settings.gridColor;
        this.ctx.lineWidth = 0.5;
        // Vertical lines
        for (let i = 0; i < 10; i++) {
            const x = this.settings.padding.left + i * (this.settings.width - this.settings.padding.left - this.settings.padding.right) / 10;
            this.ctx.beginPath();
            this.ctx.moveTo(x, this.settings.padding.top);
            this.ctx.lineTo(x, this.settings.height - this.settings.padding.bottom);
            this.ctx.stroke();
        }
        // Horizontal lines
        for (let i = 0; i < 8; i++) {
            const y = this.settings.padding.top + i * (this.settings.height - this.settings.padding.top - this.settings.padding.bottom) / 8;
            this.ctx.beginPath();
            this.ctx.moveTo(this.settings.padding.left, y);
            this.ctx.lineTo(this.settings.width - this.settings.padding.right, y);
            this.ctx.stroke();
        }
    }

    drawAxes() {
        this.ctx.strokeStyle = this.settings.textColor;
        this.ctx.fillStyle = this.settings.textColor;
        this.ctx.font = this.settings.font;
        this.ctx.lineWidth = 1;

        // Y-axis (Price)
        const priceMin = Math.min(...this.data.map(d => d.price));
        const priceMax = Math.max(...this.data.map(d => d.price));
        const priceRange = priceMax - priceMin || 1; // Avoid division by zero

        for (let i = 0; i <= 5; i++) {
            const price = priceMin + (priceRange / 5) * i;
            const y = this.settings.height - this.settings.padding.bottom - (price - priceMin) / priceRange * (this.settings.height - this.settings.padding.top - this.settings.padding.bottom);
            this.ctx.fillText(price.toFixed(2), this.settings.width - this.settings.padding.right + 5, y + 4);
        }

        // X-axis (Time)
        const timeRange = this.data[this.data.length - 1].timestamp - this.data[0].timestamp || 1;
        for (let i = 0; i <= 5; i++) {
            const timestamp = this.data[0].timestamp + (timeRange / 5) * i;
            const date = new Date(timestamp);
            const timeStr = `${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;
            const x = this.settings.padding.left + (timestamp - this.data[0].timestamp) / timeRange * (this.settings.width - this.settings.padding.left - this.settings.padding.right);
            this.ctx.fillText(timeStr, x - 15, this.settings.height - this.settings.padding.bottom + 15);
        }
    }

    drawChart() {
        if (this.data.length < 2) return;

        this.ctx.beginPath();
        const priceMin = Math.min(...this.data.map(d => d.price));
        const priceMax = Math.max(...this.data.map(d => d.price));
        const priceRange = priceMax - priceMin || 1;
        const timeRange = this.data[this.data.length - 1].timestamp - this.data[0].timestamp || 1;

        const firstPrice = this.data[0].price;
        const lastPrice = this.data[this.data.length - 1].price;
        this.ctx.strokeStyle = lastPrice >= firstPrice ? this.settings.priceUpColor : this.settings.priceDownColor;
        this.ctx.lineWidth = 1.5;

        this.data.forEach((point, index) => {
            const x = this.settings.padding.left + (point.timestamp - this.data[0].timestamp) / timeRange * (this.settings.width - this.settings.padding.left - this.settings.padding.right);
            const y = this.settings.height - this.settings.padding.bottom - (point.price - priceMin) / priceRange * (this.settings.height - this.settings.padding.top - this.settings.padding.bottom);
            if (index === 0) {
                this.ctx.moveTo(x, y);
            } else {
                this.ctx.lineTo(x, y);
            }
        });
        this.ctx.stroke();
    }

    drawInfo() {
        this.ctx.fillStyle = this.settings.textColor;
        this.ctx.font = `bold ${this.settings.font}`;
        this.ctx.fillText(this.symbol, this.settings.padding.left + 10, this.settings.padding.top + 10);
        if (this.data.length > 0) {
            const currentPrice = this.data[this.data.length - 1].price;
            this.ctx.fillText(`Price: ${currentPrice.toFixed(2)}`, this.settings.padding.left + 10, this.settings.padding.top + 30);
        }
    }

    drawCrosshair(mouseX) {
        this.ctx.strokeStyle = this.settings.textColor;
        this.ctx.lineWidth = 0.5;
        this.ctx.setLineDash([5, 5]); // Dashed line

        // Vertical line
        this.ctx.beginPath();
        this.ctx.moveTo(mouseX, this.settings.padding.top);
        this.ctx.lineTo(mouseX, this.settings.height - this.settings.padding.bottom);
        this.ctx.stroke();

        this.ctx.setLineDash([]); // Reset line dash
    }

    drawTooltip(dataPoint, mouseX) {
        if (!dataPoint) return;
        const price = dataPoint.price.toFixed(2);
        const date = new Date(dataPoint.timestamp);
        const timeStr = `${date.toLocaleDateString()} ${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;
        const text = `${this.symbol} | Price: ${price} | Time: ${timeStr}`;

        this.ctx.font = this.settings.font;
        const textWidth = this.ctx.measureText(text).width;
        const tooltipWidth = textWidth + 20;
        const tooltipHeight = 30; // Single line tooltip

        let tooltipX = mouseX + 15;
        let tooltipY = this.settings.padding.top + 10; // Position tooltip at top

        // Prevent tooltip from rendering off-screen (simple adjustment)
        if (tooltipX + tooltipWidth > this.settings.width - this.settings.padding.right) {
            tooltipX = mouseX - tooltipWidth - 15; // Position to the left of cursor
        }
        if (tooltipX < this.settings.padding.left) {
             tooltipX = this.settings.padding.left;
        }
        if (tooltipY + tooltipHeight > this.settings.height - this.settings.padding.bottom) {
            tooltipY = this.settings.height - this.settings.padding.bottom - tooltipHeight;
        }
         if (tooltipY < this.settings.padding.top) {
            tooltipY = this.settings.padding.top;
        }


        this.ctx.fillStyle = this.settings.tooltipBackgroundColor;
        this.ctx.fillRect(tooltipX, tooltipY, tooltipWidth, tooltipHeight);

        this.ctx.fillStyle = this.settings.tooltipTextColor;
        this.ctx.fillText(text, tooltipX + 10, tooltipY + tooltipHeight / 2 + 5);
    }

    getDataIndexFromX(mouseX) {
        if (this.data.length === 0) return -1;
        const chartAreaWidth = this.settings.width - this.settings.padding.left - this.settings.padding.right;
        const timeRange = this.data[this.data.length - 1].timestamp - this.data[0].timestamp || 1;

        // Calculate the timestamp corresponding to mouseX
        const relativeX = mouseX - this.settings.padding.left;
        const timestampAtMouse = this.data[0].timestamp + (relativeX / chartAreaWidth) * timeRange;

        // Find the closest data point by timestamp
        let closestIndex = -1;
        let smallestDiff = Infinity;
        this.data.forEach((point, index) => {
            const diff = Math.abs(point.timestamp - timestampAtMouse);
            if (diff < smallestDiff) {
                smallestDiff = diff;
                closestIndex = index;
            }
        });
        return closestIndex;
    }

    handleMouseMove(event) {
        const rect = this.canvas.getBoundingClientRect();
        const x = event.clientX - rect.left;
        // const y = event.clientY - rect.top; // Y not used for crosshair logic currently

        if (x >= this.settings.padding.left && x <= this.settings.width - this.settings.padding.right) {
            this.lastMouseX = x;
        } else {
            this.lastMouseX = null; // Mouse is outside chart drawing area (horizontally)
        }
        // No direct call to draw() here, animation loop handles it
    }

    handleMouseLeave() {
        this.lastMouseX = null;
        // No direct call to draw() here
    }

    updateCanvasSize() {
        if (!this.container || !this.canvas) return;
        const containerWidth = this.container.clientWidth;

        // Preserve aspect ratio from initial settings
        const aspectRatio = this.initialSettings.height / this.initialSettings.width;

        const newWidth = Math.max(containerWidth, 300); // Min width 300px
        const newHeight = newWidth * aspectRatio;

        // Update canvas internal (drawing surface) dimensions
        this.canvas.width = newWidth;
        this.canvas.height = newHeight;

        // Update settings used by drawing functions
        this.settings.width = newWidth;
        this.settings.height = newHeight;

        // CSS dimensions (optional if canvas width/height are directly set)
        // this.canvas.style.width = newWidth + 'px'; // Or '100%'
        // this.canvas.style.height = newHeight + 'px';
        // this.draw(); // Redraw is handled by the animation loop
    }

    destroy() {
        this.stopAnimation();
        this.stopSimulation();
        if (this.canvas) this.canvas.remove();
        window.removeEventListener('resize', this.boundUpdateCanvasSize); // Use stored reference
        console.log(`TradingChart for ${this.symbol} destroyed.`);
    }
}

// Ensure the class is globally accessible for app.js
if (typeof window !== 'undefined') {
    window.TradingChart = TradingChart;
}
