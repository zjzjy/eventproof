import type { Claim, EventDetail } from "../types";
import {
  claimMatchesFilter,
  claimTypeClass,
  claimTypeLabel,
  docTypeLabel,
  formatDate,
  formatDateTime,
  sourceTierLabel,
  strengthBandLabel,
} from "../utils";

type Props = {
  event: EventDetail;
  filter: string;
  onSelectClaim: (claim: Claim) => void;
};

export default function EventThread({ event, filter, onSelectClaim }: Props) {
  const hasDenial = event.claims.some(
    (claim) => claim.claim_type === "denial" && claim.status === "active",
  );

  return (
    <div className="thread">
      {event.documents.map((doc, index) => {
        const claims = doc.claims.filter((claim) => claimMatchesFilter(claim, filter));
        if (!claims.length) return null;
        return (
          <article className="floor" key={doc.id}>
            <div className="floor-rail" aria-hidden="true">
              <span className="floor-number">#{String(index + 1).padStart(2, "0")}</span>
              <span className="floor-line" />
            </div>
            <div className="floor-card">
              <header className="floor-head">
                <div className="floor-head-main">
                  <span className={`doc-badge doc-${doc.doc_type}`}>
                    {docTypeLabel[doc.doc_type] ?? doc.doc_type}
                  </span>
                  <h3>{doc.title.replace(/^通宇通讯[：:]/, "")}</h3>
                </div>
                <time>{formatDate(doc.published_at)}</time>
              </header>
              <div className="floor-meta">
                <span>{doc.source}</span>
                <span>{sourceTierLabel[doc.source_tier] ?? doc.source_tier}</span>
                <span>披露 {formatDate(doc.published_at)}（日期级）</span>
                <span>抓取 {formatDateTime(doc.ingested_at)}（推断）</span>
                <span>{claims.length} 条主张</span>
              </div>

              <div className="claim-list">
                {claims.map((claim) => {
                  const denied = claim.status === "denied";
                  const unverified = claim.status === "unverified";
                  return (
                    <div
                      className={[
                        "claim-card",
                        `claim-${claimTypeClass[claim.claim_type]}`,
                        `role-${claim.claim_role}`,
                        denied ? "is-denied" : "",
                        unverified ? "is-unverified" : "",
                      ].join(" ")}
                      key={claim.id}
                      role="button"
                      tabIndex={0}
                      onClick={() => onSelectClaim(claim)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          onSelectClaim(claim);
                        }
                      }}
                    >
                      <div className="claim-top">
                        <span className={`type-chip type-${claimTypeClass[claim.claim_type]}`}>
                          {claimTypeLabel[claim.claim_type]}
                        </span>
                        {claim.claim_role === "market_reaction" && (
                          <span className="role-chip">市场反应</span>
                        )}
                        {denied && <span className="state-chip state-denied">已被否认</span>}
                        {unverified && <span className="state-chip state-unverified">未核实</span>}
                        <span className="claim-strength">{claim.strength}</span>
                      </div>
                      <p className="claim-text">{claim.text}</p>
                      <blockquote>“{claim.quote}”</blockquote>
                      <div className="claim-bottom">
                        <div className="strength-track" aria-label={`证据强度 ${claim.strength}`}>
                          <span
                            className={`strength-fill fill-${claim.strength_band}`}
                            style={{ width: `${Math.min(100, claim.strength)}%` }}
                          />
                        </div>
                        <span className="strength-label">
                          {strengthBandLabel(claim.strength_band)} · {claim.strength}/100
                        </span>
                        <a
                          href={doc.url}
                          target="_blank"
                          rel="noreferrer"
                          className="source-link"
                          onClick={(event) => event.stopPropagation()}
                        >
                          原文
                        </a>
                      </div>
                      {claim.claim_type === "rumor" && denied && hasDenial && (
                        <div className="claim-note note-denied">
                          公司已在同一事件中否认这条传闻；原说法保留，不删除。
                        </div>
                      )}
                      {claim.claim_role === "market_reaction" && (
                        <div className="claim-note note-market">
                          交易所披露的市场异动事实；只能说明反应，不证明因果。
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              <footer className="floor-foot">
                <span>
                  {doc.source} · {claims.length} 条主张 · 1 个披露主体
                </span>
                <a href={doc.url} target="_blank" rel="noreferrer">
                  查看原文 →
                </a>
              </footer>
            </div>
          </article>
        );
      })}
    </div>
  );
}

