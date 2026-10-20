import type { Notification } from "../types";
import { formatDateTime } from "../utils";

type Props = {
  open: boolean;
  items: Notification[];
  onClose: () => void;
  onRead: (id: string) => void;
  onOpenDiff: (from: number, to: number) => void;
  onOpenEvent: () => void;
};

export default function NotificationDrawer({
  open,
  items,
  onClose,
  onRead,
  onOpenDiff,
  onOpenEvent,
}: Props) {
  if (!open) return null;
  const unread = items.filter((item) => !item.read_at).length;

  return (
    <div className="overlay drawer-overlay" onMouseDown={onClose}>
      <aside
        className="notification-drawer"
        onMouseDown={(event) => event.stopPropagation()}
        aria-modal="true"
      >
        <header className="modal-head">
          <div>
            <div className="eyebrow">NOTIFICATIONS / 通知</div>
            <h2>只对实质变化打扰你</h2>
            <p>{unread} 条未读 · 重复转载不推送</p>
          </div>
          <button className="icon-button" onClick={onClose} aria-label="关闭">
            ×
          </button>
        </header>

        <div className="notification-list">
          {items.map((item) => {
            const isDenial = item.diff_json?.type === "denial";
            return (
              <article
                className={`notification-card level-${item.level.toLowerCase()} ${
                  item.read_at ? "is-read" : ""
                }`}
                key={item.id}
              >
                <div className="notification-top">
                  <span className={`level-chip level-${item.level.toLowerCase()}`}>
                    {item.level}
                  </span>
                  <time>{formatDateTime(item.created_at)}</time>
                  {!item.read_at && <span className="unread-dot" />}
                </div>
                <h3>{item.title}</h3>
                <p>{item.body}</p>
                <div className="why-box">
                  <strong>为什么通知我</strong>
                  <span>{item.why}</span>
                </div>
                <div className="notification-actions">
                  <button
                    className="text-button"
                    onClick={() => {
                      onOpenEvent();
                      if (isDenial) onOpenDiff(2, 3);
                    }}
                  >
                    查看变化 →
                  </button>
                  {!item.read_at && (
                    <button className="quiet-button" onClick={() => onRead(item.id)}>
                      标记已读
                    </button>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      </aside>
    </div>
  );
}

