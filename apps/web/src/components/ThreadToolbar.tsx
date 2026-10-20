type Props = {
  filter: string;
  setFilter: (filter: string) => void;
  view: "thread" | "brief";
  setView: (view: "thread" | "brief") => void;
  counts: Record<string, number>;
};

const FILTERS: Array<[string, string]> = [
  ["all", "全部"],
  ["fact", "事实"],
  ["denial", "否认"],
  ["rumor", "传闻"],
  ["market", "市场"],
];

export default function ThreadToolbar({
  filter,
  setFilter,
  view,
  setView,
  counts,
}: Props) {
  return (
    <div className="thread-toolbar">
      <div className="filter-tabs">
        {FILTERS.map(([key, label]) => (
          <button
            key={key}
            className={filter === key ? "active" : ""}
            onClick={() => setFilter(key)}
          >
            {label}
            <span>{counts[key] ?? 0}</span>
          </button>
        ))}
      </div>
      <div className="view-toggle">
        <button className={view === "thread" ? "active" : ""} onClick={() => setView("thread")}>
          事件串
        </button>
        <button className={view === "brief" ? "active" : ""} onClick={() => setView("brief")}>
          简报
        </button>
      </div>
    </div>
  );
}

