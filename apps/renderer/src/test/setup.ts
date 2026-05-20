import '@testing-library/jest-dom';

// Mock electronAPI — tests inject custom behavior per test via window.electronAPI
Object.defineProperty(window, 'electronAPI', {
  value: {},
  writable: true,
});