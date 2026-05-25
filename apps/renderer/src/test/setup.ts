import '@testing-library/jest-dom';

// Mock electronAPI — tests inject custom behavior per test via window.electronAPI
Object.defineProperty(window, 'electronAPI', {
  value: {},
  writable: true,
});

// Mock matchMedia for antd responsive components
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
});

// Mock getComputedStyle for antd
Object.defineProperty(window, 'getComputedStyle', {
  value: () => ({
    getPropertyValue: () => '',
  }),
});
