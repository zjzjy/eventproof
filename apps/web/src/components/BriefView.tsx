import type { EventDetail } from "../types";
import {
  claimTypeLabel,
  formatDate,
  formatDateTime,
  statusLabel,
  strengthBandLabel,
} from "../utils";

type Props = {
  event: EventDetail;
};

export default function BriefView({ event }: Props) {
  const facts = event.claims.filter(
    (claim) => claim.claim_type === "fact" && claim.claim_role !== "market_reaction",
  );
  const denied = event.claims.filter((claim) => claim.status === "denied");
  const market = event.claims.filter((claim) => claim.claim_role === "market_reaction");

  return (
    <div className="brief-view">
      <section className="brief-hero">
        <div className="eyebrow">EVENT BRIEF / 事件简报</div>
        <h2>{event.title}</h2>
        <p>{event.summary}</p>
        <div className="brief-time-grid">
          <div>
            <span>事情发生</span>
            <strong>{formatDate(event.occurred_at)}</strong>
            <small>{event.occurred_precision === "day" ? "日期级" : event.occurred_precision}</small>
          </div>
          <div>
            <span>披露时间</span>
            <strong>{formatDate(event.disclosed_at)}</strong>
            <small>{event.disclosed_precision === "day" ? "日期级" : event.disclosed_precision}</small>
          </div>
          <div>
            <span>首次抓取</span>
            <strong>{formatDateTime(event.first_ingested_at)}</strong>
            <small>演示推断</small>
          </div>
          <div>
            <span>最近更新</span>
            <strong>{formatDateTime(event.updated_at)}</strong>
            <small>v{event.revision.version}</small>
          </div>
        </div>
      </section>

      <div className="brief-columns">
        <section className="brief-panel">
          <div className="panel-title">
            <span>我们知道</span>
            <b>{facts.length} 条事实</b>
          </div>
          <ul className="brief-list">
            {facts.slice(0, 6).map((claim) => (
              <li key={claim.id}>
                <span className={`mini-type type-${claim.claim_type}`}>
                  {claimTypeLabel[claim.claim_type]}
                </span>
                {claim.text}
                <small>{Math.round(claim.strength)} 分</small>
              </li>
            ))}
          </ul>
        </section>
        <section className="brief-panel">
          <div className="panel-title">
            <span>不知道 / 有争议</span>
            <b>{denied.length} 条已否认</b>
          </div>
          <ul className="brief-list denied-list">
            {denied.map((claim) => (
              <li key={claim.id}>
                <span className="mini-type type-rumor">传闻</span>
                {claim.text}
                <small>已否认</small>
              </li>
            ))}
            <li>
              <span className="mini-type type-unknown">未知</span>
              交易最终完成时间：公告未披露
              <small>未量化</small>
            </li>
          </ul>
        </section>
      </div>

      <section className="brief-table-wrap">
        <div className="panel-title">
          <span>主张表</span>
          <b>{event.claims.length} 条</b>
        </div>
        <table className="claim-table">
          <thead>
            <tr>
              <th>类型</th>
              <th>主张</th>
              <th>状态</th>
              <th>强度</th>
            </tr>
          </thead>
          <tbody>
            {event.claims.map((claim) => (
              <tr key={claim.id}>
                <td>
                  <span className={`type-chip type-${claim.claim_type}`}>
                    {claimTypeLabel[claim.claim_type]}
                  </span>
                </td>
                <td>{claim.text}</td>
                <td>{statusLabel[claim.status]}</td>
                <td>
                  {Math.round(claim.strength)} · {strengthBandLabel(claim.strength_band)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="brief-revisions">
        <div className="panel-title">
          <span>版本链</span>
          <b>{event.revisions.length} 个版本</b>
        </div>
        {event.revisions.map((revision) => (
          <div className="revision-row" key={revision.id}>
            <span className="revision-version">v{revision.version}</span>
            <time>{formatDateTime(revision.knowledge_at)}</time>
            <p>{revision.summary}</p>
            <div className="revision-fields">
              {(revision.changed_fields || []).map((field) => (
                <span key={field}>{field}</span>
              ))}
            </div>
          </div>
        ))}
      </section>
    </div>
  );
}

