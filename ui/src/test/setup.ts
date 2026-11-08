import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => {
  cleanup();
  window.location.hash = "";
});

// React Flow measures its nodes; jsdom lays nothing out (React Flow's guide to testing).
class ResizeObserverStub {
  constructor(private readonly callback: ResizeObserverCallback) {}
  observe(target: Element): void {
    this.callback([{ target } as ResizeObserverEntry], this as unknown as ResizeObserver);
  }
  unobserve(): void {}
  disconnect(): void {}
}

class DOMMatrixReadOnlyStub {
  m22: number;
  constructor(transform?: string) {
    const scale = transform?.match(/scale\(([0-9.]+)\)/)?.[1];
    this.m22 = scale !== undefined ? Number(scale) : 1;
  }
}

Object.assign(globalThis, {
  ResizeObserver: ResizeObserverStub,
  DOMMatrixReadOnly: DOMMatrixReadOnlyStub,
});
// A block is 176 × 64 px; every other element (the flow's panes) 1,000 × 600 px.
Object.defineProperties(HTMLElement.prototype, {
  offsetHeight: {
    get(this: HTMLElement) {
      if (this.classList.contains("react-flow__node")) return 64;
      return this.style.height.endsWith("px") ? Number.parseFloat(this.style.height) : 600;
    },
  },
  offsetWidth: {
    get(this: HTMLElement) {
      if (this.classList.contains("react-flow__node")) return 176;
      return this.style.width.endsWith("px") ? Number.parseFloat(this.style.width) : 1000;
    },
  },
});
(SVGElement.prototype as unknown as { getBBox: () => DOMRect }).getBBox = () =>
  ({ x: 0, y: 0, width: 0, height: 0 }) as DOMRect;
