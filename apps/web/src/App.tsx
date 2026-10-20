import { useEffect, useMemo, useState } from "react";
import { api } from "./api";
import AsOfBar from "./components/AsOfBar";
import BriefView from "./components/BriefView";
import ConclusionCard from "./components/ConclusionCard";
import DiffModal from "./components/DiffModal";
import EventThread from "./components/EventThread";
import EvidenceDrawer from "./components/EvidenceDrawer";
import NotificationDrawer from "./components/NotificationDrawer";
import ThreadToolbar from "./components/ThreadToolbar";
import type {
  Claim,
  EventDetail,
  EventSummary,
  Meta,
  Notification,
} from "./types";
import {
  claimMatchesFilter,
  formatDate,
  formatDateTime,
  statusDetailChips,
} from "./utils";

type DiffTarget = { from: number; to: number };

export default function App() {
  const [events, setEvents] = useState<EventSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [event, setEvent] = useState<EventDetail | null>(null);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [selectedClaim, setSelectedClaim] = useState<Claim | null>(null);
  const [asOf, setAsOf] = useState<string | null>(null);
  const [filter, setFilter] = useState("all");
  const [view, setView] = useState<"thread" | "brief">("thread");
  const [showNotifications, setShowNotifications] = useState(false);
  const [diff, setDiff] = useState<DiffTarget | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.events(), api.notifications(), api.meta()])
      .then(([eventsResponse, notificationResponse, metaResponse]) => {
        setEvents(eventsResponse.items);
        setNotifications(notificationResponse.items);
        setMeta(metaResponse);
        if (eventsResponse.items[0]) setSelectedId(eventsResponse.items[0].id);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    setLoading(true);
    setSelectedClaim(null);
    api
      .event(selectedId, asOf)
      .then((data) => {
        setEvent(data);
        setError(null);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [selectedId, asOf]);

  useEffect(() => {
    const onKey = (keyboardEvent: KeyboardEvent) => {
      if (keyboardEvent.key === "Escape") {
        setShowNotifications(false);
        setDiff(null);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const counts = useMemo(() => {
    const claims = event?.claims ?? [];
    return {
      all: claims.length,
      fact: claims.filter((claim) => claimMatchesFilter(claim, "fact")).length,
      denial: claims.filter((claim) => claimMatchesFilter(claim, "denial")).length,
      rumor: claims.filter((claim) => claimMatchesFilter(claim, "rumor")).length,
      market: claims.filter((claim) => claimMatchesFilter(claim, "market")).length,
    };
  }, [event]);

  const unread = notifications.filter((item) => !item.read_at).length;

  const handleRead = async (id: string) => {
    await api.markRead(id);
    setNotifications((items) =>
      items.map((item) =>
        item.id === id ? { ...item, read_at: new Date().toISOString() } : item,
      ),
    );
  };

  const openExport = () => {
    if (!event) return;
    window.location.href = api.exportUrl(event.id);
  };

  if (!event && loading) {
    return (
      <div className="boot-screen">
        <div className="boot-stamp">证</div>
        <h1>事证 EventProof</h1>
        <p>正在载入证据账本…</p>
      </div>
    );
  }

  if (!event && error) {
    return (
      <div className="boot-screen error-screen">
        <div className="boot-stamp">!</div>
        <h1>载入失败</h1>
        <p>{error}</p>
        <button className="solid-button" onClick={() => window.location.reload()}>
          重试
        </button>
      </div>
    );
  }

  if (!event) {
    return (
      <div className="boot-screen">
        <div className="boot-stamp">证</div>
        <h1>还没有事件</h1>
        <p>请在收件箱选择一个事件。</p>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-stamp">证</div>
          <div>
            <div className="brand-name">事证</div>
            <div className="brand-sub">EVENTPROOF / EVIDENCE LEDGER</div>
          </div>
        </div>
        <div className="topbar-center">
          <span className="watch-chip">关注 1</span>
          <span className="ticker">002792 通宇通讯</span>
          <span className="topbar-divider" />
          <span className="topbar-note">不是资讯流，是事件证据账本</span>
        </div>
        <div className="topbar-actions">
          <span className={`live-chip ${asOf ? "replay" : ""}`}>
            {asOf ? `回放 ${formatDateTime(asOf)}` : "实时视图"}
          </span>
          <button className="notification-button" onClick={() => setShowNotifications(true)}>
            通知
            {unread > 0 && <span className="notification-badge">{unread}</span>}
          </button>
        </div>
      </header>

      <div className="workspace">
        <aside className="event-rail">
          <div className="rail-head">
            <div>
              <div className="eyebrow">INBOX / 事件收件箱</div>
              <h2>关注事件</h2>
            </div>
            <span className="rail-count">{events.length}</span>
          </div>

          <div className="event-list">
            {events.map((item) => (
              <button
                key={item.id}
                className={`event-list-card ${item.id === selectedId ? "active" : ""}`}
                onClick={() => {
                  setSelectedId(item.id);
                  setAsOf(null);
                }}
              >
                <div className="event-list-top">
                  <span className="event-list-code">{item.security_code}</span>
                  <span className="event-list-strength">{Math.round(item.evidence_strength)}</span>
                </div>
                <h3>{item.title}</h3>
                <p>{item.summary}</p>
                <div className="event-list-chips">
                  {statusDetailChips(item.status_detail)
                    .slice(0, 3)
                    .map((chip) => (
                      <span className={`mini-status tone-${chip.tone}`} key={chip.label}>
                        {chip.label}
                      </span>
                    ))}
                </div>
                <div className="event-list-foot">
                  <span>{item.sources_count} 份披露</span>
                  <span>{item.denied_claims_count} 条已否认</span>
                  <span>{formatDate(item.updated_at)}</span>
                </div>
              </button>
            ))}
          </div>

          <div className="rail-block">
            <div className="rail-block-title">关注标的</div>
            <div className="ticker-row">
              <strong>通宇通讯</strong>
              <span>002792 · SZSE</span>
            </div>
            <div className="ticker-row muted">
              <span>事件线</span>
              <span>收购 + 合作传闻澄清</span>
            </div>
          </div>

          <div className="rail-block demo-hint">
            <div className="rail-block-title">演示路径</div>
            <p>把时间条拖到“08-07 传闻”，再拖到“08-07 否认”，看结论如何翻转。</p>
          </div>

          <div className="rail-block meta-block">
            <div className="rail-block-title">数据</div>
            <p>
              {meta?.model ?? "qwen3.8-flash"} · 预计算
              <br />
              估算成本 ¥{meta?.total_cost_cny?.toFixed(4) ?? "0.0000"}
              <br />
              fixture / SQLite
            </p>
          </div>
        </aside>

        <main className="event-main">
          <header className="event-header">
            <div>
              <div className="eyebrow">
                EVENT / {event.security_code} · {event.exchange}
              </div>
              <h1>{event.title}</h1>
              <p className="event-subtitle">
                {event.primary_entity} · {event.event_type} · 事件串只收录来源与证据
              </p>
            </div>
            <div className="event-header-side">
              <div className="header-strength">
                <strong>{Math.round(event.evidence_strength)}</strong>
                <span>核心证据强度</span>
              </div>
              <a
                className="quiet-link"
                href={`https://www.cninfo.com.cn/new/disclosure/stock?stockCode=${event.security_code}`}
                target="_blank"
                rel="noreferrer"
              >
                巨潮资讯 ↗
              </a>
            </div>
          </header>

          <ConclusionCard
            event={event}
            onOpenDiff={(from, to) => setDiff({ from, to })}
            onExport={openExport}
          />

          <details className="merge-note">
            <summary>
              <span className="merge-icon">⌘</span>
              <span>
                {event.sources_count} 篇官方披露 → 1 个事件
                <small>澄清公告显式引用对外投资公告；共享主体、标的、25% 比例</small>
              </span>
              <span className="merge-more">合并依据</span>
            </summary>
            <div className="merge-body">
              {event.merge_decisions.map((merge) => (
                <div className="merge-row" key={merge.id}>
                  <div>
                    <strong>{merge.document_title}</strong>
                    <span>{merge.relation} · score {merge.score.toFixed(2)}</span>
                  </div>
                  <p>{merge.reason}</p>
                  <div className="merge-slots">
                    {Object.entries(merge.shared_slots).map(([key, value]) => (
                      <span key={key}>
                        {key}: {value}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </details>

          <AsOfBar
            variants={event.available_as_of}
            value={asOf}
            onChange={(value) => setAsOf(value)}
          />

          <ThreadToolbar
            filter={filter}
            setFilter={setFilter}
            view={view}
            setView={setView}
            counts={counts}
          />

          {view === "thread" ? (
            <EventThread event={event} filter={filter} onSelectClaim={setSelectedClaim} />
          ) : (
            <BriefView event={event} />
          )}

          <section className="revision-strip">
            <div className="strip-head">
              <div>
                <div className="eyebrow">VERSIONS / 版本记录</div>
                <strong>结论不是一次生成的，是一条一条证据叠出来的</strong>
              </div>
              <span>点击版本查看相邻 diff</span>
            </div>
            <div className="revision-buttons">
              {event.revisions.map((revision) => (
                <button
                  key={revision.id}
                  className={revision.id === event.revision.id ? "active" : ""}
                  onClick={() => {
                    if (revision.version > 1) {
                      setDiff({ from: revision.version - 1, to: revision.version });
                    }
                  }}
                >
                  <b>v{revision.version}</b>
                  <span>{formatDateTime(revision.knowledge_at)}</span>
                  <small>{revision.reason}</small>
                </button>
              ))}
            </div>
          </section>

          <footer className="page-footer">
            <span>事证 EventProof · 投资事件证据时间线</span>
            <span>关键数字均可回到原文；证据强度不是真值概率，不构成投资建议。</span>
          </footer>
        </main>

        <EvidenceDrawer
          claim={selectedClaim}
          event={event}
          onClose={() => setSelectedClaim(null)}
        />
      </div>

      <NotificationDrawer
        open={showNotifications}
        items={notifications}
        onClose={() => setShowNotifications(false)}
        onRead={handleRead}
        onOpenDiff={(from, to) => {
          setShowNotifications(false);
          setDiff({ from, to });
        }}
        onOpenEvent={() => setShowNotifications(false)}
      />

      {diff && event && (
        <DiffModal
          eventId={event.id}
          fromVersion={diff.from}
          toVersion={diff.to}
          documents={event.documents}
          onClose={() => setDiff(null)}
        />
      )}
    </div>
  );
}

