import '@testing-library/jest-dom/vitest';
import { vi } from 'vitest';
import React from 'react';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: {
      changeLanguage: async () => Promise.resolve(),
      language: 'zh',
    },
  }),
}));

vi.mock('lucide-react', () => ({
  Home: vi.fn(() => React.createElement('svg', { 'data-testid': 'home-icon' })),
  ChevronDown: vi.fn(() => React.createElement('svg', { 'data-testid': 'chevron-down-icon' })),
}));

globalThis.fetch = vi.fn(() =>
  Promise.resolve({
    json: () => Promise.resolve({ code: 0, data: [] }),
  }),
) as unknown as typeof fetch;
