// Lightweight EventSource polyfill for POST with headers
export class EventSourcePolyfill {
  constructor(url, options = {}) {
    this.url = url;
    this.options = options;
    this.listeners = {};
    this._controller = null;
    this._closed = false;
    this._start();
  }

  _emit(type, evt) {
    const list = this.listeners[type] || [];
    for (const cb of list) cb(evt);
  }

  addEventListener(type, cb) {
    this.listeners[type] = this.listeners[type] || [];
    this.listeners[type].push(cb);
  }

  close() {
    this._closed = true;
    try { this._controller && this._controller.abort(); } catch {}
    this.listeners = {};
  }

  _start() {
    const { headers = {}, method = 'POST', payload } = this.options;
    this._controller = new AbortController();
    const fetchHeaders = { ...headers, 'Accept': headers['Accept'] || 'text/event-stream' };
    fetch(this.url, { method, headers: fetchHeaders, body: payload, signal: this._controller.signal, cache: 'no-store' })
      .then(resp => {
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const ct = resp.headers.get('content-type') || '';
        if (!ct.includes('text/event-stream')) {
          throw new Error('Invalid content-type, expected text/event-stream');
        }
        if (!resp.body) throw new Error('No stream body');
        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        const pump = () => reader.read().then(({ value, done }) => {
          if (this._closed) return;
          if (done) return;
          buffer += decoder.decode(value, { stream: true });
          // Normalize newlines to handle CRLF and CR
          buffer = buffer.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
          let idx;
          while ((idx = buffer.indexOf('\n\n')) !== -1) {
            const raw = buffer.slice(0, idx);
            buffer = buffer.slice(idx + 2);
            const lines = raw.split('\n');
            let event = 'message';
            let data = '';
            for (const line of lines) {
              if (!line) continue;
              if (line.startsWith(':')) continue; // comment
              if (line.startsWith('event:')) { event = line.slice(6).trim(); continue; }
              if (line.startsWith('data:')) { data += (data ? '\n' : '') + line.slice(5).trim(); continue; }
              // ignore id: / retry:
            }
            this._emit(event, { data });
          }
          return pump();
        }).catch(err => {
          if (this._closed) return;
          this._emit('error', { data: JSON.stringify({ message: err?.message || 'Stream error' }) });
        });
        return pump();
      })
      .catch(err => {
        if (this._closed) return;
        this._emit('error', { data: JSON.stringify({ message: err?.message || 'Stream error' }) });
      });
  }
}

// For convenience in non-module code which may check window.EventSourcePolyfill
if (typeof window !== 'undefined') {
  // eslint-disable-next-line no-undef
  window.EventSourcePolyfill = EventSourcePolyfill;
}


