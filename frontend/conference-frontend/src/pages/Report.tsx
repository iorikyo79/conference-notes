// Report 페이지 (Phase 3)
import React, { useState, useEffect } from 'react';
import { useApp } from '../contexts/AppContext';
import { apiClient } from '../services/api';
import type { ReportResponse, CaptionStatus } from '../types/api';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

type ReportTypeMode = 'ai' | 'html';

export const Report: React.FC = () => {
  const { activeConferenceId, activeConference } = useApp();
  const [report, setReport] = useState<ReportResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reportType, setReportType] = useState<ReportTypeMode>('ai');
  const [captionStatus, setCaptionStatus] = useState<CaptionStatus | null>(null);

  useEffect(() => {
    if (activeConferenceId && reportType === 'html') {
      apiClient.getCaptionStatus(activeConferenceId).then(setCaptionStatus).catch(() => {});
    } else {
      setCaptionStatus(null);
    }
  }, [activeConferenceId, reportType]);

  const generateReport = async () => {
    if (!activeConferenceId) return;
    setLoading(true);
    setError(null);
    setReport(null);
    try {
      const result = await apiClient.generateReport({
        conference_id: activeConferenceId,
        report_type: reportType === 'html' ? 'html' : 'full',
      });
      setReport(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : '리포트 생성 실패');
    } finally {
      setLoading(false);
    }
  };

  const downloadMarkdown = () => {
    if (!report) return;
    const blob = new Blob([report.summary], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${report.conference_name}_report.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const downloadHtml = async () => {
    if (!activeConferenceId) return;
    try {
      const blob = await apiClient.exportReportHtml(activeConferenceId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${activeConference?.name || 'conference'}_report.html`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'HTML 다운로드 실패');
    }
  };

  return (
    <div className="report-page">
      <h2>학회 리포트</h2>

      {/* 리포트 타입 선택 */}
      <div className="report-type-selector">
        <button
          className={`report-type-btn ${reportType === 'ai' ? 'active' : ''}`}
          onClick={() => { setReportType('ai'); setReport(null); }}
        >
          AI 요약 리포트
        </button>
        <button
          className={`report-type-btn ${reportType === 'html' ? 'active' : ''}`}
          onClick={() => { setReportType('html'); setReport(null); }}
        >
          HTML 통합 리포트
        </button>
      </div>

      {/* 캡션 상태 경고 (HTML 모드) */}
      {reportType === 'html' && captionStatus && captionStatus.total > 0 && captionStatus.completed < captionStatus.total && (
        <div className="caption-warning">
          이미지 캡션이 모두 생성되지 않았습니다. ({captionStatus.completed}/{captionStatus.total} 완료)
          HTML 리포트에 빈 캡션이 포함될 수 있습니다.
        </div>
      )}

      <div className="report-actions">
        <button
          className="btn btn-primary"
          onClick={generateReport}
          disabled={loading || !activeConferenceId}
        >
          {loading ? '생성 중...' : reportType === 'html' ? 'HTML 리포트 생성' : '리포트 생성'}
        </button>
        {report && reportType === 'ai' && (
          <button className="btn btn-secondary" onClick={downloadMarkdown}>
            Markdown 다운로드
          </button>
        )}
        {report && reportType === 'html' && (
          <button className="btn btn-secondary" onClick={downloadHtml}>
            HTML 다운로드
          </button>
        )}
      </div>

      {error && (
        <div style={{ color: '#dc3545', padding: '1rem', background: '#ffebee', borderRadius: '8px', marginBottom: '1rem' }}>
          {error}
        </div>
      )}

      {report ? (
        reportType === 'html' ? (
          <div className="html-preview">
            <iframe
              srcDoc={report.summary}
              style={{ width: '100%', height: '70vh', border: '1px solid #ddd', borderRadius: '8px' }}
              title="HTML Report Preview"
            />
          </div>
        ) : (
          <>
            {report.keywords.length > 0 && (
              <div className="keywords-container">
                {report.keywords.map((kw, i) => (
                  <span key={i} className="keyword-tag">{kw}</span>
                ))}
              </div>
            )}
            <div className="report-content">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {report.summary}
              </ReactMarkdown>
            </div>
          </>
        )
      ) : (
        !loading && (
          <div className="report-content" style={{ textAlign: 'center', color: '#999' }}>
            <p>
              {reportType === 'html'
                ? '\'HTML 리포트 생성\' 버튼을 눌러 통합 HTML 리포트를 생성하세요.'
                : '\'리포트 생성\' 버튼을 눌러 학회 참석 리포트를 생성하세요.'}
            </p>
            {activeConference && (
              <p style={{ marginTop: '0.5rem', fontSize: '0.85rem' }}>
                학회: {activeConference.name}
              </p>
            )}
          </div>
        )
      )}
    </div>
  );
};
