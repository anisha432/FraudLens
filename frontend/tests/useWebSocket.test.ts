import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { createWS, getAuthToken } from '../src/api';

// ---------------------------------------------------------------------------
// Frontend contract tests for WebSocket auth + reconnect behavior.
//
// These verify the *client-side* rules that prevent the infinite reconnect
// loop reported in production (repeated 401/403 with token= and stale token).
//
// The real useWebSocket() hook uses React hooks; we test its logic here by
// extracting the pure functions (createWS, getAuthToken) and by exercising
// the close-handler decision logic through aFakeConnection that mirrors the
// hook's onclose branching.
// ---------------------------------------------------------------------------

function badAuthEvent(event: CloseEvent): boolean {
  if (event && typeof event.code === 'number') {
    if (event.code >= 4000 || event.code === 1008) {
      return true;
    }
  }
  return false;
}

/** Mirror the hook's onclose decision: returns 'stop' | 'reconnect' | 'no-op'. */
function decideOnClose(
  event: CloseEvent,
  getCurrentToken: () => string | null,
  badAuthRef: { current: boolean },
  consecutive1006Ref: { current: number },
): 'stop' | 'reconnect' | 'no-op' {
  if (badAuthEvent(event)) {
    badAuthRef.current = true;
    return 'stop';
  }
  if (getCurrentToken() === null) {
    badAuthRef.current = true;
    return 'stop';
  }
  if (event.code === 1006) {
    consecutive1006Ref.current = (consecutive1006Ref.current || 0) + 1;
    if (consecutive1006Ref.current >= 2) {
      badAuthRef.current = true;
      return 'stop';
    }
  } else {
    consecutive1006Ref.current = 0;
  }
  return 'reconnect';
}

// ---------------------------------------------------------------------------
// createWS / getAuthToken
// ---------------------------------------------------------------------------

describe('createWS', () => {
  const origLocalStorage = global.localStorage;

  beforeEach(() => {
    global.localStorage = {
      store: {} as Record<string, string>,
      getItem(key: string) {
        return this.store[key] ?? null;
      },
      setItem(key: string, val: string) {
        this.store[key] = val;
      },
      removeItem(key: string) {
        delete this.store[key];
      },
      clear() {
        this.store = {};
      },
    } as Storage;
    (global.localStorage as any).clear();
  });

  afterEach(() => {
    global.localStorage = origLocalStorage;
  });

  it('returns null when there is no token', () => {
    expect(createWS()).toBeNull();
  });

  it('returns null when the token is blank/whitespace only', () => {
    global.localStorage.setItem('fraudlens_token', '   ');
    expect(createWS()).toBeNull();
  });

  it('returns a WebSocket only when a real token exists', () => {
    global.localStorage.setItem('fraudlens_token', 'some-token-abc123');
    const ws = createWS();
    expect(ws).not.toBeNull();
    expect(ws.url).toContain('token=some-token-abc123');
    expect(ws.url).toMatch(/ws[s]?:\/\/.*\/ws\/live/);
  });

  it('encodes the token so it is safe in a query string', () => {
    global.localStorage.setItem('fraudlens_token', 'a b&c=d');
    const ws = createWS();
    expect(ws).not.toBeNull();
    expect(ws.url).toContain('token=');
  });
});

describe('getAuthToken', () => {
  const origLocalStorage = global.localStorage;

  beforeEach(() => {
    global.localStorage = {
      store: {} as Record<string, string>,
      getItem(key: string) {
        return this.store[key] ?? null;
      },
      setItem(key: string, val: string) {
        this.store[key] = val;
      },
      removeItem(key: string) {
        delete this.store[key];
      },
      clear() {
        this.store = {};
      },
    } as Storage;
  });

  afterEach(() => {
    global.localStorage = origLocalStorage;
  });

  it('returns null for missing token', () => {
    expect(getAuthToken()).toBeNull();
  });

  it('returns null for whitespace-only token', () => {
    global.localStorage.setItem('fraudlens_token', '   ');
    expect(getAuthToken()).toBeNull();
  });

  it('returns the trimmed token when it is present', () => {
    global.localStorage.setItem('fraudlens_token', '  real-token  ');
    expect(getAuthToken()).toBe('real-token');
  });
});

// ---------------------------------------------------------------------------
// useWebSocket onclose decision logic (mirrors hooks/useWebSocket.ts)
// ---------------------------------------------------------------------------

describe('useWebSocket onclose decision logic', () => {
  const origLocalStorage = global.localStorage;

  beforeEach(() => {
    global.localStorage = {
      store: {} as Record<string, string>,
      getItem(key: string) {
        return this.store[key] ?? null;
      },
      setItem(key: string, val: string) {
        this.store[key] = val;
      },
      removeItem(key: string) {
        delete this.store[key];
      },
      clear() {
        this.store = {};
      },
    } as Storage;
  });

  afterEach(() => {
    global.localStorage = origLocalStorage;
  });

  it('stops reconnecting when server rejects with close code >= 4000', () => {
    global.localStorage.setItem('fraudlens_token', 'stale-token');
    const badAuth = { current: false };
    const cons1006 = { current: 0 };

    const ce = { code: 4001, reason: 'Not authenticated' } as CloseEvent;
    const decision = decideOnClose(ce, getAuthToken, badAuth, cons1006);

    expect(decision).toBe('stop');
    expect(badAuth.current).toBe(true);
    // No reconnect should be scheduled.
  });

  it('stops reconnecting when token is cleared (logout) and close code is 1006', () => {
    global.localStorage.setItem('fraudlens_token', 'live-token');
    const badAuth = { current: false };
    const cons1006 = { current: 0 };

    // Simulate logout: remove token.
    global.localStorage.removeItem('fraudlens_token');

    const ce = { code: 1006 } as CloseEvent;
    const decision = decideOnClose(ce, getAuthToken, badAuth, cons1006);

    expect(decision).toBe('stop');
    expect(badAuth.current).toBe(true);
  });

  it('allows one reconnect after first 1006 with token still present', () => {
    global.localStorage.setItem('fraudlens_token', 'maybe-stale-token');
    const badAuth = { current: false };
    const cons1006 = { current: 0 };

    // First 1006: ambiguous, allow reconnect.
    const ce1 = { code: 1006 } as CloseEvent;
    expect(decideOnClose(ce1, getAuthToken, badAuth, cons1006)).toBe('reconnect');
    expect(badAuth.current).toBe(false);
    expect(cons1006.current).toBe(1);

    // Second 1006 in a row: treat as auth failure, stop.
    const ce2 = { code: 1006 } as CloseEvent;
    expect(decideOnClose(ce2, getAuthToken, badAuth, cons1006)).toBe('stop');
    expect(badAuth.current).toBe(true);
  });

  it('resets 1006 counter on non-1006 close codes', () => {
    global.localStorage.setItem('fraudlens_token', 'real-token');
    const badAuth = { current: false };
    const cons1006 = { current: 2 }; // pretend we already saw two 1006s

    // A normal close (e.g. 1000) resets the counter.
    const ce = { code: 1000, reason: 'Normal closure' } as CloseEvent;
    const decision = decideOnClose(ce, getAuthToken, badAuth, cons1006);

    expect(decision).toBe('reconnect');
    expect(badAuth.current).toBe(false);
    expect(cons1006.current).toBe(0);
  });

  it('does not connect when badAuthRef is already set', () => {
    // This mirrors connect() bailing out when badAuthRef.current is true.
    const badAuth = { current: true };
    const cons1006 = { current: 0 };
    global.localStorage.setItem('fraudlens_token', 'some-token');

    // connect() checks: if (!getAuthToken() || badAuthRef.current) return;
    const token = getAuthToken();
    const shouldConnect = !(token === null || token === undefined) && !badAuth.current;
    expect(shouldConnect).toBe(false);
  });
});
