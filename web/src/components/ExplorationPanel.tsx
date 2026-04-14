import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import type { ReaderExplorationEntry } from "../lib/generated-data";
import { formatPageRange, getCategoryLabel } from "../lib/formatters";

type ExplorationPanelProps = {
  title: string;
  entries: ReaderExplorationEntry[];
  emptyMessage: string;
};

export function ExplorationPanel({ title, entries, emptyMessage }: ExplorationPanelProps): JSX.Element {
  const categoryCounts = useMemo(() => {
    const counts = new Map<string, number>();

    for (const entry of entries) {
      for (const category of entry.categories) {
        counts.set(category, (counts.get(category) ?? 0) + 1);
      }
    }

    return [...counts.entries()].sort((left, right) => {
      if (right[1] !== left[1]) {
        return right[1] - left[1];
      }

      return left[0].localeCompare(right[0], "ko");
    });
  }, [entries]);

  const [activeCategory, setActiveCategory] = useState<string>(categoryCounts[0]?.[0] ?? "");

  useEffect(() => {
    setActiveCategory((current) => {
      if (current && categoryCounts.some(([category]) => category === current)) {
        return current;
      }

      return categoryCounts[0]?.[0] ?? "";
    });
  }, [categoryCounts]);

  const visibleEntries = useMemo(() => {
    if (!activeCategory) {
      return entries.slice(0, 8);
    }

    return entries.filter((entry) => entry.categories.includes(activeCategory)).slice(0, 8);
  }, [activeCategory, entries]);

  return (
    <aside className="surface exploration-panel">
      <div className="section-heading compact">
        <span className="eyebrow">Exploration</span>
        <h2>{title}</h2>
      </div>
      {categoryCounts.length > 0 ? (
        <div className="chip-row">
          {categoryCounts.map(([category, count]) => (
            <button
              key={category}
              type="button"
              className={`chip${activeCategory === category ? " is-active" : ""}`}
              onClick={() => setActiveCategory(category)}
            >
              {getCategoryLabel(category)}
              <span>{count}</span>
            </button>
          ))}
        </div>
      ) : null}

      <div className="result-stack">
        {visibleEntries.length > 0 ? (
          visibleEntries.map((entry) => (
            <Link key={`${entry.routePath}-${entry.id}`} to={entry.routePath} className="result-card">
              <span className="result-kicker">{entry.partTitle}</span>
              <strong>{entry.displayTitle}</strong>
              <span>{entry.chapterDisplayTitle}</span>
              <p>{entry.excerpt}</p>
              <span className="result-meta">
                {formatPageRange(entry.pageStart, entry.pageEnd, entry.pageLabelStart, entry.pageLabelEnd)}
              </span>
            </Link>
          ))
        ) : (
          <div className="empty-card">
            <p>{emptyMessage}</p>
          </div>
        )}
      </div>
    </aside>
  );
}
