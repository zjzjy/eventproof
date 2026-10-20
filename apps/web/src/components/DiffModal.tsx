import { useEffect, useState } from "react";
import { api } from "../api";
import type { Diff, Document } from "../types";
import { claimTypeLabel, formatDateTime, statusLabel } from "../utils";

type Props = {
  eventId: string;
  fromVersion: number;
  toVersion: number;
  documents: Document[];
  onClose: () => void;
};

export default function DiffModal({
  eventId,
  fromVersion,
  toVersion,
  documents,
  onClose,
}: Props) {
  const [diff, setDiff] = useState<Diff | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    api
      .diff(eventId, fromVersion, toVersion)
      .then((data) => alive && setDiff(data))
      .catch((err: Error) => alive && setError(err.message));
    return () => {
      alive = false;
    };
  }, [eventId, fromVersion, toVersion]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const trigger = diff
    ? documents.find((doc) => doc.id === diff.trigger_document_id)
    : null;

  return (
    <div className="overlay" onMouseDown={onClose}>
      <section
        className="modal diff-modal"
        onMouseDown={(event) => event.stopPropagation()}
        aria-modal="true"
      >
        <header className="modal-head">
          <div>
            <div className="eyebrow">VERSION DIFF / 版本变化</div>
            <h2>
              版本 {fromVersion} → {toVersion}
            </h2>
            {diff && (
              <p>
                {formatDateTime(diff.from.knowledge_at)} →{" "}
                {formatDateTime(diff.to.knowledge_at)}
              </p>
            )}
          </div>
          <button className="icon-button" onClick={onClose} aria-label="关闭">
            ×
          </button>
        </header>

        {error && <div className="modal-error">{error}</div>}
        {!diff && !error && <div className="modal-loading">正在读取版本…</div>}

        {diff && (
          <div className="diff-body">
            <div className="summary-compare">
              <div>
                <span>之前</span>
                <p>{diff.summary_from}</p>
              </div>
              <div className="summary-arrow">→</div>
              <div>
                <span>之后</span>
                <p>{diff.summary_to}</p>
              </div>
            </div>

            <div className="diff-grid">
              <div>
                <div className="diff-section-title">
                  新增主张 <b>{diff.added.length}</b>
                </div>
                {diff.added.length === 0 && <p className="muted">没有新增主张。</p>}
                {diff.added.map((claim) => (
                  <div className="diff-claim added" key={claim.id}>
                    <span>{claimTypeLabel[claim.claim_type]}</span>
                    <p>{claim.text}</p>
                  </div>
                ))}
              </div>
              <div>
                <div className="diff-section-title">
                  状态变化 <b>{diff.status_changes.length}</b>
                </div>
                {diff.status_changes.length === 0 && (
                  <p className="muted">没有主张状态变化。</p>
                )}
                {diff.status_changes.map((change) => (
                  <div className="diff-claim changed" key={change.claim.id}>
                    <span>
                      {statusLabel[change.from]} → {statusLabel[change.to]}
                    </span>
                    <p>{change.claim.text}</p>
                  </div>
                ))}
              </div>
            </div>

            <div className="diff-reason">
              <strong>为什么变</strong>
              <p>{diff.reason}</p>
              {trigger && (
                <a href={trigger.url} target="_blank" rel="noreferrer">
                  触发文档：{trigger.title} ↗
                </a>
              )}
            </div>

            <div className="diff-fields">
              {diff.changed_fields.map((field) => (
                <span key={field}>{field}</span>
              ))}
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

