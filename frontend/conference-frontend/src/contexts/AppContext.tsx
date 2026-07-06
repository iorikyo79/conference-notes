// App 전역 상태 관리
import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import type { Conference, PageName } from '../types/api';
import { apiClient } from '../services/api';

interface AppContextValue {
  currentPage: PageName;
  navigateTo: (page: PageName) => void;

  conferences: Conference[];
  activeConference: Conference | null;
  activeConferenceId: string | null;
  setActiveConferenceId: (id: string | null) => void;

  activeSessionId: string | null;
  setActiveSessionId: (id: string | null) => void;

  loading: boolean;
  error: string | null;

  loadConferences: () => Promise<void>;
  refreshConference: () => Promise<void>;
  createConference: (data: {
    id: string;
    name: string;
    location?: string;
    start_date: string;
    end_date: string;
  }) => Promise<void>;
}

const AppContext = createContext<AppContextValue | null>(null);

export const AppProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [currentPage, setCurrentPage] = useState<PageName>('home');
  const [conferences, setConferences] = useState<Conference[]>([]);
  const [activeConferenceId, setActiveConferenceId] = useState<string | null>(null);
  const [activeConference, setActiveConference] = useState<Conference | null>(null);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const navigateTo = useCallback((page: PageName) => {
    setCurrentPage(page);
  }, []);

  const loadConferences = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiClient.getConferences();
      setConferences(data);
      // 첫 번째 학회를 기본으로 선택
      if (data.length > 0 && !activeConferenceId) {
        setActiveConferenceId(data[0].id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '학회 목록 로드 실패');
    } finally {
      setLoading(false);
    }
  }, [activeConferenceId]);

  const refreshConference = useCallback(async () => {
    if (!activeConferenceId) return;
    try {
      const conf = await apiClient.getConference(activeConferenceId);
      setActiveConference(conf);
    } catch (err) {
      setError(err instanceof Error ? err.message : '학회 정보 로드 실패');
    }
  }, [activeConferenceId]);

  // activeConferenceId가 변경되면 학회 상세 정보 로드
  useEffect(() => {
    if (activeConferenceId) {
      refreshConference();
    } else {
      setActiveConference(null);
    }
  }, [activeConferenceId, refreshConference]);

  // 초기 로드
  useEffect(() => {
    loadConferences();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const createConference = useCallback(async (data: {
    id: string;
    name: string;
    location?: string;
    start_date: string;
    end_date: string;
  }) => {
    setError(null);
    try {
      await apiClient.createConference(data);
      await loadConferences();
    } catch (err) {
      setError(err instanceof Error ? err.message : '학회 생성 실패');
      throw err;
    }
  }, [loadConferences]);

  const value: AppContextValue = {
    currentPage,
    navigateTo,
    conferences,
    activeConference,
    activeConferenceId,
    setActiveConferenceId,
    activeSessionId,
    setActiveSessionId,
    loading,
    error,
    loadConferences,
    refreshConference,
    createConference,
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
};

export const useApp = (): AppContextValue => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useApp must be used within AppProvider');
  }
  return context;
};
