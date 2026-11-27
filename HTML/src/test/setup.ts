import "@testing-library/jest-dom/vitest";

// jsdom has no ResizeObserver; the charts' responsive containers need one. A no-op is enough for the tests.
if (!("ResizeObserver" in globalThis)) {
  class ResizeObserverStub {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  Object.assign(globalThis, { ResizeObserver: ResizeObserverStub });
}
