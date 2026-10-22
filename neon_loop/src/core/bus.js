// Tiny event bus: bus.on(name, fn) → off(); bus.emit(name, payload). Event names: CONTRACTS.md §Events.
const handlers = new Map();
export const bus = {
  on(name, fn) { let s = handlers.get(name); if (!s) handlers.set(name, s = new Set()); s.add(fn); return () => s.delete(fn); },
  once(name, fn) { const off = bus.on(name, p => { off(); fn(p); }); return off; },
  emit(name, payload) { const s = handlers.get(name); if (s) for (const fn of [...s]) fn(payload); },
};
