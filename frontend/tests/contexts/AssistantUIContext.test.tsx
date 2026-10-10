import { describe, it, expect } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { AssistantUIProvider, useAssistantUI } from '@/contexts/AssistantUIContext';

describe('AssistantUIContext', () => {
  it('reports unavailable and closed with no provider', () => {
    const { result } = renderHook(() => useAssistantUI());

    expect(result.current.isAvailable).toBe(false);
    expect(result.current.isOpen).toBe(false);
    expect(result.current.projectId).toBeNull();
  });

  it('calling openAssistant/closeAssistant/setAvailable with no provider is a harmless no-op', () => {
    const { result } = renderHook(() => useAssistantUI());

    expect(() => {
      result.current.openAssistant('project-1');
      result.current.closeAssistant();
      result.current.forgetProject();
      result.current.setAvailable(true);
      result.current.setPageProjectId('project-1');
    }).not.toThrow();
  });

  it('opens with a project id and closes again, keeping the project the conversation is under', () => {
    const { result } = renderHook(() => useAssistantUI(), { wrapper: AssistantUIProvider });

    act(() => result.current.openAssistant('project-123'));
    expect(result.current.isOpen).toBe(true);
    expect(result.current.projectId).toBe('project-123');

    act(() => result.current.closeAssistant());
    expect(result.current.isOpen).toBe(false);
    expect(result.current.projectId).toBe('project-123');
  });

  it('forgets the kept project on request, for a sign-out', () => {
    const { result } = renderHook(() => useAssistantUI(), { wrapper: AssistantUIProvider });
    act(() => result.current.openAssistant('project-123'));
    act(() => result.current.closeAssistant());

    act(() => result.current.forgetProject());

    expect(result.current.projectId).toBeNull();
    expect(result.current.isOpen).toBe(false);
  });

  it('replaces the kept project on the next open', () => {
    const { result } = renderHook(() => useAssistantUI(), { wrapper: AssistantUIProvider });
    act(() => result.current.openAssistant('project-123'));
    act(() => result.current.closeAssistant());

    act(() => result.current.openAssistant());

    expect(result.current.projectId).toBeNull();
  });

  it('opens with no project id for the header button', () => {
    const { result } = renderHook(() => useAssistantUI(), { wrapper: AssistantUIProvider });

    act(() => result.current.openAssistant());

    expect(result.current.projectId).toBeNull();
  });

  it('flips isAvailable once the lazy chunk confirms the backend is on', () => {
    const { result } = renderHook(() => useAssistantUI(), { wrapper: AssistantUIProvider });

    act(() => result.current.setAvailable(true));

    expect(result.current.isAvailable).toBe(true);
  });

  it('opens for the page project, and keeps it when the page scope is cleared meanwhile', () => {
    const { result } = renderHook(() => useAssistantUI(), { wrapper: AssistantUIProvider });

    act(() => result.current.setPageProjectId('project-A'));
    act(() => result.current.openAssistant());
    expect(result.current.projectId).toBe('project-A');

    act(() => result.current.setPageProjectId(null));
    expect(result.current.isOpen).toBe(true);
    expect(result.current.projectId).toBe('project-A');
  });

  it('prefers an explicit project over the page project', () => {
    const { result } = renderHook(() => useAssistantUI(), { wrapper: AssistantUIProvider });

    act(() => result.current.setPageProjectId('project-A'));
    act(() => result.current.openAssistant('project-B'));

    expect(result.current.projectId).toBe('project-B');
  });

  it('opens the general panel on an explicit null, even on a project page', () => {
    const { result } = renderHook(() => useAssistantUI(), { wrapper: AssistantUIProvider });

    act(() => result.current.setPageProjectId('project-A'));
    act(() => result.current.openAssistant('project-A'));
    act(() => result.current.openAssistant(null));

    expect(result.current.isOpen).toBe(true);
    expect(result.current.projectId).toBeNull();
  });

  it('does not open the panel by recording a page project', () => {
    const { result } = renderHook(() => useAssistantUI(), { wrapper: AssistantUIProvider });

    act(() => result.current.setPageProjectId('project-7'));

    expect(result.current.isOpen).toBe(false);
    expect(result.current.projectId).toBeNull();
  });
});
