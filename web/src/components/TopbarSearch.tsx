import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import type { ReaderChapter, ReaderSectionEntry } from "../lib/generated-data";
import { formatPageRange, stripGuideDots } from "../lib/formatters";
import {
  buildWarmedSearchState,
  rankSearchResults,
  resolveSearchNavigation,
  type SearchWarmStatus,
  warmSearchEntries,
} from "../lib/search";

type TopbarSearchProps = {
  searchEntries: ReaderSectionEntry[];
  chapters: ReaderChapter[];
  onFocusSearch?: () => void;
};

type SearchUiState = "idle" | "loading" | SearchWarmStatus | "error";

export function TopbarSearch({ searchEntries, chapters, onFocusSearch }: TopbarSearchProps): JSX.Element {
  const navigate = useNavigate();
  const location = useLocation();
  const searchRootRef = useRef<HTMLDivElement | null>(null);
  const warmTimeoutRef = useRef<number | null>(null);
  const [query, setQuery] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const [warmedEntries, setWarmedEntries] = useState<ReturnType<typeof warmSearchEntries> | null>(null);
  const [searchUiState, setSearchUiState] = useState<SearchUiState>("idle");

  useEffect(() => {
    setIsOpen(false);
    setActiveIndex(0);
  }, [location.pathname]);

  useEffect(() => {
    return () => {
      if (warmTimeoutRef.current !== null) {
        window.clearTimeout(warmTimeoutRef.current);
      }
    };
  }, []);

  useEffect(() => {
    function handlePointerDown(event: MouseEvent): void {
      if (!searchRootRef.current?.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }

    window.addEventListener("mousedown", handlePointerDown);
    return () => window.removeEventListener("mousedown", handlePointerDown);
  }, []);

  const visibleResults = useMemo(() => {
    if (!warmedEntries) {
      return [];
    }

    return rankSearchResults(warmedEntries, query, 9);
  }, [query, warmedEntries]);

  function warmSearch(): void {
    if (warmedEntries || searchUiState === "loading") {
      return;
    }

    setSearchUiState("loading");
    warmTimeoutRef.current = window.setTimeout(() => {
      try {
        const nextState = buildWarmedSearchState(searchEntries);
        setWarmedEntries(nextState.entries);
        setSearchUiState(nextState.status);
      } catch {
        setSearchUiState("error");
      }
    }, 80);
  }

  function ensureWarmedEntries(): ReturnType<typeof warmSearchEntries> {
    if (warmedEntries) {
      return warmedEntries;
    }

    if (warmTimeoutRef.current !== null) {
      window.clearTimeout(warmTimeoutRef.current);
      warmTimeoutRef.current = null;
    }

    const nextState = buildWarmedSearchState(searchEntries);
    setWarmedEntries(nextState.entries);
    setSearchUiState(nextState.status);
    return nextState.entries;
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    const resolvedResults =
      visibleResults.length > 0 || !query.trim() ? visibleResults : rankSearchResults(ensureWarmedEntries(), query, 9);
    const routePath = resolveSearchNavigation({ query, results: resolvedResults, activeIndex, chapters });
    if (!routePath) {
      return;
    }

    navigate(routePath);
  }

  return (
    <div ref={searchRootRef} className="search-shell">
      <form className="search-form" onSubmit={handleSubmit}>
        <label className="visually-hidden" htmlFor="reader-search-input">
          장 제목, 항목명, 본문 일부 검색
        </label>
        <input
          id="reader-search-input"
          type="search"
          value={query}
          placeholder="장 제목, 항목명, 본문 일부를 검색하세요"
          autoComplete="off"
          onFocus={() => {
            onFocusSearch?.();
            warmSearch();
            setIsOpen(true);
          }}
          onChange={(event) => {
            setQuery(event.target.value);
            setActiveIndex(0);
            setIsOpen(true);
          }}
          onKeyDown={(event) => {
            if (event.key === "ArrowDown") {
              event.preventDefault();
              setActiveIndex((current) => Math.min(current + 1, Math.max(visibleResults.length - 1, 0)));
              return;
            }

            if (event.key === "ArrowUp") {
              event.preventDefault();
              setActiveIndex((current) => Math.max(current - 1, 0));
              return;
            }

            if (event.key === "Escape") {
              setIsOpen(false);
            }
          }}
        />
        {query ? (
          <button type="button" className="search-reset" onClick={() => setQuery("")}>초기화</button>
        ) : null}
      </form>

      {isOpen ? (
        <div className="search-dropdown surface">
          {searchUiState === "loading" ? (
            <div className="empty-card compact">
              <p>검색 카탈로그를 준비하고 있습니다.</p>
            </div>
          ) : searchUiState === "error" ? (
            <div className="empty-card compact error-state">
              <p>검색 카탈로그 준비에 실패했습니다. 다시 포커스하면 재시도합니다.</p>
            </div>
          ) : query && visibleResults.length > 0 ? (
            visibleResults.map((entry, index) => (
              <button
                key={`${entry.chapterSlug}-${entry.sectionId}-${entry.id}`}
                type="button"
                className={`search-result${index === activeIndex ? " is-active" : ""}`}
                onMouseEnter={() => setActiveIndex(index)}
                onClick={() => navigate(entry.routePath)}
              >
                <span className="result-kicker">{stripGuideDots(entry.partTitle)}</span>
                <strong>{stripGuideDots(entry.sectionTitle)}</strong>
                <span>{stripGuideDots(entry.chapterTitle)}</span>
                <p>{entry.excerpt}</p>
                <span className="result-meta">
                  {formatPageRange(entry.pageStart, entry.pageEnd, entry.pageLabelStart, entry.pageLabelEnd)}
                </span>
              </button>
            ))
          ) : query ? (
            <div className="empty-card compact">
              <p>
                {searchUiState === "empty"
                  ? "검색 인덱스가 비어 있습니다."
                  : "섹션 검색 결과가 없으면 Enter로 장 제목 fallback 이동을 시도합니다."}
              </p>
            </div>
          ) : searchUiState === "ready" ? (
            <div className="empty-card compact">
              <p>검색 준비 완료. 장 제목, 섹션 제목, 본문 일부를 바로 찾을 수 있습니다.</p>
            </div>
          ) : searchUiState === "empty" ? (
            <div className="empty-card compact">
              <p>검색 가능한 섹션 카탈로그가 비어 있습니다.</p>
            </div>
          ) : (
            <div className="empty-card compact">
              <p>검색창을 처음 누르면 검색 카탈로그를 준비합니다.</p>
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}
