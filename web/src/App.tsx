import { useEffect, useState } from "react";
import { Link, Navigate, Route, Routes, useLocation, useMatch } from "react-router-dom";

import { ExplorationPanel } from "./components/ExplorationPanel";
import { QAPage } from "./components/QAPage";
import { ReaderArticle } from "./components/ReaderArticle";
import { TocPanel } from "./components/TocPanel";
import { TopbarSearch } from "./components/TopbarSearch";
import type { ReaderData } from "./lib/generated-data";
import { loadGeneratedData, resolveCanonicalChapterRoute } from "./lib/generated-data";
import { compactSummary, formatDateTime, formatPageRange, stripGuideDots } from "./lib/formatters";

type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; data: ReaderData };

function useBodyScrollLock(locked: boolean): void {
  useEffect(() => {
    if (!locked) {
      return;
    }

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [locked]);
}

function HomePage({ data }: { data: ReaderData }): JSX.Element {
  return (
    <div className="page-stack">
      <section className="surface landing-hero">
        <div className="chapter-hero-copy">
          <span className="eyebrow">TmDS Reader</span>
          <h1>심판편람 제14판 PDF를 챕터 단위로 탐색하고 읽을 수 있도록 구조화한 웹 리더입니다.</h1>
          <p>
            PDF 북마크 구조를 spine으로 삼고, 인쇄 페이지 라벨과 PDF 페이지 번호를 함께 보존해
            검색과 장/절 탐색을 안정적으로 연결합니다.
          </p>
          <p>
            `content:prepare`가 만드는 generated JSON을 그대로 읽는 리더이기 때문에, 데이터와 UI를 같은
            워크스페이스에서 빠르게 검증할 수 있습니다.
          </p>
        </div>
        <div className="meta-grid">
          <div className="meta-card">
            <span className="meta-label">동기화 시각</span>
            <strong>{formatDateTime(data.manifest.syncedAt)}</strong>
          </div>
          <div className="meta-card">
            <span className="meta-label">챕터 수</span>
            <strong>{data.meta.chapterCount}</strong>
          </div>
          <div className="meta-card">
            <span className="meta-label">페이지 수</span>
            <strong>{data.meta.pageCount}</strong>
          </div>
          <div className="meta-card">
            <span className="meta-label">탐색 엔트리</span>
            <strong>{data.explorationEntries.length}</strong>
          </div>
        </div>
      </section>

      <section className="content-grid">
        <div className="reader-column">
          {data.parts.map((part) => (
            <section key={part.id} className="surface catalog-section">
              <div className="section-heading">
                <span className="eyebrow">{part.label}</span>
                <h2>{part.title}</h2>
              </div>
              <div className="chapter-card-grid">
                {part.chapters.map((chapter) => (
                  <Link key={chapter.slug} to={chapter.sectionCatalog[0]?.routePath} className="chapter-card">
                    <span className="result-kicker">{stripGuideDots(chapter.partTitle)}</span>
                    <strong>{chapter.displayTitle}</strong>
                    <p>{compactSummary(chapter.summary, 132)}</p>
                    <div className="chapter-card-meta">
                      <span>
                        {formatPageRange(
                          chapter.pageStart,
                          chapter.pageEnd,
                          chapter.pageLabelStart,
                          chapter.pageLabelEnd
                        )}
                      </span>
                      <span>{chapter.tocItemCount}개 항목</span>
                      <span>{chapter.hasImage ? `이미지 ${chapter.imageCount}개` : "텍스트 중심"}</span>
                    </div>
                  </Link>
                ))}
              </div>
            </section>
          ))}
        </div>

        <ExplorationPanel
          title="전체 탐색 요약"
          entries={data.explorationEntries}
          emptyMessage="탐색 엔트리가 아직 없습니다."
        />
      </section>
    </div>
  );
}

function ChapterPage({ data }: { data: ReaderData }): JSX.Element {
  const location = useLocation();
  const sectionMatch = useMatch("/chapter/:chapterSlug/:sectionId");
  const chapterMatch = useMatch("/chapter/:chapterSlug");
  const chapterSlug = sectionMatch?.params.chapterSlug ?? chapterMatch?.params.chapterSlug ?? "";
  const requestedSectionId = sectionMatch?.params.sectionId;

  const chapter = data.chapterMap.get(chapterSlug);
  if (!chapter) {
    return <Navigate to="/" replace />;
  }
  const currentPart = data.parts.find((part) => part.chapters.some((candidate) => candidate.slug === chapter.slug)) ?? null;

  const chapterRoute = resolveCanonicalChapterRoute(chapter, requestedSectionId);
  if (location.pathname !== chapterRoute.canonicalPath) {
    return <Navigate to={chapterRoute.canonicalPath} replace />;
  }

  return (
    <div className="page-stack">
      <ReaderArticle
        chapter={chapter}
        partChapters={currentPart?.chapters ?? []}
        activeSectionId={chapterRoute.activeSectionId}
        builtAt={data.meta.builtAt}
      />
    </div>
  );
}

function ReaderShell({ data }: { data: ReaderData }): JSX.Element {
  const location = useLocation();
  const sectionMatch = useMatch("/chapter/:chapterSlug/:sectionId");
  const chapterMatch = useMatch("/chapter/:chapterSlug");
  const chapterSlug = sectionMatch?.params.chapterSlug ?? chapterMatch?.params.chapterSlug ?? null;
  const currentChapter = chapterSlug ? data.chapterMap.get(chapterSlug) ?? null : null;
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  useBodyScrollLock(isDrawerOpen);

  useEffect(() => {
    setIsDrawerOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    const title = currentChapter ? `${currentChapter.displayTitle} · TmDS Reader` : "TmDS Reader";
    document.title = title;
  }, [currentChapter]);

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-row">
          <button type="button" className="menu-button" onClick={() => setIsDrawerOpen(true)} aria-label="목차 열기">
            목차
          </button>
          <Link to="/" className="brand-block">
            <span className="eyebrow">TmDS Reader</span>
            <strong>{currentChapter?.displayTitle ?? "심판편람 제14판"}</strong>
          </Link>
        </div>
        <TopbarSearch
          searchEntries={data.searchEntries}
          chapters={data.chapters}
          onFocusSearch={() => setIsDrawerOpen(false)}
        />
      </header>

      <div className="layout-frame">
        <aside className="rail surface rail-desktop">
          <div className="section-heading compact">
            <span className="eyebrow">Contents</span>
            <h2>목차</h2>
          </div>
          <TocPanel parts={data.parts} currentChapter={currentChapter} />
        </aside>

        <main className="main-panel">
          <Routes>
            <Route path="/" element={<HomePage data={data} />} />
            <Route path="/qa/page/:pageNumber" element={<QAPage />} />
            <Route path="/chapter/:chapterSlug" element={<ChapterPage data={data} />} />
            <Route path="/chapter/:chapterSlug/:sectionId" element={<ChapterPage data={data} />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>

      <div className={`drawer-shell${isDrawerOpen ? " is-open" : ""}`} aria-hidden={!isDrawerOpen}>
        <button type="button" className="drawer-backdrop" onClick={() => setIsDrawerOpen(false)} aria-label="목차 닫기" />
        <aside className="drawer-panel surface">
          <div className="drawer-header">
            <div>
              <span className="eyebrow">Contents</span>
              <h2>모바일 목차</h2>
            </div>
            <button type="button" className="close-button" onClick={() => setIsDrawerOpen(false)}>
              닫기
            </button>
          </div>
          <TocPanel parts={data.parts} currentChapter={currentChapter} onNavigate={() => setIsDrawerOpen(false)} />
        </aside>
      </div>
    </div>
  );
}

export function App(): JSX.Element {
  const [state, setState] = useState<LoadState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;

    loadGeneratedData()
      .then((data) => {
        if (!cancelled) {
          setState({ status: "ready", data });
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          const message = error instanceof Error ? error.message : String(error);
          setState({ status: "error", message });
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  if (state.status === "loading") {
    return (
      <div className="status-shell">
        <div className="surface status-card">
          <span className="eyebrow">Loading</span>
          <h1>generated JSON을 TmDS 리더에 맞춰 조립하고 있습니다.</h1>
        </div>
      </div>
    );
  }

  if (state.status === "error") {
    return (
      <div className="status-shell">
        <div className="surface status-card error-state">
          <span className="eyebrow">Reader error</span>
          <h1>리더 데이터를 불러오지 못했습니다.</h1>
          <p>{state.message}</p>
          <p>
            먼저 <code>npm run web:prepare</code>로 generated 계약을 동기화한 뒤, 새 번들 앱을 다시 열어 주세요.
          </p>
        </div>
      </div>
    );
  }

  return <ReaderShell data={state.data} />;
}
