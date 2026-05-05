import React, { useState, useEffect } from 'react';

export default function PendingReviewsPage() {
  const [reviews, setReviews] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchReviews = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/bom/reviews');
      const data = await res.json();
      setReviews(Array.isArray(data.reviews) ? data.reviews : []);
    } catch (err) {
      console.error('Failed to fetch reviews', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReviews();
  }, []);

  const getStatusColor = (status) => {
    switch (status?.toUpperCase()) {
      case 'APPROVED': return 'bg-zen-success/10 text-zen-success border-zen-success/20';
      case 'REJECTED': return 'bg-zen-error/10 text-zen-error border-zen-error/20';
      default: return 'bg-zen-warning/10 text-zen-warning border-zen-warning/20';
    }
  };

  return (
    <div className="flex-1 overflow-y-auto p-10 bg-zen-bg">
      <div className="max-w-6xl mx-auto">
        <header className="flex justify-between items-center mb-10">
          <div>
            <h2 className="text-3xl font-bold text-zen-text-main mb-2">Pending Reviews</h2>
            <p className="text-zen-text-dim">Monitor BOM submissions sent to the Design Lead.</p>
          </div>
          <button 
            onClick={fetchReviews}
            className="p-2 rounded-lg bg-zen-surface-alt border border-zen-border text-zen-text-dim hover:text-zen-text-main transition-all"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg>
          </button>
        </header>

        {loading ? (
          <div className="text-center py-20 text-zen-text-dim">Connecting to ToolRoom...</div>
        ) : reviews.length > 0 ? (
          <div className="zen-card overflow-hidden">
            <table className="w-full text-left text-sm">
              <thead className="bg-zen-surface-alt text-zen-text-muted text-[10px] uppercase tracking-widest font-bold">
                <tr>
                  <th className="px-6 py-4">Submission Date</th>
                  <th className="px-6 py-4">Project / Tool</th>
                  <th className="px-6 py-4">Submitted By</th>
                  <th className="px-6 py-4 text-center">Status</th>
                  <th className="px-6 py-4">Lead Comments</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zen-border">
                {reviews.map((review, i) => (
                  <tr key={i} className="hover:bg-zen-surface-alt/50 transition-colors">
                    <td className="px-6 py-4 font-mono text-[11px] text-zen-text-muted">
                      {new Date(review.createdAt).toLocaleString()}
                    </td>
                    <td className="px-6 py-4">
                      <div className="font-bold text-zen-text-main">{review.projectName}</div>
                      <div className="text-[10px] text-zen-primary font-mono">{review.toolId}</div>
                    </td>
                    <td className="px-6 py-4 text-zen-text-dim">
                      {review.submittedBy}
                    </td>
                    <td className="px-6 py-4 text-center">
                      <span className={`px-3 py-1 rounded-full text-[10px] font-bold border ${getStatusColor(review.status)}`}>
                        {review.status || 'PENDING'}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-xs text-zen-text-dim italic">
                      {review.leadComment || 'No feedback yet.'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="zen-card p-20 text-center">
            <div className="w-16 h-16 rounded-full bg-zen-surface-alt flex items-center justify-center mx-auto mb-6">
              <svg className="w-8 h-8 text-zen-text-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"></path></svg>
            </div>
            <p className="text-zen-text-dim">No BOMs currently pending review.</p>
          </div>
        )}
      </div>
    </div>
  );
}
