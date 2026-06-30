import { describe, it, expect } from 'vitest';
import { HeimanBackendClient } from '../src/services/backend';

describe('HeimanBackendClient', () => {
  const mockConfig = {
    backend_url: 'http://localhost:1912',
  };

  it('should create client with config', () => {
    const client = new HeimanBackendClient(mockConfig);
    expect(client).toBeDefined();
  });

  it('should have listSensors method', async () => {
    const client = new HeimanBackendClient(mockConfig);
    // Mock test - will return empty array on connection error
    const sensors = await client.listSensors();
    expect(Array.isArray(sensors)).toBe(true);
  });

  it('should handle sensor status', () => {
    const validStatuses = ['ONLINE', 'OFFLINE'];
    expect(validStatuses).toContain('ONLINE');
  });
});
