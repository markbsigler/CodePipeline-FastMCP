/**
 * Streaming Response Utility for FastMCP Server
 * Provides Server-Sent Events and chunked transfer encoding support
 */

class StreamingResponse {
  constructor(res) {
    this.res = res;
    this.isInitialized = false;
  }

  /**
   * Initialize Server-Sent Events stream
   */
  initializeSSE() {
    if (this.isInitialized) return;
    
    this.res.writeHead(200, {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Headers': 'Cache-Control, Authorization',
      'X-Accel-Buffering': 'no' // Disable nginx buffering
    });
    
    this.isInitialized = true;
  }

  /**
   * Initialize chunked transfer encoding
   */
  initializeChunked() {
    if (this.isInitialized) return;
    
    this.res.writeHead(200, {
      'Content-Type': 'application/json',
      'Transfer-Encoding': 'chunked',
      'Access-Control-Allow-Origin': '*',
      'X-Content-Type-Options': 'nosniff'
    });
    
    this.isInitialized = true;
  }

  /**
   * Send progress update via Server-Sent Events
   */
  async sendProgress(message, progress = null, eventType = 'progress') {
    this.initializeSSE();
    
    const data = {
      type: eventType,
      message: message,
      timestamp: new Date().toISOString()
    };
    
    if (progress !== null) {
      data.progress = progress;
    }
    
    this.res.write(`event: ${eventType}\n`);
    this.res.write(`data: ${JSON.stringify(data)}\n\n`);
    
    // Small delay to ensure proper streaming
    await new Promise(resolve => setImmediate(resolve));
  }

  /**
   * Send data chunk via chunked transfer encoding
   */
  async sendChunk(data) {
    this.initializeChunked();
    
    const chunk = typeof data === 'string' ? data : JSON.stringify(data);
    this.res.write(chunk);
    
    await new Promise(resolve => setImmediate(resolve));
  }

  /**
   * Send completion event
   */
  async sendComplete(result = null) {
    if (this.res.headersSent && this.res.getHeader('content-type') === 'text/event-stream') {
      // SSE mode
      const data = {
        type: 'complete',
        timestamp: new Date().toISOString()
      };
      
      if (result !== null) {
        data.result = result;
      }
      
      this.res.write(`event: complete\n`);
      this.res.write(`data: ${JSON.stringify(data)}\n\n`);
    } else if (result !== null) {
      // Chunked mode - send final data
      await this.sendChunk(result);
    }
    
    this.res.end();
  }

  /**
   * Send error event
   */
  async sendError(error, code = 500) {
    if (!this.isInitialized) {
      // Send regular error response
      this.res.status(code).json({
        error: error.message || error,
        timestamp: new Date().toISOString()
      });
      return;
    }
    
    if (this.res.getHeader('content-type') === 'text/event-stream') {
      // SSE mode
      this.res.write(`event: error\n`);
      this.res.write(`data: ${JSON.stringify({
        type: 'error',
        error: error.message || error,
        code: code,
        timestamp: new Date().toISOString()
      })}\n\n`);
    } else {
      // Chunked mode
      await this.sendChunk({
        error: error.message || error,
        code: code,
        timestamp: new Date().toISOString()
      });
    }
    
    this.res.end();
  }

  /**
   * Handle client disconnect gracefully
   */
  onDisconnect(callback) {
    this.res.on('close', callback);
    this.res.on('error', callback);
  }

  /**
   * Check if client is still connected
   */
  isConnected() {
    return !this.res.destroyed && this.res.writable;
  }
}

/**
 * WebSocket streaming helper
 */
class WebSocketStreaming {
  constructor(ws) {
    this.ws = ws;
    this.isConnected = true;
    
    // Monitor connection status
    ws.on('close', () => {
      this.isConnected = false;
    });
    
    ws.on('error', () => {
      this.isConnected = false;
    });
  }

  /**
   * Send streaming data via WebSocket
   */
  async sendStream(streamId, data, sequence = null, isLast = false) {
    if (!this.isConnected || this.ws.readyState !== 1) { // WebSocket.OPEN
      return false;
    }
    
    const message = {
      type: 'stream_data',
      streamId: streamId,
      data: data,
      timestamp: new Date().toISOString(),
      isLast: isLast
    };
    
    if (sequence !== null) {
      message.sequence = sequence;
    }
    
    try {
      this.ws.send(JSON.stringify(message));
      return true;
    } catch (err) {
      console.error('WebSocket send error:', err);
      this.isConnected = false;
      return false;
    }
  }

  /**
   * Send progress update via WebSocket
   */
  async sendProgress(progress, message, streamId = null) {
    if (!this.isConnected) return false;
    
    const progressMessage = {
      type: 'progress',
      progress: progress,
      message: message,
      timestamp: new Date().toISOString()
    };
    
    if (streamId) {
      progressMessage.streamId = streamId;
    }
    
    try {
      this.ws.send(JSON.stringify(progressMessage));
      return true;
    } catch (err) {
      console.error('WebSocket progress send error:', err);
      return false;
    }
  }

  /**
   * Send completion message
   */
  async sendComplete(result = null, streamId = null) {
    if (!this.isConnected) return false;
    
    const completeMessage = {
      type: 'complete',
      timestamp: new Date().toISOString()
    };
    
    if (result !== null) {
      completeMessage.result = result;
    }
    
    if (streamId) {
      completeMessage.streamId = streamId;
    }
    
    try {
      this.ws.send(JSON.stringify(completeMessage));
      return true;
    } catch (err) {
      console.error('WebSocket complete send error:', err);
      return false;
    }
  }

  /**
   * Send error message
   */
  async sendError(error, streamId = null) {
    if (!this.isConnected) return false;
    
    const errorMessage = {
      type: 'error',
      error: error.message || error,
      timestamp: new Date().toISOString()
    };
    
    if (streamId) {
      errorMessage.streamId = streamId;
    }
    
    try {
      this.ws.send(JSON.stringify(errorMessage));
      return true;
    } catch (err) {
      console.error('WebSocket error send error:', err);
      return false;
    }
  }
}

module.exports = {
  StreamingResponse,
  WebSocketStreaming
};
