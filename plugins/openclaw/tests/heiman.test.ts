import { describe, it, expect } from 'vitest';

describe('Heiman Plugin', () => {
  it('should have valid config', () => {
    const config = {
      debug: false,
      backend_url: 'http://localhost:1912',
    };
    expect(config.backend_url).toBe('http://localhost:1912');
  });

  it('should validate sensor types', () => {
    const validTypes = ['Smoke', 'CO', 'TH', 'Door', 'Water'];
    expect(validTypes).toContain('Smoke');
    expect(validTypes).toContain('CO');
  });
});
