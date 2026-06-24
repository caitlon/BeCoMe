import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { downloadJson } from '@/lib/download';

describe('downloadJson', () => {
  let createObjectURL: ReturnType<typeof vi.fn>;
  let revokeObjectURL: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    createObjectURL = vi.fn(() => 'blob:mock-url');
    revokeObjectURL = vi.fn();
    URL.createObjectURL = createObjectURL as unknown as typeof URL.createObjectURL;
    URL.revokeObjectURL = revokeObjectURL as unknown as typeof URL.revokeObjectURL;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('builds a JSON blob and revokes the object URL afterwards', () => {
    downloadJson({ hello: 'world' }, 'data.json');

    expect(createObjectURL).toHaveBeenCalledOnce();
    const blob = createObjectURL.mock.calls[0][0] as Blob;
    expect(blob.type).toBe('application/json');
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:mock-url');
  });

  it('clicks an anchor carrying the requested filename', () => {
    const click = vi.fn();
    const anchor = document.createElement('a');
    anchor.click = click;
    const createElement = vi.spyOn(document, 'createElement').mockReturnValue(anchor);

    downloadJson({ a: 1 }, 'become-export.json');

    expect(anchor.download).toBe('become-export.json');
    expect(anchor.href).toBe('blob:mock-url');
    expect(click).toHaveBeenCalledOnce();

    createElement.mockRestore();
  });

  it('revokes the URL even when the click throws', () => {
    const anchor = document.createElement('a');
    anchor.click = vi.fn(() => {
      throw new Error('click failed');
    });
    vi.spyOn(document, 'createElement').mockReturnValue(anchor);

    expect(() => downloadJson({ a: 1 }, 'x.json')).toThrow('click failed');
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:mock-url');
  });
});
