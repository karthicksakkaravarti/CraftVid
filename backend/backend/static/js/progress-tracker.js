/**
 * ProgressTracker - A module for tracking real-time progress of batch operations
 * 
 * This module handles WebSocket connections to receive real-time updates on 
 * the progress of batch operations like image, voice, and video generation.
 */

class ProgressTracker {
    /**
     * Initialize the progress tracker
     * 
     * @param {string} workspaceId - The ID of the current workspace
     * @param {Object} options - Configuration options
     */
    constructor(workspaceId, options = {}) {
        this.workspaceId = workspaceId;
        this.options = {
            reconnectAttempts: 5,
            reconnectDelay: 3000,
            debug: false,
            ...options
        };
        
        this.socket = null;
        this.isConnected = false;
        this.reconnectCount = 0;
        this.taskHandlers = {};
        this.taskStatuses = {};
        
        // Bind methods
        this.connect = this.connect.bind(this);
        this.disconnect = this.disconnect.bind(this);
        this.reconnect = this.reconnect.bind(this);
        this.onMessage = this.onMessage.bind(this);
        this.onOpen = this.onOpen.bind(this);
        this.onClose = this.onClose.bind(this);
        this.onError = this.onError.bind(this);
        
        // Register for events
        this.eventListeners = {};
    }
    
    /**
     * Connect to the WebSocket server
     */
    connect() {
        if (this.socket && (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING)) {
            this.log('Already connected or connecting');
            return;
        }
        
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/progress/workspace/${this.workspaceId}/`;
        
        this.log(`Connecting to ${wsUrl}`);
        
        try {
            this.socket = new WebSocket(wsUrl);
            this.socket.onopen = this.onOpen;
            this.socket.onclose = this.onClose;
            this.socket.onerror = this.onError;
            this.socket.onmessage = this.onMessage;
        } catch (error) {
            this.log('Error creating WebSocket connection', error);
            this.reconnect();
        }
    }
    
    /**
     * Disconnect from the WebSocket server
     */
    disconnect() {
        if (this.socket) {
            this.socket.close();
            this.socket = null;
        }
        this.isConnected = false;
    }
    
    /**
     * Attempt to reconnect to the WebSocket server
     */
    reconnect() {
        if (this.reconnectCount >= this.options.reconnectAttempts) {
            this.log('Max reconnect attempts reached');
            this.emitEvent('maxReconnectAttemptsReached', {});
            return;
        }
        
        this.reconnectCount++;
        this.log(`Reconnecting... Attempt ${this.reconnectCount}`);
        
        setTimeout(() => {
            this.connect();
        }, this.options.reconnectDelay);
    }
    
    /**
     * Handle WebSocket open event
     */
    onOpen() {
        this.log('WebSocket connection established');
        this.isConnected = true;
        this.reconnectCount = 0;
        this.emitEvent('connected', {});
    }
    
    /**
     * Handle WebSocket close event
     * 
     * @param {Event} event - The close event
     */
    onClose(event) {
        this.log('WebSocket connection closed', event);
        this.isConnected = false;
        
        if (!event.wasClean) {
            this.reconnect();
        }
        
        this.emitEvent('disconnected', { event });
    }
    
    /**
     * Handle WebSocket error event
     * 
     * @param {Event} error - The error event
     */
    onError(error) {
        this.log('WebSocket error', error);
        this.emitEvent('error', { error });
    }
    
    /**
     * Handle WebSocket message event
     * 
     * @param {MessageEvent} event - The message event
     */
    onMessage(event) {
        try {
            const data = JSON.parse(event.data);
            this.log('Message received', data);
            
            // Store task status
            this.taskStatuses[data.task_id] = {
                task_type: data.task_type,
                status: data.status,
                progress: data.progress,
                message: data.message,
                entity_id: data.entity_id,
                timestamp: data.timestamp
            };
            
            // Call task-specific handlers
            if (data.entity_id && this.taskHandlers[data.entity_id]) {
                this.taskHandlers[data.entity_id](data);
            }
            
            // Emit event for this task type
            this.emitEvent(data.task_type, data);
            
            // Emit general progress event
            this.emitEvent('progress', data);
            
        } catch (error) {
            this.log('Error parsing message', error, event.data);
        }
    }
    
    /**
     * Register a handler for a specific entity
     * 
     * @param {string} entityId - The ID of the entity (screen, script, etc.)
     * @param {Function} handler - The handler function
     */
    registerTaskHandler(entityId, handler) {
        this.taskHandlers[entityId] = handler;
    }
    
    /**
     * Unregister a handler for a specific entity
     * 
     * @param {string} entityId - The ID of the entity
     */
    unregisterTaskHandler(entityId) {
        delete this.taskHandlers[entityId];
    }
    
    /**
     * Get the status of a task
     * 
     * @param {string} taskId - The ID of the task
     * @returns {Object|null} The task status or null if not found
     */
    getTaskStatus(taskId) {
        return this.taskStatuses[taskId] || null;
    }
    
    /**
     * Add an event listener
     * 
     * @param {string} event - The event name
     * @param {Function} callback - The callback function
     */
    addEventListener(event, callback) {
        if (!this.eventListeners[event]) {
            this.eventListeners[event] = [];
        }
        this.eventListeners[event].push(callback);
    }
    
    /**
     * Remove an event listener
     * 
     * @param {string} event - The event name
     * @param {Function} callback - The callback function
     */
    removeEventListener(event, callback) {
        if (!this.eventListeners[event]) {
            return;
        }
        this.eventListeners[event] = this.eventListeners[event].filter(cb => cb !== callback);
    }
    
    /**
     * Emit an event
     * 
     * @param {string} event - The event name
     * @param {Object} data - The event data
     */
    emitEvent(event, data) {
        if (!this.eventListeners[event]) {
            return;
        }
        this.eventListeners[event].forEach(callback => {
            try {
                callback(data);
            } catch (error) {
                this.log('Error in event listener', error);
            }
        });
    }
    
    /**
     * Log a message if debug is enabled
     * 
     * @param {...any} args - The arguments to log
     */
    log(...args) {
        if (this.options.debug) {
            console.log('[ProgressTracker]', ...args);
        }
    }
}

// Export the ProgressTracker class if using ES modules
if (typeof module !== 'undefined' && typeof module.exports !== 'undefined') {
    module.exports = ProgressTracker;
} 