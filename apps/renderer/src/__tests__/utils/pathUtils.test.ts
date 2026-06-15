import { describe, it, expect } from 'vitest';
import { getFileNameFromPath } from '../utils/pathUtils';

describe('getFileNameFromPath', () => {
  it('extracts filename from Windows path', () => {
    expect(getFileNameFromPath('C:\\Users\\test\\file.pdf')).toBe('file.pdf');
  });

  it('extracts filename from Unix path', () => {
    expect(getFileNameFromPath('/home/user/file.pdf')).toBe('file.pdf');
  });

  it('returns input when no separator found', () => {
    expect(getFileNameFromPath('file.pdf')).toBe('file.pdf');
  });
});